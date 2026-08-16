"""Post-processing: deduplicate records and write a clean CSV.

Kept separate from crawling so the same rows can be reused by another sink
(database, Google Sheets, API) without touching the scraper.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Iterable

from .models import CSV_COLUMNS, Record

log = logging.getLogger(__name__)


def dedupe(records: Iterable[Record]) -> list[Record]:
    """Drop repeats by `Record.dedupe_key`, keeping the first occurrence.

    Pagination overlaps and re-runs are the usual sources of duplicates.
    """
    seen: set[str] = set()
    unique: list[Record] = []
    for record in records:
        key = record.dedupe_key
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique


def write_csv(records: Iterable[Record], path: str | Path) -> Path:
    """Write records to UTF-8 CSV (BOM included so Excel opens it correctly)."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [record.as_csv_row() for record in records]
    with out_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    log.info("wrote %s rows -> %s", len(rows), out_path)
    return out_path
