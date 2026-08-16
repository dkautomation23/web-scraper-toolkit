"""Deduplication + CSV writing."""

import csv

from scraper.models import CSV_COLUMNS, Record
from scraper.pipeline import dedupe, write_csv


def book(title: str, url: str) -> Record:
    return Record(site="books", title=title, url=url, price=10.0, currency="GBP")


def test_dedupe_keeps_first_occurrence_of_a_repeated_url():
    # Same URL = same product, even if the listing title differs slightly.
    rows = [book("A", "https://x/a"), book("B", "https://x/b"), book("A (reprint)", "https://x/a")]
    assert [r.title for r in dedupe(rows)] == ["A", "B"]

    same_url_other_case = [book("A", "https://x/a"), book("A", "https://X/A")]
    assert len(dedupe(same_url_other_case)) == 1               # key is case-insensitive


def test_dedupe_uses_title_and_author_when_present():
    quote = lambda url: Record(site="quotes", title="Be yourself", author="Oscar Wilde", url=url)
    assert len(dedupe([quote("https://x/1"), quote("https://x/2")])) == 1


def test_record_normalises_whitespace_and_nbsp():
    record = Record(site="books", title="  Two\n\tspaces\xa0here ", url=" https://x/a ")
    assert record.title == "Two spaces here"
    assert record.url == "https://x/a"


def test_write_csv_produces_expected_header_and_types(tmp_path):
    out = write_csv([book("A", "https://x/a")], tmp_path / "nested" / "out.csv")
    assert out.exists()

    with out.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert list(rows[0]) == CSV_COLUMNS
    assert rows[0]["price"] == "10.00"      # always 2 decimals
    assert rows[0]["rating"] == ""          # unknown stays empty, never "None"
    assert rows[0]["in_stock"] == ""


def test_tags_are_joined_for_csv():
    record = Record(site="quotes", title="t", url="u", tags=["a", "b"])
    assert record.as_csv_row()["tags"] == "a; b"
