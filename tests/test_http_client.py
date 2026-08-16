"""Retry/backoff behaviour, exercised with a fake session (no network, no sleep)."""

import pytest
import requests

from scraper.http_client import FetchError, PoliteClient


class FakeResponse:
    def __init__(self, status_code=200, text="ok", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


class FakeSession:
    """Returns queued responses (or raises queued exceptions) in order."""

    def __init__(self, queue):
        self.queue = list(queue)
        self.calls = 0

    def get(self, url, **kwargs):
        self.calls += 1
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def close(self):
        pass


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("scraper.http_client.time.sleep", lambda _s: None)


def client(queue, **kwargs):
    return PoliteClient(delay=0, session=FakeSession(queue), **kwargs)


def test_transient_500_is_retried_then_succeeds():
    c = client([FakeResponse(500), FakeResponse(503), FakeResponse(200, "done")])
    assert c.get("https://x/").text == "done"
    assert c.session.calls == 3
    assert c.stats.retries == 2


def test_connection_error_is_retried():
    c = client([requests.ConnectionError("boom"), FakeResponse(200)])
    assert c.get("https://x/").status_code == 200
    assert c.stats.retries == 1


def test_404_is_not_retried():
    c = client([FakeResponse(404)], max_retries=3)
    with pytest.raises(FetchError):
        c.get("https://x/")
    assert c.session.calls == 1          # permanent error - one attempt only


def test_gives_up_after_max_retries_and_counts_failure():
    c = client([FakeResponse(503)] * 4, max_retries=3)
    with pytest.raises(FetchError):
        c.get("https://x/")
    assert c.session.calls == 4          # first try + 3 retries
    assert c.stats.failures == 1


def test_retry_after_header_is_respected(monkeypatch):
    pauses = []
    monkeypatch.setattr("scraper.http_client.time.sleep", pauses.append)
    c = client([FakeResponse(429, headers={"Retry-After": "7"}), FakeResponse(200)])
    c.get("https://x/")
    assert pauses == [7.0]


def test_user_agent_is_sent_and_rotates():
    seen = []

    class RecordingSession(FakeSession):
        def get(self, url, **kwargs):
            seen.append(kwargs["headers"]["User-Agent"])
            return super().get(url, **kwargs)

    c = PoliteClient(delay=0, session=RecordingSession([FakeResponse()] * 20))
    for _ in range(20):
        c.get("https://x/")
    assert all(ua.startswith("Mozilla/5.0") for ua in seen)
    assert len(set(seen)) > 1            # rotation actually happens
