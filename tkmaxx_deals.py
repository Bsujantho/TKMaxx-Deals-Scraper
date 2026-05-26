from __future__ import annotations

import argparse
import csv
import logging
import re
import sys
import time
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Iterable


LOGGER = logging.getLogger("tkmaxx_deals")

DEFAULT_CATEGORIES = [
    "https://www.tkmaxx.com/uk/en/women/women-view-all/c/01000001",
    "https://www.tkmaxx.com/uk/en/men/men-view-all/c/02000001",
    "https://www.tkmaxx.com/uk/en/kids%2Btoys/kids-baby%2Btoys-view-all/c/03000001",
    "https://www.tkmaxx.com/uk/en/home/home/c/04000001",
    "https://www.tkmaxx.com/uk/en/clearance/view-all-clearance/c/05010001",
]

PRICE_RE = re.compile(r"\u00a3\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)")

PRODUCT_TILE_SELECTORS = [
    "a.c-product-card",
    "li.c-product-grid__item",
    "article",
    "li[class*='product' i]",
    "[class*='product-grid__item' i]",
    "div[class*='product-tile' i]",
    "div[class*='productTile' i]",
    "div[class*='product-card' i]",
    "div[class*='productCard' i]",
    "[data-testid*='product' i]",
    "[data-test*='product' i]",
]

BRAND_SELECTORS = [
    "[data-testid*='brand' i]",
    "[data-test*='brand' i]",
    ".product-brand",
    "[class*='brand' i]",
]

NAME_SELECTORS = [
    "[data-testid*='name' i]",
    "[data-test*='name' i]",
    ".product-name",
    "[class*='name' i]",
    "a[title]",
]

PRICE_SELECTORS = [
    "[data-testid*='price' i]",
    "[data-test*='price' i]",
    ".product-price",
    "[class*='price' i]",
]

COOKIE_BUTTON_SELECTORS = [
    "#onetrust-accept-btn-handler",
    "button[id*='accept' i]",
    "button[aria-label*='accept' i]",
]


@dataclass(slots=True)
class Product:
    brand: str
    name: str
    sale_price: float | None
    original_price: float | None
    discount_pct: float | None
    url: str
    category_url: str


def parse_prices(text: str) -> tuple[float | None, float | None]:
    """
    Extract sale and original prices from a TK Maxx price string.

    Common examples include "RRP GBP100 GBP39.99" and "GBP24.99".
    In the source text those GBP examples are the pound sign. If multiple
    prices exist, the scraper treats the first as the original price and the
    last as the sale price, then corrects obviously reversed values.
    """
    amounts = [float(match.replace(",", "")) for match in PRICE_RE.findall(text)]
    if not amounts:
        return None, None
    if len(amounts) == 1:
        return amounts[0], None

    original = amounts[0]
    sale = amounts[-1]
    if original < sale:
        sale = min(amounts)
        original = max(amounts)
    return sale, original


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


def build_driver(headless: bool) -> Any:
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError as exc:
        raise SystemExit(
            "Selenium is required to scrape TK Maxx. Install dependencies with "
            "`pip install -r requirements.txt`."
        ) from exc

    chrome_opts = Options()
    if headless:
        chrome_opts.add_argument("--headless=new")
    chrome_opts.add_argument("--window-size=1440,1600")
    chrome_opts.add_argument("--disable-dev-shm-usage")
    chrome_opts.add_argument("--no-sandbox")
    chrome_opts.add_argument("--log-level=3")
    return webdriver.Chrome(options=chrome_opts)


