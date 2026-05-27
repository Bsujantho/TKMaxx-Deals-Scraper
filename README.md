# TK Maxx Deals Scraper

TK Maxx UK deal scraper that uses the site's Bloomreach product index instead of browser automation. It searches a set of TK Maxx queries, reads product price/RRP data, computes percentage discounts, and exports product deal data.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```powershell
python tkmaxx_deals.py --output tkmaxx_deals.xlsx
```

For a faster smoke test:

```powershell
python tkmaxx_deals.py --query gucci --max-products-per-query 10 --output smoke_test.csv
```

Useful options:

- `--query TERM` can be repeated to scrape specific searches.
- `--output results.csv` writes CSV instead of Excel.
- `--export-mode all` exports every unique product found. This is the default.
- `--export-mode best-by-brand` exports only the highest-discounted product for each brand.
- `--rows-per-page`, `--max-pages`, `--max-products-per-query`, and `--request-delay` tune API pagination.

## Export Modes

The default export now writes every unique product found:

```powershell
python tkmaxx_deals.py --query men --max-pages 30 --export-mode all
```

If the log says `Found 3000 products for 'men'`, this mode writes those 3,000 unique products to the spreadsheet.

To create the smaller summary that keeps only one best discounted item per brand, run:

```powershell
python tkmaxx_deals.py --query men --max-pages 30 --export-mode best-by-brand --output tkmaxx_best_deals.xlsx
```

In best-by-brand mode, a log like `Wrote 456 best brand deals from 3000 unique products` means the scraper found 3,000 products but grouped them by brand and kept only the top discounted item from each brand.

## Product Limits

By default, the scraper reads up to 500 products per query:

```text
100 rows per page * 5 pages = 500 products
```

That is a safety cap set by this script, not a hard TK Maxx limit. Increase `--max-pages` to fetch more products:

```powershell
python tkmaxx_deals.py --max-pages 20
```

That reads up to 2,000 products per query. To keep paging until the API has no more results, use:

```powershell
python tkmaxx_deals.py --max-pages 0
```

You can also use `--max-products-per-query` when you want a smaller fixed cap for testing:

```powershell
python tkmaxx_deals.py --query gucci --max-products-per-query 50
```

The number of rows in the exported spreadsheet also depends on `--export-mode`. Use `--export-mode all` when you want every product, and `--export-mode best-by-brand` when you want one deal per brand.

## Default Queries

- women
- men
- kids
- toys
- home
- beauty
- clearance
- shoes
- designer

## Notes

The previous Selenium approach can hit TK Maxx's "Something went wrong" fallback page. This version avoids that broken browser route and reads product data from Bloomreach, the search index used by the TK Maxx frontend.

Review TK Maxx's terms before running large or frequent scrapes.
