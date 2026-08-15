"""The gate. Nothing reaches the network without passing through here.

FR-1's acceptance criteria in executable form — and the place where **ADR-004** changed what this
module is for.

Before ADR-004 this was a legal veto: a source whose terms prohibited automated access could not
run. That decision has been taken, and taken the other way. The gate no longer asks whether we are
*permitted*; it asks whether the risk has been **read and accepted by a named person**, and
whether this particular source is in a state where asking it anything is a good idea.

Five checks:

1. **The risk is recorded.** `tos_review_note` and `risk_accepted_by` are both present. The schema
   already refuses to enable a source without them; this refuses to *run* one, which catches a row
   edited by hand after enablement.
2. **Code and config agree on the access mode.** A connector declaring `official_api` cannot run
   against a row configured `scrape`, in either direction. A disagreement means someone changed
   one of the two, and guessing which is right is how a scraper ends up running under an API's
   review note.
3. **The host is on the outbound allowlist.** The NFR is "the harvester cannot be steered to
   arbitrary URLs" — declared per connector, checked per run.
4. **The source is not quarantined.** FR-18: a source that has started refusing us stops being
   asked until its backoff expires. Quarantine is a state of the source, not a decision each run
   makes.
5. **We can identify ourselves.** No contact address, no scan. ADR-004 gave up politeness; it kept
   identifiability, and this is where that is enforced rather than intended.

The gate raises rather than returning `False`. A caller that forgets to check a boolean makes a
request; a caller that forgets to catch an exception makes none.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ..models.price_source import PriceSource
from .canonical import HarvestDescriptor


class SourceNotCleared(RuntimeError):
    """Raised instead of making the request. The message names the fix."""


@dataclass(frozen=True, slots=True)
class HarvestGate:
    allowed_hosts: frozenset[str]
    contact_email: str

    def check(
        self,
        descriptor: HarvestDescriptor,
        row: PriceSource | None,
        *,
        now: datetime | None = None,
    ) -> None:
        """Raise `SourceNotCleared` unless this source may run right now."""
        now = now or datetime.now(timezone.utc)
        name = descriptor.name

        if not self.contact_email.strip():
            raise SourceNotCleared(
                "HARVEST_CONTACT_EMAIL is empty. Every request this harvester makes carries a "
                "contact address so a site can ask us to slow down instead of having to block "
                "us. ADR-004 gave up robots.txt and conservative rates; it did not give up "
                "being identifiable, and this is that decision enforced."
            )

        if row is None:
            raise SourceNotCleared(
                f"Source {name!r} has no row in `price_sources`. A source is configuration, not "
                "code: insert the row with its terms review and a risk owner before running it."
            )

        if not row.enabled:
            raise SourceNotCleared(
                f"Source {name!r} is disabled. This is the kill switch, and it takes effect with "
                "no deploy: set `enabled = 1` when the source is cleared to run."
            )

        if not (row.tos_review_note or "").strip():
            raise SourceNotCleared(
                f"Source {name!r} is enabled with no terms review note. Under ADR-004 the note is "
                "not a permission slip — it is the record of what was accepted, and an accepted "
                "risk that was never written down was never read."
            )

        if not (row.risk_accepted_by or "").strip():
            raise SourceNotCleared(
                f"Source {name!r} has no `risk_accepted_by`. ADR-004 accepts a contractual risk "
                "per source; a person has to be attached to that acceptance."
            )

        if row.access_mode != descriptor.access_mode:
            raise SourceNotCleared(
                f"Source {name!r} is configured as access_mode={row.access_mode!r} but its "
                f"connector declares {descriptor.access_mode!r}. Fix the disagreement — running "
                "either way would apply one mode's review to the other mode's traffic."
            )

        if descriptor.host not in self.allowed_hosts:
            raise SourceNotCleared(
                f"Source {name!r} talks to {descriptor.host!r}, which is not on the outbound "
                f"allowlist ({', '.join(sorted(self.allowed_hosts)) or 'empty'}). Add it to "
                "HARVEST_ALLOWED_HOSTS deliberately, or do not run this source."
            )

        if row.is_quarantined(now):
            remaining = row.quarantined_until - now  # type: ignore[operator]
            minutes = max(1, int(remaining.total_seconds() // 60))
            raise SourceNotCleared(
                f"Source {name!r} is quarantined for another {minutes} minute(s): "
                f"{row.quarantine_reason or 'blocked'}. Retrying into a block is how a temporary "
                "one becomes permanent. Clear `quarantined_until` deliberately to override."
            )
