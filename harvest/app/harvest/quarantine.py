"""When to stop asking, and for how long. FR-18.

ADR-004 chose an assertive posture, which makes being blocked an operating condition rather than
an incident. The failure this module prevents is the obvious one: a pipeline that meets its first
403 with retries turns a temporary block into a permanent one, and does it while looking busy.

Three rules, all boring on purpose:

* **A threshold, not a hair trigger.** One 429 is ordinary traffic shaping and the HTTP layer
  already backs off for it. Quarantine is for a *sustained* pattern within a run.
* **Escalating backoff.** An hour, then four, then sixteen, up to a ceiling. A source that
  refuses us twice in a row is not more likely to relent on the same schedule.
* **One probing request on release, not a full scan.** Resuming a 400-query deep scan against a
  source that is still blocking would re-trigger whatever caused it. The runner asks once; the
  answer decides whether the level resets or the backoff doubles down.

Pure policy, no session and no clock of its own, so the arithmetic is testable without waiting
and without a database.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class QuarantinePolicy:
    #: Refusals within one run before the source is quarantined.
    threshold: int = 5
    #: The first quarantine's length. Each consecutive one multiplies it.
    base_minutes: int = 60
    backoff_factor: float = 4.0
    max_minutes: int = 2880

    def should_quarantine(self, refusals: int) -> bool:
        return refusals >= self.threshold

    def duration_for(self, level: int) -> timedelta:
        """`level` is how many consecutive quarantines this source has had, including this one.

        Level 1 is `base_minutes`; each further level multiplies, capped. A clean run resets the
        level to 0, so a source that recovers is not punished for last month.
        """
        steps = max(0, level - 1)
        minutes = self.base_minutes * (self.backoff_factor**steps)
        return timedelta(minutes=min(minutes, self.max_minutes))

    def until(self, now: datetime, level: int) -> datetime:
        return now + self.duration_for(level)
