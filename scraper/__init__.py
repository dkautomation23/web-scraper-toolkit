"""web-scraper-toolkit: a small, production-shaped scraping CLI.

Public surface is intentionally tiny: build a `Spider` for a registered site,
run it, and hand the records to `write_csv`.
"""

__version__ = "0.1.0"

from .models import Record
from .pipeline import dedupe, write_csv

__all__ = ["Record", "dedupe", "write_csv", "__version__"]
