"""A token bucket per source. Politeness is cheaper than a block.

The rate lives in `price_sources.rate_limit_per_min`, not in code, because the number that is
polite is a property of the agreement with the source and changes without a deploy.

`sleep` and `clock` are injected so the tests can assert the pacing arithmetic without
actually waiting — a rate limiter tested by sleeping is a rate limiter tested once and then
skipped.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class TokenBucket:
    """Classic token bucket: `per_minute` tokens, refilled continuously.

    Continuously rather than in per-minute batches: a bucket that refills on the minute lets
    60 requests leave in one burst at 00:00 and nothing until 01:00, which is the shape of
    traffic that gets a key throttled even though the average is inside the limit.
    """

    per_minute: int
    #: Burst allowance. Defaults to the whole minute's budget, which is the usual reading of
    #: a "30 per minute" limit — but a source that means "never two at once" can set 1.
    capacity: float | None = None
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep

    _tokens: float = field(init=False, default=0.0)
    _last: float = field(init=False, default=0.0)

    def __post_init__(self) -> None:
        if self.per_minute <= 0:
            raise ValueError("per_minute must be positive; use `enabled = 0` to stop a source")
        if self.capacity is None:
            self.capacity = float(self.per_minute)
        self._tokens = float(self.capacity)
        self._last = self.clock()

    @property
    def _rate_per_second(self) -> float:
        return self.per_minute / 60.0

    def acquire(self, tokens: float = 1.0) -> float:
        """Block until `tokens` are available. Returns how long it waited, for the logs."""
        waited = 0.0
        while True:
            now = self.clock()
            self._tokens = min(
                float(self.capacity), self._tokens + (now - self._last) * self._rate_per_second
            )
            self._last = now
            if self._tokens >= tokens:
                self._tokens -= tokens
                return waited
            delay = (tokens - self._tokens) / self._rate_per_second
            self.sleep(delay)
            waited += delay
