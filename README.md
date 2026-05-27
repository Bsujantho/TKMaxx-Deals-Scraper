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
