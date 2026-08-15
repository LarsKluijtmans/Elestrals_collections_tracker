"""Orchestrates one scan: gate → plan → fetch → match → record → report.

One execution path for both modes and every caller — the CLI, the Celery beat schedule and the
admin trigger all end up here, so what runs at 3am is the same object graph a human starts by
hand. That is story 027's "the trigger path and the scheduled path are the same code", and it is
a function rather than a promise.

    deep    ask the whole catalog-derived query space; discover what we have never seen
    light   re-check known listings by id; then a short "more like this" plan around the products
            whose market just moved

The two share `_ingest`, the only place a listing becomes a row. Everything that makes a scan
trustworthy lives there or in the gate above it:

* a source that does not report sales cannot produce a `sold` observation, even if its connector
  claims one — the check is against `price_sources.reports_sold`, not against the connector's
  word;
* a match under the confidence floor is counted as rejected and writes no observation, while the
  listing itself is kept as a lead;
* one query failing fails that query, never the run. A run ends `partial` and says which queries
  died, because a source that answers 380 of 400 questions is not a failed run and reporting it as
  one trains everyone to ignore the status;
* **a sustained pattern of refusals quarantines the source** (FR-18). Under ADR-004 blocks are an
  operating condition, and retrying into one is how a temporary block becomes permanent.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal

from ..config import settings
from ..harvest.canonical import HarvestCounts, HarvestDescriptor, Query, RawListing
from ..harvest.gate import HarvestGate, SourceNotCleared
from ..harvest.http import PoliteClient, SourceRefused, build_user_agent
from ..harvest.matcher import TitleMatcher
from ..harvest.quarantine import QuarantinePolicy
from ..harvest.query_plan import Focus, deep_plan, light_plan
from ..harvest.rate_limit import TokenBucket
from ..harvest.sources import new_source
from ..models.harvest_run import HarvestRun
from ..models.price_source import PriceSource
from ..repositories.catalog_snapshot_repository import CatalogSnapshotRepository
from ..repositories.harvest_repository import HarvestRepository
from ..repositories.price_source_repository import PriceSourceRepository
from .logging_service import log_event

ClientFactory = Callable[[HarvestDescriptor, PriceSource], PoliteClient]


def default_gate() -> HarvestGate:
    return HarvestGate(
        allowed_hosts=frozenset(settings.allowed_hosts_list),
        contact_email=settings.harvest_contact_email,
    )


def default_policy() -> QuarantinePolicy:
    return QuarantinePolicy(
        threshold=settings.harvest_block_threshold,
        base_minutes=settings.harvest_quarantine_minutes,
        backoff_factor=settings.harvest_quarantine_backoff_factor,
        max_minutes=settings.harvest_quarantine_max_minutes,
    )


def default_client_factory(descriptor: HarvestDescriptor, row: PriceSource) -> PoliteClient:
    """The rate limit comes from the source's row; the identity comes from configuration."""
    return PoliteClient(
        host=descriptor.host,
        user_agent=build_user_agent(settings.harvest_contact_email.strip() or "unset"),
        bucket=TokenBucket(per_minute=row.rate_limit_per_min),
        timeout=settings.harvest_request_timeout_seconds,
        max_retries=settings.harvest_max_retries,
        expect=descriptor.expects,
    )


