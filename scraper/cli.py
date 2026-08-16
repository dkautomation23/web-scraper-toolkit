"""Command-line entry point: crawl a site, deduplicate, write CSV.

    python -m scraper --site books --category Travel --max-pages 3 --out out.csv
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time

from dotenv import load_dotenv

from .http_client import FetchError, PoliteClient
from .models import Record
from .pipeline import dedupe, write_csv
from .sites import SITES


def _env(name: str, default):
    """Read a default from the environment, falling back to the hard-coded one."""
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return type(default)(raw) if isinstance(default, (int, float)) else raw


def build_parser() -> argparse.ArgumentParser:
    load_dotenv()  # optional .env next to the project - see .env.example
    parser = argparse.ArgumentParser(
        prog="scraper",
        description="Scrape a paginated listing into a clean, deduplicated CSV.",
        epilog="Example: python -m scraper --site books --category Travel --out books.csv",
    )
    parser.add_argument(
        "--site", choices=sorted(SITES), required=True, help="which site adapter to use"
    )
    parser.add_argument(
        "--category",
        help="books: sidebar category name (e.g. Travel); quotes: tag (e.g. love)",
    )
    parser.add_argument("--url", help="start URL, overrides --site/--category defaults")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=_env("SCRAPER_MAX_PAGES", 5),
        help="pagination limit (default: 5)",
    )
    parser.add_argument(
        "--max-items", type=int, default=0, help="stop after N items (0 = no limit)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=_env("SCRAPER_DELAY", 1.0),
        help="seconds between requests (default: 1.0)",
    )
    parser.add_argument(
        "--retries", type=int, default=3, help="retries per URL (default: 3)"
    )
    parser.add_argument(
        "--out",
        default=_env("SCRAPER_OUTPUT", "output.csv"),
        help="CSV path (default: output.csv)",
    )
    parser.add_argument("--verbose", action="store_true", help="log every page fetched")
    return parser


def crawl(args: argparse.Namespace) -> list[Record]:
    """Walk pages until the limit is reached or pagination ends."""
    site = SITES[args.site]
    records: list[Record] = []

    proxy = os.getenv("SCRAPER_PROXY")  # e.g. http://user:pass@host:port
    with PoliteClient(delay=args.delay, max_retries=args.retries) as client:
        if proxy:
            client.session.proxies.update({"http": proxy, "https": proxy})
        url = args.url or site.start_url(client, args.category)
        for page_number in range(1, args.max_pages + 1):
            if not url:
                break
            try:
                response = client.get(url)
            except FetchError as exc:
                # A dead page mid-crawl must not throw away what we already have.
                logging.error("%s - stopping crawl, keeping %s rows", exc, len(records))
                break
            found = site.parse(response.text, url, category=args.category or "")
            records.extend(found)
            logging.info("page %s: %s items (%s)", page_number, len(found), url)
            if args.max_items and len(records) >= args.max_items:
                records = records[: args.max_items]
                break
            url = site.next_page(response.text, url)

        logging.info(
            "requests=%s retries=%s failures=%s",
            client.stats.requests,
            client.stats.retries,
            client.stats.failures,
        )
    return records


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )

    started = time.monotonic()
    records = crawl(args)
    unique = dedupe(records)
    out_path = write_csv(unique, args.out)

    print(
        f"{len(unique)} rows -> {out_path} "
        f"({len(records) - len(unique)} duplicates removed, "
        f"{time.monotonic() - started:.1f}s)"
    )
    return 0 if unique else 1


if __name__ == "__main__":
    sys.exit(main())
