"""Data model for a single scraped row.

One flat dataclass instead of per-site classes: every site normalises into the
same shape, so the CSV schema stays stable no matter what we scrape next.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

# Collapse newlines / tabs / repeated spaces that HTML markup leaves behind.
_WHITESPACE = re.compile(r"\s+")

CSV_COLUMNS = [
    "site",
    "category",
    "title",
    "author",
    "price",
    "currency",
    "rating",
    "in_stock",
    "stock_count",
    "tags",
    "url",
    "scraped_at",
]


def clean_text(value: Any) -> str:
    """Strip markup whitespace and non-breaking spaces from a scraped string."""
    if value is None:
        return ""
    text = str(value).replace("\xa0", " ").replace("\u2018", "'").replace("\u2019", "'")
    return _WHITESPACE.sub(" ", text).strip()


@dataclass(slots=True)
class Record:
    """One normalised row. Unused fields stay empty rather than absent."""

    site: str
    url: str
    title: str = ""
    category: str = ""
    author: str = ""
    price: float | None = None
    currency: str = ""
    rating: int | None = None
    in_stock: bool | None = None
    stock_count: int | None = None
    tags: list[str] = field(default_factory=list)
    scraped_at: str = ""

    def __post_init__(self) -> None:
        self.title = clean_text(self.title)
        self.category = clean_text(self.category)
        self.author = clean_text(self.author)
        self.url = clean_text(self.url)
        self.tags = [clean_text(t) for t in self.tags if clean_text(t)]

    @property
    def dedupe_key(self) -> str:
        """Identity of a row: the canonical URL, or title+author when a site
        exposes the same item under several URLs (quotes.toscrape does)."""
        if self.title and self.author:
            return f"{self.site}|{self.title.lower()}|{self.author.lower()}"
        return f"{self.site}|{self.url.lower()}"

    def as_csv_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["tags"] = "; ".join(self.tags)
        row["price"] = "" if self.price is None else f"{self.price:.2f}"
        row["rating"] = "" if self.rating is None else self.rating
        row["in_stock"] = "" if self.in_stock is None else str(self.in_stock).lower()
        row["stock_count"] = "" if self.stock_count is None else self.stock_count
        return {column: row.get(column, "") for column in CSV_COLUMNS}
