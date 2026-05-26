# TK Maxx Best Deals Scraper

Selenium scraper for TK Maxx UK category pages. It scrolls each category page, extracts product tiles, computes percentage discounts from sale and original prices, and exports the best deal found for each brand.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Selenium Manager will normally locate or download the matching ChromeDriver automatically. You need Google Chrome installed.

## Run

```powershell
python tkmaxx_deals.py --output tkmaxx_best_deals.xlsx
```

The scraper defaults to visible Chrome because TK Maxx currently serves an error page to headless Chrome in some environments.

For a faster smoke test:

```powershell
python tkmaxx_deals.py --max-products-per-category 10 --output smoke_test.csv
```

Useful options:

- `--category URL` can be repeated to scrape specific TK Maxx category pages.
- `--headless` runs without opening a browser window, if TK Maxx allows headless access from your environment.
- `--output results.csv` writes CSV instead of Excel.
- `--timeout`, `--scroll-pause`, `--max-scrolls`, and `--page-attempts` tune lazy-loading and retry behavior.

## Default Categories

- Women view all
- Men view all
- Kids, baby, and toys view all
- Home view all
- Clearance view all

## Notes

The scraper is intentionally conservative: it uses normal browser automation, waits between lazy-load scrolls, and skips tiles it cannot parse cleanly. Review TK Maxx's terms and robots guidance before running large or frequent scrapes.

If TK Maxx changes its markup, run with `--headful --log-level DEBUG` and update the selector lists in `tkmaxx_deals.py`.
