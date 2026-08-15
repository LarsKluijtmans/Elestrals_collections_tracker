"""The outbound layer: pacing, identity, and the two refusals that keep it on its own host.

These are the NFRs under "Security & Conduct" — allowlisted hosts, an honest user agent, a
conservative per-source rate — asserted rather than described. The rate limiter is tested with
an injected clock because a rate limiter tested by actually sleeping is a rate limiter tested
once and then skipped for being slow.
"""
from __future__ import annotations

import httpx
import pytest

from app.harvest.http import OffHostRequest, PoliteClient, SourceUnavailable, build_user_agent
from app.harvest.rate_limit import TokenBucket


class FakeClock:
    """A clock that only moves when something sleeps."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


# --- pacing ---------------------------------------------------------------------------

def test_a_full_bucket_does_not_wait():
    clock = FakeClock()
    bucket = TokenBucket(per_minute=60, clock=clock, sleep=clock.sleep)

    assert bucket.acquire() == 0.0


def test_an_empty_bucket_waits_for_exactly_one_token():
    """60/min is one per second, so the second request against a bucket of one waits a
    second — not a whole minute, and not nothing."""
    clock = FakeClock()
    bucket = TokenBucket(per_minute=60, capacity=1, clock=clock, sleep=clock.sleep)

    bucket.acquire()
    assert bucket.acquire() == pytest.approx(1.0)


def test_the_bucket_refills_continuously_rather_than_in_batches():
    """A bucket that refilled on the minute would let a full minute's budget leave at once
    and then stall — the traffic shape that gets a key throttled despite a legal average."""
    clock = FakeClock()
    bucket = TokenBucket(per_minute=60, capacity=2, clock=clock, sleep=clock.sleep)
    bucket.acquire()
    bucket.acquire()

    clock.now += 1.0  # one second of real time, one token back
    assert bucket.acquire() == 0.0


def test_a_zero_rate_is_a_configuration_error_not_a_stopped_source():
    with pytest.raises(ValueError, match="enabled = 0"):
        TokenBucket(per_minute=0)


# --- staying on the host ----------------------------------------------------------------

def _client(handler, **kwargs) -> PoliteClient:
    return PoliteClient(
        host="api.example.com",
        user_agent=build_user_agent("ops@example.com"),
        bucket=TokenBucket(per_minute=6000, sleep=lambda _: None),
        client=httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False),
        sleep=lambda _: None,
        **kwargs,
    )


def test_an_absolute_url_on_another_host_is_refused():
    """A source that returns a `next` link is a source that can point us anywhere."""
    client = _client(lambda request: httpx.Response(200, json={}))

    with pytest.raises(OffHostRequest, match="Refusing"):
        client.get_json("https://evil.example.net/data")


def test_a_redirect_off_host_is_refused_rather_than_followed():
    """Following it would launder the request through a check that already passed."""
    def handler(request):
        return httpx.Response(302, headers={"Location": "https://evil.example.net/data"})

    client = _client(handler)
    with pytest.raises(OffHostRequest, match="redirects are not followed"):
        client.get_json("/thing")


def test_every_request_carries_an_identifiable_user_agent():
    seen: list[str] = []

    def handler(request):
        seen.append(request.headers.get("User-Agent", ""))
        return httpx.Response(200, json={})

    _client(handler).get_json("/thing")

    assert seen == ["elestral-vault-harvester/1.0 (+ops@example.com)"]


# --- backoff -----------------------------------------------------------------------------

def test_a_429_is_retried_on_the_servers_schedule():
    """`Retry-After` is obeyed when it is sent. Retrying on our own schedule is arguing with
    the answer."""
    waits: list[float] = []
    attempts = {"n": 0}

    def handler(request):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "7"})
        return httpx.Response(200, json={"ok": True})

    client = PoliteClient(
        host="api.example.com",
        user_agent="ua",
        bucket=TokenBucket(per_minute=6000, sleep=lambda _: None),
        client=httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False),
        sleep=waits.append,
    )

    assert client.get_json("/thing") == {"ok": True}
    assert waits == [7.0]


def test_a_source_that_stays_down_fails_that_source_and_says_so():
    client = _client(lambda request: httpx.Response(503), max_retries=2)

    with pytest.raises(SourceUnavailable, match="after 3 attempts"):
        client.get_json("/thing")


def test_a_400_is_an_answer_and_is_not_retried():
    """Retrying a rejection spends someone else's capacity on a request that will fail
    identically."""
    attempts = {"n": 0}

    def handler(request):
        attempts["n"] += 1
        return httpx.Response(400, text="bad request")

    with pytest.raises(SourceUnavailable):
        _client(handler).get_json("/thing")
    assert attempts["n"] == 1


def test_a_404_can_be_the_answer_the_caller_wanted():
    """The light scan's most common response: the listing is gone."""
    client = _client(lambda request: httpx.Response(404))

    assert client.get_json("/item/gone", not_found_ok=True) is None
