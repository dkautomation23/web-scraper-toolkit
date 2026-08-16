"""Polite HTTP layer: retries with exponential backoff, UA rotation, delays.

Everything that makes a scraper survive the real internet lives here, so the
site parsers stay pure functions over HTML.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass

import requests
from requests import Response

log = logging.getLogger(__name__)

# A handful of real desktop UA strings. Rotating them spreads the fingerprint
# without pretending to be a browser we are not (no headless-browser tricks).
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
]

# Codes worth retrying: transient rate limits and upstream/proxy hiccups.
RETRY_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


class FetchError(RuntimeError):
    """Raised when a URL could not be fetched after every retry."""


@dataclass(slots=True)
class FetchStats:
    """Counters printed at the end of a run - cheap observability."""

    requests: int = 0
    retries: int = 0
    failures: int = 0


class PoliteClient:
    """A requests.Session wrapper that waits, retries and rotates UA strings.

    Args:
        delay: base pause between requests, in seconds.
        jitter: random extra pause (0..jitter) so requests are not metronomic.
        max_retries: attempts after the first failure.
        backoff: multiplier for the exponential backoff (1s, 2s, 4s at 2.0).
        timeout: per-request timeout in seconds.
    """

    def __init__(
        self,
        delay: float = 1.0,
        jitter: float = 0.4,
        max_retries: int = 3,
        backoff: float = 2.0,
        timeout: float = 20.0,
        session: requests.Session | None = None,
    ) -> None:
        self.delay = max(0.0, delay)
        self.jitter = max(0.0, jitter)
        self.max_retries = max(0, max_retries)
        self.backoff = backoff
        self.timeout = timeout
        self.session = session or requests.Session()
        self.stats = FetchStats()
        self._last_request_at = 0.0

    # -- internals ---------------------------------------------------------

    def _wait_turn(self) -> None:
        """Sleep so that at least `delay` seconds passed since the last call."""
        if self.delay <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        pause = self.delay - elapsed + random.uniform(0, self.jitter)
        if pause > 0:
            time.sleep(pause)

    def _retry_pause(self, attempt: int, response: Response | None) -> float:
        """Honour Retry-After when the server sends it, else exponential backoff."""
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                return float(retry_after)
        return (self.backoff ** attempt) + random.uniform(0, 0.5)

    # -- public API --------------------------------------------------------

    def get(self, url: str, **kwargs) -> Response:
        """GET a URL, retrying transient failures. Raises FetchError at the end."""
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        headers.update(kwargs.pop("headers", {}))

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self._wait_turn()
            response = None
            try:
                self.stats.requests += 1
                response = self.session.get(
                    url, headers=headers, timeout=self.timeout, **kwargs
                )
                self._last_request_at = time.monotonic()
                if response.status_code in RETRY_STATUS:
                    raise requests.HTTPError(
                        f"HTTP {response.status_code}", response=response
                    )
                response.raise_for_status()
                # Many sites omit charset in Content-Type; requests then falls
                # back to ISO-8859-1 and mangles UTF-8 text ("Noah’s" -> "Noahâs").
                content_type = response.headers.get("Content-Type", "").lower()
                if "charset" not in content_type:
                    response.encoding = response.apparent_encoding or "utf-8"
                return response
            except requests.RequestException as exc:
                last_error = exc
                self._last_request_at = time.monotonic()
                status = getattr(exc.response, "status_code", None)
                # 4xx other than the retryable ones will never succeed - stop now.
                if status is not None and status not in RETRY_STATUS:
                    break
                if attempt == self.max_retries:
                    break
                pause = self._retry_pause(attempt, response)
                self.stats.retries += 1
                log.warning(
                    "fetch failed (%s), retry %s/%s in %.1fs: %s",
                    status or type(exc).__name__,
                    attempt + 1,
                    self.max_retries,
                    pause,
                    url,
                )
                time.sleep(pause)

        self.stats.failures += 1
        raise FetchError(f"GET {url} failed: {last_error}") from last_error

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "PoliteClient":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()
