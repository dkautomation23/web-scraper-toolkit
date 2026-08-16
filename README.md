# web-scraper-toolkit

Sample project demonstrating production web-scraping / automation patterns.

A small command-line scraper that turns a paginated listing into a clean,
deduplicated CSV. It is built the way a paid scraping job is built: polite
request pacing, retries with exponential backoff, user-agent rotation, field
normalisation, deduplication, and tests that run without touching the network.

Targets are the two public sandboxes published for scraping practice —
[books.toscrape.com](https://books.toscrape.com) and
[quotes.toscrape.com](https://quotes.toscrape.com).

---

## What it does

| Concern | How it is handled |
| --- | --- |
| Rate limiting | Fixed delay + random jitter between requests (`--delay`) |
| Transient failures | Retries `408/425/429/5xx` with exponential backoff, honours `Retry-After` |
| Permanent failures | `404`/`403` fail fast — no wasted retries |
| Blocking | User-agent rotation, optional proxy via `SCRAPER_PROXY` |
| Pagination | Follows `li.next > a` until the page limit is reached |
| Broken markup | A malformed card is skipped and logged, the crawl continues |
| Encoding | Detects charset when the server omits it (fixes `Noahâs` → `Noah's`) |
| Duplicates | Keyed on canonical URL, or `title + author` where a site repeats items |
| Output | UTF-8 CSV with a BOM so Excel opens it correctly, fixed column order |

## Install

```bash
git clone https://github.com/dkautomation23/web-scraper-toolkit.git
cd web-scraper-toolkit
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                              # optional, all values have defaults
```

Python 3.10+.

## Usage

```bash
# Books in one catalogue category -> CSV
python -m scraper --site books --category Travel --max-pages 3 --out books_travel.csv

# Quotes, 5 pages, one request per second, verbose logging
python -m scraper --site quotes --max-pages 5 --delay 1.0 --out quotes.csv --verbose

# Quotes filtered by tag, capped at 20 items
python -m scraper --site quotes --category love --max-items 20 --out love.csv

# Any start URL, bypassing the site defaults
python -m scraper --site books --url https://books.toscrape.com/catalogue/page-2.html --out page2.csv
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--site` | required | `books` or `quotes` |
| `--category` | – | books: sidebar category (`Travel`); quotes: tag (`love`) |
| `--url` | – | explicit start URL, overrides `--site`/`--category` |
| `--max-pages` | `5` | pagination limit |
| `--max-items` | `0` | stop after N rows (0 = no limit) |
| `--delay` | `1.0` | seconds between requests |
| `--retries` | `3` | retries per URL |
| `--out` | `output.csv` | CSV destination |
| `--verbose` | off | log every page and the request/retry counters |

Defaults can also come from `.env` (`SCRAPER_DELAY`, `SCRAPER_MAX_PAGES`,
`SCRAPER_OUTPUT`, `SCRAPER_PROXY`). No credentials are needed or stored.

## Example run

```console
$ python -m scraper --site quotes --max-pages 5 --delay 1.0 --out sample_output/quotes.csv --verbose
INFO page 1: 10 items (https://quotes.toscrape.com/)
INFO page 2: 10 items (https://quotes.toscrape.com/page/2/)
INFO page 3: 10 items (https://quotes.toscrape.com/page/3/)
INFO page 4: 10 items (https://quotes.toscrape.com/page/4/)
INFO page 5: 10 items (https://quotes.toscrape.com/page/5/)
INFO requests=5 retries=0 failures=0
50 rows -> sample_output/quotes.csv (0 duplicates removed, 5.8s)
```

Output (`sample_output/books_travel.csv`, first rows):

```csv
site,category,title,author,price,currency,rating,in_stock,stock_count,tags,url,scraped_at
books,Travel,It's Only the Himalayas,,45.17,GBP,2,true,,,https://books.toscrape.com/catalogue/its-only-the-himalayas_981/index.html,2026-08-16T06:51:57Z
books,Travel,Full Moon over Noah's Ark: An Odyssey to Mount Ararat and Beyond,,49.43,GBP,4,true,,,https://books.toscrape.com/catalogue/full-moon-over-noahs-ark-an-odyssey-to-mount-ararat-and-beyond_811/index.html,2026-08-16T06:51:57Z
```

Committed samples: `sample_output/books_travel.csv` (11 rows),
`sample_output/quotes.csv` (50 rows).

## Project layout

```
scraper/
  cli.py           argparse CLI + crawl loop (pagination, limits, stats)
  http_client.py   polite session: delays, retries/backoff, UA rotation, proxy
  sites.py         one adapter per site: HTML -> Record, and next-page lookup
  models.py        Record dataclass, field normalisation, CSV schema
  pipeline.py      deduplication + CSV writer
tests/
  fixtures/        saved HTML pages used by the parser tests
  test_parsers.py  parsing, pagination, malformed markup, price/currency
  test_pipeline.py deduplication, normalisation, CSV shape
  test_http_client.py retry/backoff/Retry-After behaviour with a fake session
sample_output/     CSVs produced by real runs
```

## Adding a site

Subclass `SiteScraper`, implement `parse()`, register it in `SITES` — the CLI,
retries, deduplication and CSV writing are reused unchanged:

```python
class MyShop(SiteScraper):
    name = "myshop"
    base_url = "https://example.com/catalog/"

    def parse(self, html, url, category=""):
        return [Record(site=self.name, title=..., url=..., price=...) ]
```

## Tests

```bash
pytest -q
```

```console
.....................                                                    [100%]
21 passed in 0.26s
```

Parser tests run against saved fixtures and the HTTP tests use a fake session,
so the suite is deterministic and needs no network access.

## Scope and etiquette

Public data only, one request at a time, delays on by default. Both target
sites exist specifically for scraping practice. For real projects: check
`robots.txt` and the site's terms first, and prefer an official API when one
exists.

## License

MIT — see [LICENSE](LICENSE).
