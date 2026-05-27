from __future__ import annotations

import argparse
import csv
import logging
import sys
import time
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin

import requests


LOGGER = logging.getLogger("tkmaxx_deals")

TKMAXX_BASE_URL = "https://www.tkmaxx.com/uk/en/"
BLOOMREACH_SEARCH_URL = "https://core.dxpapi.com/api/v1/core/"
BLOOMREACH_ACCOUNT_ID = "7256"
BLOOMREACH_CATALOG_VIEWS = "tkmaxx:tkmaxx-uk"

DEFAULT_QUERIES = [
    "women",
    "men",
    "kids",
    "toys",
    "home",
    "beauty",
    "clearance",
    "shoes",
    "designer",
]

BLOOMREACH_FIELDS = ",".join(
    [
        "pid",
        "code",
        "title",
        "url",
        "brand",
        "price",
        "fmt_price",
        "rrp",
        "fmt_rrp",
        "save_price",
        "fmt_save_price",
        "percent_saving",
        "was_price",
        "fmt_was_price",
        "stock",
        "stock_status",
        "is_low_stock",
        "thumb_image",
        "environment",
        "mh_dept",
        "mh_dept_name",
        "mh_class",
        "mh_class_name",
    ]
)


@dataclass(slots=True)
class Product:
    brand: str
    name: str
    sale_price: float | None
    original_price: float | None
    discount_pct: float | None
    url: str
    product_id: str
    source_query: str
    stock: float | None = None
    stock_status: str | None = None
    department: str | None = None
    product_class: str | None = None
    image_url: str | None = None


def compute_discount(sale: float | None, original: float | None) -> float | None:
    """Compute the percentage discount for a product."""
    if sale is None or original is None or original <= 0:
        return None
    return round((original - sale) / original * 100.0, 2)


def find_best_deals_by_brand(items: Iterable[Product]) -> list[Product]:
    """Return the highest-discounted product found for each brand."""
    best: dict[str, Product] = {}
    for item in items:
        if item.discount_pct is None:
            continue
        current = best.get(item.brand)
        if current is None or _deal_rank(item) > _deal_rank(current):
            best[item.brand] = item
    return sorted(best.values(), key=_deal_rank, reverse=True)


def scrape_query(
    session: requests.Session,
    query: str,
    *,
    rows_per_page: int,
    max_pages: int,
    request_delay: float,
    max_products: int | None = None,
) -> list[Product]:
    """Search TK Maxx's Bloomreach index for one query and return products."""
    products: list[Product] = []
    seen_ids: set[str] = set()
    page = 0
    total_found: int | None = None

    while max_pages <= 0 or page < max_pages:
        start = page * rows_per_page
        data = fetch_bloomreach_page(
            session,
            query,
            start=start,
            rows=rows_per_page,
        )
        response = data.get("response", {})
        docs = response.get("docs") or []
        total_found = _safe_int(response.get("numFound"), default=total_found)

        if not docs:
            break

        for doc in docs:
            product = product_from_bloomreach_doc(doc, source_query=query)
            if product is None or product.product_id in seen_ids:
                continue
            seen_ids.add(product.product_id)
            products.append(product)
            if max_products is not None and len(products) >= max_products:
                return products

        page += 1
        if total_found is not None and page * rows_per_page >= total_found:
            break
        if request_delay > 0:
            time.sleep(request_delay)

    return products


def fetch_bloomreach_page(
    session: requests.Session,
    query: str,
    *,
    start: int,
    rows: int,
) -> dict[str, Any]:
    params = {
        "account_id": BLOOMREACH_ACCOUNT_ID,
        "catalog_views": BLOOMREACH_CATALOG_VIEWS,
        "request_type": "search",
        "search_type": "keyword",
        "q": query,
        "rows": str(rows),
        "start": str(start),
        "url": f"{TKMAXX_BASE_URL}search?st={query}",
        "ref_url": TKMAXX_BASE_URL,
        "fl": BLOOMREACH_FIELDS,
    }
    response = session.get(BLOOMREACH_SEARCH_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    if "response" not in data:
        raise RuntimeError(f"Unexpected Bloomreach response for query {query!r}: {data}")
    return data


def product_from_bloomreach_doc(doc: dict[str, Any], *, source_query: str) -> Product | None:
    product_id = str(doc.get("pid") or doc.get("code") or "").strip()
    name = str(doc.get("title") or "").strip()
    brand = str(doc.get("brand") or "").strip()
    if not product_id or not name:
        return None
    if not brand or brand.lower() == "unbranded":
        brand = "Unbranded"

    sale_price = _safe_float(doc.get("price"))
    original_price = _safe_float(doc.get("rrp"))
    discount = _safe_float(doc.get("percent_saving"))
    if discount is None:
        discount = compute_discount(sale_price, original_price)

    relative_url = str(doc.get("url") or "").strip()
    product_url = urljoin(TKMAXX_BASE_URL, relative_url.lstrip("/"))

    return Product(
        brand=brand,
        name=name,
        sale_price=sale_price,
        original_price=original_price,
        discount_pct=round(discount, 2) if discount is not None else None,
        url=product_url,
        product_id=product_id,
        source_query=source_query,
        stock=_safe_float(doc.get("stock")),
        stock_status=_safe_str(doc.get("stock_status")),
        department=_clean_taxonomy_label(doc.get("mh_dept_name")),
        product_class=_clean_taxonomy_label(doc.get("mh_class_name")),
        image_url=_safe_str(doc.get("thumb_image")),
    )


def scrape_queries(
    queries: Iterable[str],
    *,
    rows_per_page: int,
    max_pages: int,
    request_delay: float,
    max_products_per_query: int | None,
) -> list[Product]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept": "application/json",
        }
    )

    all_products: list[Product] = []
    seen_ids: set[str] = set()
    for query in queries:
        query = query.strip()
        if not query:
            continue
        LOGGER.info("Searching %r", query)
        products = scrape_query(
            session,
            query,
            rows_per_page=rows_per_page,
            max_pages=max_pages,
            request_delay=request_delay,
            max_products=max_products_per_query,
        )
        LOGGER.info("Found %s products for %r", len(products), query)
        for product in products:
            if product.product_id in seen_ids:
                continue
            seen_ids.add(product.product_id)
            all_products.append(product)
    return all_products


