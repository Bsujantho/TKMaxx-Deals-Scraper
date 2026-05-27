# TK Maxx Best Deals Scraper

TK Maxx UK deal scraper that uses the site's Bloomreach product index instead of browser automation. It searches a set of TK Maxx queries, reads product price/RRP data, computes percentage discounts, and exports the best deal found for each brand.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```powershell
python tkmaxx_deals.py --output tkmaxx_best_deals.xlsx
```

For a faster smoke test:

```powershell
python tkmaxx_deals.py --query gucci --max-products-per-query 10 --output smoke_test.csv
```

Useful options:

- `--query TERM` can be repeated to scrape specific searches.
- `--output results.csv` writes CSV instead of Excel.
- `--rows-per-page`, `--max-pages`, `--max-products-per-query`, and `--request-delay` tune API pagination.

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

The exported spreadsheet is not a dump of every product found. The scraper collects products from the selected queries, then keeps the single best discounted item for each brand. That means the final Excel file can have far fewer rows than the number of products scraped.

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