class HarvestRunner:
    def __init__(
        self,
        *,
        sources: PriceSourceRepository,
        harvest: HarvestRepository,
        catalog: CatalogSnapshotRepository,
        gate: HarvestGate | None = None,
        policy: QuarantinePolicy | None = None,
        client_factory: ClientFactory = default_client_factory,
    ) -> None:
        self._sources = sources
        self._harvest = harvest
        self._catalog = catalog
        self._gate = gate or default_gate()
        self._policy = policy or default_policy()
        self._client_factory = client_factory

    # --- entry point ----------------------------------------------------------------

    def run(
        self,
        *,
        source_key: str,
        mode: str,
        run: HarvestRun | None = None,
        triggered_by: str = "schedule",
    ) -> HarvestRun:
        if mode not in ("deep", "light"):
            raise ValueError(f"mode must be 'deep' or 'light', not {mode!r}")

        adapter = new_source(source_key)
        descriptor = adapter.describe()
        row = self._sources.by_key(source_key)

        try:
            self._gate.check(descriptor, row)
        except SourceNotCleared as exc:
            # A refused source made no request, so there is nothing to report a run about —
            # unless the caller already created one (the admin trigger does, to return an id in
            # its 202), in which case it must not be left `running` forever.
            log_event(
                "warning", f"harvest refused: {source_key}",
                component="price-harvester", operation="harvest.gate",
                context={"source": source_key, "mode": mode, "reason": str(exc)},
            )
            if run is not None:
                self._harvest.finish_run(run, status="failed", counts={}, error_summary=str(exc))
                return run
            raise

        assert row is not None  # the gate rejects a missing row before we get here
        index = self._catalog.build()
        matcher = TitleMatcher(index, floor=Decimal(str(settings.harvest_match_confidence_floor)))
        client = self._client_factory(descriptor, row)
        adapter.bind(client)

        run = run if run is not None else self._harvest.start_run(
            row.id, mode, triggered_by=triggered_by
        )
        log_event(
            "info", f"harvest started: {source_key} ({mode})",
            component="price-harvester", operation="harvest.start", run_id=run.id,
            context={"source": source_key, "mode": mode, "triggered_by": run.triggered_by,
                     "access_mode": descriptor.access_mode,
                     "reports_sold": descriptor.reports_sold,
                     "tracked_printings": len(index.printings)},
        )

        counts = HarvestCounts()
        failures: list[str] = []
        refusals = 0
        stopped = False
        try:
            if mode == "deep":
                refusals, stopped = self._deep(
                    adapter, row, run, index, matcher, counts, failures
                )
            else:
                refusals, stopped = self._light(
                    adapter, descriptor, row, run, index, matcher, counts, failures
                )
        finally:
            client.close()

        self._settle_quarantine(row, refusals=refusals, failures=failures, run=run)

        status = self._status(counts, failures, stopped=stopped)
        if stopped:
            failures.append("stopped by an admin")
        self._harvest.finish_run(
            run,
            status=status,
            counts=counts.as_dict(),
            error_summary="\n".join(failures[:50]) or None,
        )
        log_event(
            "info" if status == "success" else "warning",
            f"harvest {status}: {source_key} ({mode})",
            component="price-harvester", operation="harvest.finish", run_id=run.id,
            context={"source": source_key, "mode": mode, "status": status,
                     "refusals": refusals, **counts.as_dict()},
        )
        return run

    @staticmethod
    def _status(counts: HarvestCounts, failures: list[str], *, stopped: bool) -> str:
        if stopped:
            # Ends `partial` with whatever it had. Not `failed`: an admin stopping a scan is a
            # decision, and the data it collected before that is real.
            return "partial"
        if not failures:
            return "success"
        # Nothing came back at all and something went wrong: the source is down, not slow.
        if counts.fetched == 0:
            return "failed"
        return "partial"

    def _settle_quarantine(
        self, row: PriceSource, *, refusals: int, failures: list[str], run: HarvestRun
    ) -> None:
        """Quarantine on a sustained pattern; release on a clean run.

        Deliberately not "quarantine on any refusal": one 403 among 400 queries is a listing we
        are not allowed to see, not a block. And deliberately not "release on any run": a run
        that limped through with failures has not demonstrated the source is well.
        """
        if self._policy.should_quarantine(refusals):
            reason = f"{refusals} refusals in one run"
            self._sources.quarantine(row, reason=reason, policy=self._policy)
            failures.append(f"quarantined: {reason}")
            log_event(
                "error", f"source quarantined: {row.key}",
                component="price-harvester", operation="harvest.quarantine", run_id=run.id,
                context={"source": row.key, "refusals": refusals,
                         "level": row.quarantine_level,
                         "until": str(row.quarantined_until)},
            )
        elif refusals == 0 and not failures and row.quarantine_level:
            self._sources.clear_quarantine(row)

    # --- deep ------------------------------------------------------------------------

    def _deep(self, adapter, row, run, index, matcher, counts, failures) -> tuple[int, bool]:
        if index.is_empty():
            # Worth failing loudly. A deep plan built from an empty catalog is a handful of
            # generic sweeps, which looks like a successful thin run rather than a missing
            # catalog — and ADR-001 left FE01.csv empty on purpose, so this is reachable.
            failures.append(
                "catalog is empty: no tracked printings or sealed products, so the deep plan is "
                "only the generic sweeps. Import the catalog first."
            )

        plan = deep_plan(index, max_queries=settings.harvest_deep_max_queries)
        counts.queries = len(plan)
        return self._execute(
            adapter, row, run, matcher, plan, counts, failures,
            per_query=settings.harvest_deep_results_per_query,
        )

    # --- light -----------------------------------------------------------------------

    def _light(
        self, adapter, descriptor, row, run, index, matcher, counts, failures
    ) -> tuple[int, bool]:
        refusals = self._recheck_known(
            adapter, descriptor, row, run, counts, failures
        )

        focuses: list[Focus] = []
        for product_id, _hint, reason in self._harvest.focus_labels(
            row.id, limit=settings.harvest_light_similar_queries
        ):
            resolved = index.search_text_for(product_id)
            if resolved is None:
                continue  # the catalog no longer has it; the explorer shows that as unmatched
            text, kind_hint = resolved
            focuses.append(Focus(text=text, reason=reason, kind_hint=kind_hint))

        focuses.extend(self._thin_coverage_focuses(row, index, remaining=
            settings.harvest_light_similar_queries - len(focuses)))

        plan = light_plan(focuses, max_queries=settings.harvest_light_similar_queries)
        counts.queries = len(plan)
        more_refusals, stopped = self._execute(
            adapter, row, run, matcher, plan, counts, failures,
            per_query=settings.harvest_light_results_per_query,
        )
        return refusals + more_refusals, stopped

    def _thin_coverage_focuses(self, row, index, *, remaining: int) -> list[Focus]:
        """Products we have never had a live listing for. The second population of story 009."""
        if remaining <= 0:
            return []
        live = self._harvest.products_with_live_listings(row.id)
        out: list[Focus] = []
        for entry in index.printings:
            if len(out) >= remaining:
                break
            if entry.printing_id in live:
                continue
            out.append(Focus(
                text=f"{entry.card_name} {entry.set_code}".strip(),
                reason="no live listing for this product",
                kind_hint="single",
            ))
        return out

    def _recheck_known(self, adapter, descriptor, row, run, counts, failures) -> int:
        """Ask the source about listings we already hold, and record what changed."""
        known = self._harvest.due_for_recheck(
            row.id,
            older_than_hours=settings.harvest_light_recheck_after_hours,
            limit=settings.harvest_light_max_listings,
        )
        if not known:
            return 0
        if not descriptor.supports_recheck:
            failures.append(
                f"{descriptor.name} cannot re-check listings by id, so {len(known)} known "
                "listings were not verified this run"
            )
            return 0

        by_id = {listing.external_id: listing for listing in known}
        try:
            states = list(adapter.recheck(list(by_id)))
        except SourceRefused as exc:
            failures.append(f"recheck refused: {exc}")
            return self._policy.threshold  # a refusal on the re-check is a block, not a gap
        except Exception as exc:  # noqa: BLE001 — a dead re-check must not lose the run
            failures.append(f"recheck failed: {type(exc).__name__}: {exc}")
            log_event(
                "error", "harvest recheck failed",
                component="price-harvester", operation="harvest.recheck", exc=exc,
                run_id=run.id, context={"source": row.key, "listings": len(by_id)},
            )
            return 0

        for state in states:
            listing = by_id.get(state.external_id)
            if listing is None:
                continue
            counts.fetched += 1
            at = state.observed_at or datetime.now(timezone.utc)

            if state.status == "active":
                self._harvest.mark_seen(
                    listing, run_id=run.id, at=at,
                    price_cents=state.price_cents, currency=state.currency,
                )
                # Today's asking price for a listing we already matched. Re-using the stored
                # match is the point of storing it: the title has not changed, so re-deriving it
                # would spend the matcher's time reaching the same answer.
                self._observe_known(listing, row, run, at, counts)
                continue

            self._harvest.mark_ended(
                listing,
                status=self._ended_status(state.status, row),
                at=at,
                sold_price_cents=state.sold_price_cents if row.reports_sold else None,
            )
            counts.ended += 1
            if state.status == "ended_sold" and row.reports_sold:
                self._observe_sale(listing, row, run, at, state.sold_price_cents, counts)
        return 0

    @staticmethod
    def _ended_status(reported: str, row: PriceSource) -> str:
        """A source that does not report sales cannot end a listing as sold.

        The invariant this whole module is arranged around, enforced at the last moment before
        the write — where a wrong connector, a wrong config row and a wrong test double all have
        to pass through it.
        """
        if reported == "ended_sold" and not row.reports_sold:
            return "ended_unknown"
        if reported in ("ended_sold", "ended_unsold", "ended_unknown"):
            return reported
        return "ended_unknown"

    # --- shared --------------------------------------------------------------------

    def _execute(
        self, adapter, row, run, matcher, plan: list[Query], counts, failures, *, per_query: int
    ) -> tuple[int, bool]:
        refusals = 0
        for index_in_plan, query in enumerate(plan):
            # Checked between queries, not mid-query, so a stop lands on a clean boundary and the
            # run finishes its own row properly. Every tenth query: the flag is a database read
            # and a 400-query plan should not become 400 extra round trips.
            if index_in_plan % 10 == 0 and self._harvest.stop_requested(run.id):
                return refusals, True

            try:
                results = list(adapter.discover(query, limit=per_query))
            except SourceRefused as exc:
                refusals += 1
                failures.append(f"{query.text!r}: refused — {exc}")
                if self._policy.should_quarantine(refusals):
                    # Stop the run now rather than working through the remaining plan against a
                    # source that has already said no five times.
                    log_event(
                        "warning", f"halting scan: {row.key} is refusing us",
                        component="price-harvester", operation="harvest.refused", run_id=run.id,
                        context={"source": row.key, "refusals": refusals},
                    )
                    break
                continue
            except Exception as exc:  # noqa: BLE001 — one bad query must not kill the run
                failures.append(f"{query.text!r}: {type(exc).__name__}: {exc}")
                log_event(
                    "error", f"harvest query failed: {query.text}",
                    component="price-harvester", operation="harvest.query", exc=exc,
                    run_id=run.id, context={"source": row.key, "reason": query.reason},
                )
                continue

            for raw in results:
                self._ingest(raw, query, row, run, matcher, counts)
        return refusals, False

    def _ingest(
        self, raw: RawListing, query: Query, row: PriceSource, run, matcher, counts
    ) -> None:
        counts.fetched += 1
        match = matcher.match(raw.title, kind_hint=query.kind_hint)
        counts.parsed += 1

        listing, created = self._harvest.save_listing({
            "source_id": row.id,
            "external_id": raw.external_id,
            "title": raw.title[:320],
            "url": raw.url[:512],
            "image_url": raw.image_url[:512] if raw.image_url else None,
            "kind": match.kind,
            "printing_id": match.printing_id,
            "sealed_product_id": match.sealed_product_id,
            "condition": match.condition,
            "match_confidence": match.confidence,
            "match_note": match.note[:255] if match.note else None,
            "price_cents": raw.price_cents,
            "currency": raw.currency,
            "shipping_cents": raw.shipping_cents,
            "quantity": raw.quantity,
            "buying_format": raw.buying_format,
            "location_country": raw.location_country,
            "status": "ended_sold" if (raw.is_sold and row.reports_sold) else "active",
            "first_seen_at": raw.observed_at,
            "last_seen_at": raw.observed_at,
            "first_seen_run_id": run.id,
            "last_seen_run_id": run.id,
        })
        if created:
            counts.discovered += 1

        if not match.clears(matcher.floor):
            counts.rejected += 1
            return

        sale_type = "sold" if (raw.is_sold and row.reports_sold) else "listed"
        if raw.is_sold and not row.reports_sold:
            # The connector claimed a sale from a source configured not to report them. Not
            # trusted, and not silent: one of the two is wrong and somebody has to look.
            log_event(
                "warning",
                f"{row.key} reported a sale but is configured reports_sold=0; recorded as an "
                "asking price instead",
                component="price-harvester", operation="harvest.sale-claim", run_id=run.id,
                context={"source": row.key, "external_id": raw.external_id},
            )

        price = raw.sold_price_cents if sale_type == "sold" else raw.price_cents
        if price is None:
            return
        written = self._harvest.record_observation({
            "source_id": row.id,
            "run_id": run.id,
            "printing_id": match.printing_id,
            "sealed_product_id": match.sealed_product_id,
            "condition": match.condition,
            "sale_type": sale_type,
            "observed_at": raw.observed_at,
            "price_cents": price,
            "currency": raw.currency,
            "shipping_cents": raw.shipping_cents,
            "quantity": raw.quantity,
            "external_id": _observation_key(raw.external_id, sale_type, raw.observed_at),
            "source_url": raw.url[:512],
            "match_confidence": match.confidence,
            "created_at": datetime.now(timezone.utc),
        })
        if written:
            counts.accepted += 1

    def _observe_known(self, listing, row, run, at: datetime, counts) -> None:
        """Write today's asking price for an already-matched listing."""
        if not (listing.printing_id or listing.sealed_product_id):
            return
        written = self._harvest.record_observation({
            "source_id": row.id,
            "run_id": run.id,
            "printing_id": listing.printing_id,
            "sealed_product_id": listing.sealed_product_id,
            "condition": listing.condition,
            "sale_type": "listed",
            "observed_at": at,
            "price_cents": listing.price_cents,
            "currency": listing.currency,
            "shipping_cents": listing.shipping_cents,
            "quantity": listing.quantity,
            "external_id": _observation_key(listing.external_id, "listed", at),
            "source_url": listing.url[:512],
            "match_confidence": listing.match_confidence or Decimal("0"),
            "created_at": datetime.now(timezone.utc),
        })
        if written:
            counts.accepted += 1

    def _observe_sale(self, listing, row, run, at: datetime, price_cents, counts) -> None:
        """Only reachable when `price_sources.reports_sold` is true. See `_ended_status`."""
        if price_cents is None or not (listing.printing_id or listing.sealed_product_id):
            return
        written = self._harvest.record_observation({
            "source_id": row.id,
            "run_id": run.id,
            "printing_id": listing.printing_id,
            "sealed_product_id": listing.sealed_product_id,
            "condition": listing.condition,
            "sale_type": "sold",
            "observed_at": at,
            "price_cents": price_cents,
            "currency": listing.currency,
            "shipping_cents": listing.shipping_cents,
            "quantity": listing.quantity,
            "external_id": listing.external_id,
            "source_url": listing.url[:512],
            "match_confidence": listing.match_confidence or Decimal("0"),
            "created_at": datetime.now(timezone.utc),
        })
        if written:
            counts.accepted += 1


def _observation_key(external_id: str, sale_type: str, observed_at: datetime) -> str:
    """The dedupe key behind `UNIQUE (source_id, external_id)`.

    A sale happens once and keys on its own id. An asking price is the same listing seen again
    and again, so it keys per day: re-running an hourly light scan writes one row per listing per
    day no matter how often it runs, while tomorrow's price still lands as its own point.
    """
    if sale_type == "sold":
        return external_id[:128]
    return f"{external_id}@{observed_at.date().isoformat()}"[:128]


__all__ = ["HarvestRunner", "default_client_factory", "default_gate", "default_policy"]
