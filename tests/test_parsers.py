"""Parser tests run against saved HTML fixtures - no network, fast, stable."""

from pathlib import Path

import pytest

from scraper.sites import SITES, parse_price

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_books_listing_is_parsed_into_records():
    html = load("books_listing.html")
    records = SITES["books"].parse(html, "https://books.toscrape.com/catalogue/category/books/travel_2/index.html")

    assert len(records) == 3
    first = records[0]
    assert first.site == "books"
    assert first.category == "Travel"
    assert first.title == "It's Only the Himalayas"   # curly quote normalised
    assert first.price == pytest.approx(45.17)
    assert first.currency == "GBP"
    assert first.rating == 2                          # "star-rating Two"
    assert first.in_stock is True
    assert first.url.startswith("https://books.toscrape.com/catalogue/")
    assert first.scraped_at.endswith("Z")


def test_quotes_listing_is_parsed_with_tags():
    html = load("quotes_listing.html")
    records = SITES["quotes"].parse(html, "https://quotes.toscrape.com/")

    assert len(records) == 3
    first = records[0]
    assert first.author == "Albert Einstein"
    assert "change" in first.tags
    assert not first.title.startswith("\u201c")       # smart quotes stripped
    assert first.url == "https://quotes.toscrape.com/author/Albert-Einstein"


@pytest.mark.parametrize(
    "site,fixture,expected",
    [
        ("books", "books_listing.html", "page-2.html"),
        ("quotes", "quotes_listing.html", "/page/2/"),
    ],
)
def test_next_page_is_resolved_to_absolute_url(site, fixture, expected):
    base = SITES[site].base_url
    next_url = SITES[site].next_page(load(fixture), base)
    assert next_url is not None and next_url.endswith(expected.lstrip("/"))
    assert next_url.startswith("https://")


def test_next_page_returns_none_without_pager():
    assert SITES["quotes"].next_page("<html><body>no pager</body></html>", "https://x/") is None


def test_parser_skips_malformed_cards_instead_of_raising():
    broken = "<article class='product_pod'><p class='price_color'>£10.00</p></article>"
    assert SITES["books"].parse(broken, "https://books.toscrape.com/") == []


@pytest.mark.parametrize(
    "raw,value,currency",
    [("£51.77", 51.77, "GBP"), ("$12.00", 12.00, "USD"), ("€9,50", 9.50, "EUR"), ("", None, "")],
)
def test_parse_price_handles_symbols_and_separators(raw, value, currency):
    parsed, cur = parse_price(raw)
    assert cur == currency
    assert parsed == value if value is None else parsed == pytest.approx(value)