def scrape_category(
    driver: Any,
    url: str,
    *,
    timeout: float,
    scroll_pause: float,
    max_scrolls: int,
    page_attempts: int,
    max_products: int | None = None,
) -> list[Product]:
    """Load one category page, scroll lazy content into view, and parse products."""
    for attempt in range(1, page_attempts + 1):
        driver.get(url)
        time.sleep(1.0)
        accept_cookie_banner(driver)
        try:
            wait_for_candidate_tiles(driver, timeout=timeout)
            break
        except RuntimeError:
            if attempt >= page_attempts:
                raise
            LOGGER.warning(
                "TK Maxx returned an error page for %s; retrying (%s/%s)",
                url,
                attempt,
                page_attempts,
            )
            time.sleep(2.0 * attempt)

    scroll_through_page(driver, pause=scroll_pause, max_scrolls=max_scrolls)

    products: list[Product] = []
    seen_urls: set[str] = set()
    for tile in find_candidate_tiles(driver):
        product = parse_product_tile(tile, category_url=url)
        if product is None or product.url in seen_urls:
            continue
        seen_urls.add(product.url)
        products.append(product)
        if max_products is not None and len(products) >= max_products:
            break
    return products


def accept_cookie_banner(driver: Any) -> None:
    from selenium.webdriver.common.by import By

    for selector in COOKIE_BUTTON_SELECTORS:
        for button in driver.find_elements(By.CSS_SELECTOR, selector):
            try:
                if button.is_displayed() and button.is_enabled():
                    button.click()
                    time.sleep(0.5)
                    return
            except Exception:
                continue


def wait_for_candidate_tiles(driver: Any, *, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_tkmaxx_error_page(driver):
            raise RuntimeError(
                "TK Maxx returned its 'Something went wrong' page. Retry later; "
                "if you used --headless, run again without it."
            )
        if find_candidate_tiles(driver):
            return
        time.sleep(0.5)
    LOGGER.warning("No product tiles found before timeout on %s", driver.current_url)


def is_tkmaxx_error_page(driver: Any) -> bool:
    from selenium.webdriver.common.by import By

    try:
        body_text = " ".join(
            normalized_text(driver.find_element(By.TAG_NAME, "body")).lower().split()
        )
    except Exception:
        return False
    return "something went wrong" in body_text and "shop tkmaxx online" in body_text


def scroll_through_page(driver: Any, *, pause: float, max_scrolls: int) -> None:
    last_height = 0
    last_count = 0
    stable_rounds = 0

    for _ in range(max_scrolls):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause)
        height = int(driver.execute_script("return document.body.scrollHeight") or 0)
        count = len(find_candidate_tiles(driver))

        if height == last_height and count == last_count:
            stable_rounds += 1
            if stable_rounds >= 2:
                break
        else:
            stable_rounds = 0

        last_height = height
        last_count = count


def find_candidate_tiles(driver: Any) -> list[Any]:
    from selenium.webdriver.common.by import By

    candidates: list[Any] = []
    seen_ids: set[str] = set()
    for selector in PRODUCT_TILE_SELECTORS:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            continue
        for element in elements:
            element_id = getattr(element, "id", "")
            if element_id in seen_ids or not looks_like_product_tile(element):
                continue
            seen_ids.add(element_id)
            candidates.append(element)
    return candidates


def looks_like_product_tile(element: Any) -> bool:
    text = normalized_text(element)
    if "\u00a3" not in text:
        return False
    return first_product_link(element) is not None


def parse_product_tile(tile: Any, *, category_url: str) -> Product | None:
    price_text = extract_first_text(tile, PRICE_SELECTORS) or normalized_text(tile)
    sale_price, original_price = parse_prices(price_text)
    if sale_price is None:
        return None

    url = first_product_link(tile)
    if not url:
        return None

    brand = extract_first_text(tile, BRAND_SELECTORS)
    name = extract_first_text(tile, NAME_SELECTORS)
    fallback_brand, fallback_name = infer_brand_and_name_from_tile(tile)
    brand = brand or fallback_brand
    name = name or fallback_name

    if not brand or not name:
        return None

    return Product(
        brand=brand,
        name=name,
        sale_price=sale_price,
        original_price=original_price,
        discount_pct=compute_discount(sale_price, original_price),
        url=url,
        category_url=category_url,
    )


