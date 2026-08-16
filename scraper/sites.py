"""Site adapters. Each one turns HTML into `Record`s and finds the next page.

Parsers take HTML strings (not clients), which is what makes them testable
against saved fixtures without touching the network.

Both targets are the official scraping sandboxes published for practice:
    https://books.toscrape.com  |  https://quotes.toscrape.com
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .http_client import PoliteClient
from .models import Record, clean_text

_PRICE = re.compile(r"([0-9]+(?:[.,][0-9]{2})?)")
_STOCK_COUNT = re.compile(r"(\d+)\s+available")
_RATING_WORDS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _soup(html: str) -> BeautifulSoup:
    # lxml is faster but adds a binary dependency; html.parser ships with Python.
    return BeautifulSoup(html, "html.parser")


def parse_price(raw: str) -> tuple[float | None, str]:
    """'£51.77' -> (51.77, 'GBP'). Unknown symbols return an empty currency."""
    text = clean_text(raw)
    if not text:
        return None, ""
    currency = {"£": "GBP", "$": "USD", "€": "EUR"}.get(text[:1], "")
    match = _PRICE.search(text.replace(",", "."))
    return (float(match.group(1)) if match else None), currency


class SiteScraper(ABC):
    """Contract every site adapter implements."""

    name: str
    base_url: str

    def start_url(self, client: PoliteClient, category: str | None) -> str:
        """Resolve the first URL to fetch. Override when a site needs a lookup."""
        return self.base_url

    @abstractmethod
    def parse(self, html: str, url: str, category: str = "") -> list[Record]:
        """Extract every item on one listing page."""

    def next_page(self, html: str, url: str) -> str | None:
        """Absolute URL of the next page, or None when pagination is exhausted."""
        link = _soup(html).select_one("li.next > a")
        return urljoin(url, link["href"]) if link and link.get("href") else None


class BooksToScrape(SiteScraper):
    """Catalogue scraper: title, price, star rating, stock count."""

    name = "books"
    base_url = "https://books.toscrape.com/"

    def start_url(self, client: PoliteClient, category: str | None) -> str:
        if not category:
            return self.base_url
        # The category slug is not guessable from the name alone (it carries a
        # numeric id), so read the sidebar once and match on the visible label.
        index = client.get(self.base_url).text
        wanted = category.strip().lower()
        for link in _soup(index).select("div.side_categories ul li ul li a"):
            label = clean_text(link.get_text())
            if label.lower() == wanted:
                return urljoin(self.base_url, link["href"])
        available = ", ".join(
            clean_text(a.get_text())
            for a in _soup(index).select("div.side_categories ul li ul li a")
        )
        raise SystemExit(f"Unknown category '{category}'. Available: {available}")

    def parse(self, html: str, url: str, category: str = "") -> list[Record]:
        page = _soup(html)
        page_category = clean_text(
            getattr(page.select_one("div.page-header h1"), "text", "")
        ) or category
        records: list[Record] = []
        for card in page.select("article.product_pod"):
            link = card.select_one("h3 a")
            if link is None:
                continue  # markup drifted - skip the card instead of crashing
            price, currency = parse_price(
                getattr(card.select_one("p.price_color"), "text", "")
            )
            rating_tag = card.select_one("p.star-rating")
            rating_word = rating_tag["class"][-1] if rating_tag else ""
            stock_text = clean_text(
                getattr(card.select_one("p.instock.availability"), "text", "")
            )
            stock_match = _STOCK_COUNT.search(stock_text)
            records.append(
                Record(
                    site=self.name,
                    category=page_category,
                    title=link.get("title") or link.get_text(),
                    url=urljoin(url, link["href"]),
                    price=price,
                    currency=currency,
                    rating=_RATING_WORDS.get(rating_word),
                    in_stock="in stock" in stock_text.lower(),
                    stock_count=int(stock_match.group(1)) if stock_match else None,
                    scraped_at=_now(),
                )
            )
        return records


class QuotesToScrape(SiteScraper):
    """Quote scraper: text, author, tags. Demonstrates list-valued fields."""

    name = "quotes"
    base_url = "https://quotes.toscrape.com/"

    def start_url(self, client: PoliteClient, category: str | None) -> str:
        # On this site a "category" is a tag: /tag/love/
        return urljoin(self.base_url, f"tag/{category.strip().lower()}/") if category else self.base_url

    def parse(self, html: str, url: str, category: str = "") -> list[Record]:
        records: list[Record] = []
        for block in _soup(html).select("div.quote"):
            text = clean_text(getattr(block.select_one("span.text"), "text", ""))
            if not text:
                continue
            author_link = block.select_one("a[href^='/author/']")
            records.append(
                Record(
                    site=self.name,
                    category=category,
                    title=text.strip("\u201c\u201d\""),
                    author=clean_text(getattr(block.select_one("small.author"), "text", "")),
                    url=urljoin(url, author_link["href"]) if author_link else url,
                    tags=[clean_text(t.get_text()) for t in block.select("a.tag")],
                    scraped_at=_now(),
                )
            )
        return records


SITES: dict[str, SiteScraper] = {
    BooksToScrape.name: BooksToScrape(),
    QuotesToScrape.name: QuotesToScrape(),
}