def write_products(products: list[Product], output_path: Path) -> None:
    rows = [asdict(product) for product in products]
    columns = [field.name for field in fields(Product)]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.suffix.lower() == ".csv":
        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        return

    try:
        import pandas as pd
    except ImportError as exc:
        raise SystemExit(
            "pandas and openpyxl are required for Excel output. Install dependencies "
            "with `pip install -r requirements.txt`, or choose a .csv output path."
        ) from exc

    df = pd.DataFrame(rows, columns=columns)
    if not df.empty:
        df.sort_values(by="discount_pct", ascending=False, inplace=True, na_position="last")
        df.reset_index(drop=True, inplace=True)
    df.to_excel(output_path, index=False)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Search TK Maxx UK's product index and export the best discount found "
            "for each brand."
        )
    )
    parser.add_argument(
        "--query",
        action="append",
        dest="queries",
        help="Search query to scrape. Repeat to add multiple searches.",
    )
    parser.add_argument(
        "--category",
        action="append",
        dest="categories",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--output",
        default="tkmaxx_best_deals.xlsx",
        help="Output file path. Use .xlsx or .csv.",
    )
    parser.add_argument(
        "--rows-per-page",
        type=int,
        default=100,
        help="Bloomreach rows to request per page.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Maximum pages to request for each query. Use 0 for all pages.",
    )
    parser.add_argument(
        "--max-products-per-query",
        type=int,
        default=None,
        help="Optional product cap per query for smoke tests.",
    )
    parser.add_argument(
        "--request-delay",
        type=float,
        default=0.25,
        help="Seconds to wait between paged API requests.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s: %(message)s",
    )

    if args.rows_per_page <= 0:
        raise SystemExit("--rows-per-page must be greater than 0")
    if args.max_pages < 0:
        raise SystemExit("--max-pages must be 0 or greater")

    queries = args.queries or _queries_from_legacy_categories(args.categories) or DEFAULT_QUERIES
    products = scrape_queries(
        queries,
        rows_per_page=args.rows_per_page,
        max_pages=args.max_pages,
        request_delay=args.request_delay,
        max_products_per_query=args.max_products_per_query,
    )
    best_deals = find_best_deals_by_brand(products)
    output_path = Path(args.output)
    write_products(best_deals, output_path)
    LOGGER.info(
        "Wrote %s best brand deals from %s unique products to %s",
        len(best_deals),
        len(products),
        output_path,
    )
    return 0


def _queries_from_legacy_categories(categories: list[str] | None) -> list[str]:
    if not categories:
        return []
    queries: list[str] = []
    for category in categories:
        normalized = category.lower()
        if "women" in normalized:
            queries.append("women")
        elif "men" in normalized:
            queries.append("men")
        elif "kids" in normalized or "toys" in normalized:
            queries.append("kids")
        elif "home" in normalized:
            queries.append("home")
        elif "clearance" in normalized:
            queries.append("clearance")
        else:
            queries.append(category)
    return queries


def _clean_taxonomy_label(value: Any) -> str | None:
    text = _safe_str(value)
    if not text:
        return None
    if ":" in text:
        return text.split(":", 1)[1].strip()
    return text


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any, *, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _deal_rank(item: Product) -> tuple[float, float, float]:
    return (
        item.discount_pct or -1.0,
        item.original_price or 0.0,
        -(item.sale_price or 0.0),
    )


if __name__ == "__main__":
    sys.exit(main())