def extract_first_text(element: Any, selectors: list[str]) -> str | None:
    from selenium.webdriver.common.by import By

    for selector in selectors:
        try:
            children = element.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            continue
        for child in children:
            text = normalized_text(child) or child.get_attribute("title") or ""
            text = " ".join(text.split())
            if text and "\u00a3" not in text:
                return text
    return None


def infer_brand_and_name_from_tile(tile: Any) -> tuple[str | None, str | None]:
    lines = [
        " ".join(line.split())
        for line in normalized_text(tile).splitlines()
        if line.strip()
    ]
    non_price_lines = [
        line
        for line in lines
        if "\u00a3" not in line and line.lower() not in {"quick view", "add to bag"}
    ]
    if not non_price_lines:
        return None, None
    if len(non_price_lines) == 1:
        return non_price_lines[0], non_price_lines[0]
    return non_price_lines[0], non_price_lines[1]


def first_product_link(element: Any) -> str | None:
    from selenium.webdriver.common.by import By

    if getattr(element, "tag_name", "").lower() == "a":
        href = element.get_attribute("href")
        if href and not href.startswith(("javascript:", "#")):
            return href

    fallback: str | None = None
    for link in element.find_elements(By.CSS_SELECTOR, "a[href]"):
        href = link.get_attribute("href")
        if not href or href.startswith(("javascript:", "#")):
            continue
        if "/p/" in href:
            return href
        if fallback is None and "tkmaxx.com/uk/en/" in href:
            fallback = href
    return fallback


def normalized_text(element: Any) -> str:
    return (getattr(element, "text", "") or "").strip()


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
        description="Scrape TK Maxx UK category pages and export the best discount per brand."
    )
    parser.add_argument(
        "--category",
        action="append",
        dest="categories",
        help="Category URL to scrape. Repeat to add multiple categories.",
    )
    parser.add_argument(
        "--output",
        default="tkmaxx_best_deals.xlsx",
        help="Output file path. Use .xlsx or .csv.",
    )
    browser_group = parser.add_mutually_exclusive_group()
    browser_group.add_argument(
        "--headless",
        action="store_true",
        help="Run Chrome headless. TK Maxx may serve an error page in this mode.",
    )
    browser_group.add_argument(
        "--headful",
        action="store_false",
        dest="headless",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--max-products-per-category",
        type=int,
        default=None,
        help="Optional cap for faster test runs.",
    )
    parser.add_argument(
        "--max-scrolls",
        type=int,
        default=30,
        help="Maximum lazy-load scroll attempts per category.",
    )
    parser.add_argument(
        "--scroll-pause",
        type=float,
        default=1.5,
        help="Seconds to wait after each scroll.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="Seconds to wait for product tiles after opening each page.",
    )
    parser.add_argument(
        "--page-attempts",
        type=int,
        default=3,
        help="Number of attempts per category when TK Maxx returns a transient error page.",
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

    categories = args.categories or DEFAULT_CATEGORIES
    driver = build_driver(headless=args.headless)

    collected: list[Product] = []
    try:
        for category_url in categories:
            LOGGER.info("Scraping %s", category_url)
            try:
                products = scrape_category(
                    driver,
                    category_url,
                    timeout=args.timeout,
                    scroll_pause=args.scroll_pause,
                    max_scrolls=args.max_scrolls,
                    page_attempts=args.page_attempts,
                    max_products=args.max_products_per_category,
                )
            except Exception:
                LOGGER.exception("Failed to scrape %s", category_url)
                continue
            LOGGER.info("Found %s products", len(products))
            collected.extend(products)
    finally:
        driver.quit()

    best_deals = find_best_deals_by_brand(collected)
    output_path = Path(args.output)
    write_products(best_deals, output_path)
    LOGGER.info("Wrote %s best deals to %s", len(best_deals), output_path)
    return 0


def _deal_rank(item: Product) -> tuple[float, float, float]:
    return (
        item.discount_pct or -1.0,
        item.original_price or 0.0,
        -(item.sale_price or 0.0),
    )


if __name__ == "__main__":
    sys.exit(main())
