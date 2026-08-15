"""Raw source rows → canonical cards, or rejections with a reason.

Three properties this module is required to have, and is tested for:

* **Pure** — no database, no network, no clock. Fixture-driven tests need nothing running.
* **Total** — it never raises. A record it cannot handle becomes a `Rejection`, because an
  exception mid-run would take the whole import down over one bad row.
* **Whole-record** — a card is emitted complete or not at all. A row-level problem rejects the
  *entire card*, not just the offending printing: importing a card with one printing missing
  silently corrupts set completion, which is worse than importing nothing and saying so.
"""
from __future__ import annotations

import json
from collections import OrderedDict
from collections.abc import Iterable

from . import vocabulary as vocab
from .canonical import (
    CanonicalCard,
    CanonicalPrinting,
    NormalisationResult,
    RawRecord,
    Rejection,
)

#: Fields that describe the *card*, so every row of one card must agree on them.
CARD_LEVEL_FIELDS = (
    "name", "card_type", "element", "rune_type", "subtype",
    "attack", "defence", "spirit_cost", "rules_text", "flavour_text", "artist",
)

_REQUIRED = ("collector_number", "name", "card_type", "rarity")


def _get(row: dict[str, str], key: str) -> str:
    return (row.get(key) or "").strip()


def _opt(row: dict[str, str], key: str) -> str | None:
    value = _get(row, key)
    return value or None


def _as_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalise_set(records: Iterable[RawRecord], *, set_code: str) -> NormalisationResult:
    """Group rows into cards and validate each group whole."""
    result = NormalisationResult()

    groups: OrderedDict[str, list[RawRecord]] = OrderedDict()
    for record in records:
        number = _get(record.data, "collector_number")
        if not number:
            result.rejections.append(Rejection(
                source_ref=record.source_ref,
                reason_code="missing_required_field",
                field="collector_number",
                message="Row has no collector_number, so it cannot be attached to a card.",
                raw_record=dict(record.data),
            ))
            continue
        groups.setdefault(number, []).append(record)

    for number, rows in groups.items():
        outcome = _normalise_card(rows, set_code=set_code, collector_number=number)
        if isinstance(outcome, Rejection):
            result.rejections.append(outcome)
        else:
            result.cards.append(outcome)

    return result


def _normalise_card(
    rows: list[RawRecord], *, set_code: str, collector_number: str
) -> CanonicalCard | Rejection:
    head = rows[0]

    for field_name in _REQUIRED:
        if not _get(head.data, field_name):
            return Rejection(
                source_ref=head.source_ref,
                reason_code="missing_required_field",
                field=field_name,
                message=f"`{field_name}` is required and was empty.",
                raw_record=dict(head.data),
            )

    conflict = _find_card_level_conflict(rows)
    if conflict is not None:
        field_name, first_value, other_value, other_ref = conflict
        return Rejection(
            source_ref=other_ref,
            reason_code="conflicting_card_fields",
            field=field_name,
            message=(
                f"Rows for card {collector_number} disagree on `{field_name}`: "
                f"{first_value!r} at {head.source_ref} vs {other_value!r} at {other_ref}. "
                "Taking either would make the card depend on file ordering."
            ),
            raw_record=dict(head.data),
        )

    card_type = vocab.card_type(_get(head.data, "card_type"))
    if card_type is None:
        return Rejection(
            source_ref=head.source_ref, reason_code="missing_required_field", field="card_type",
            message=f"Unrecognised card_type {_get(head.data, 'card_type')!r}.",
            raw_record=dict(head.data),
        )

    element = vocab.element(_opt(head.data, "element"))
    if _opt(head.data, "element") and element is None:
        return Rejection(
            source_ref=head.source_ref, reason_code="type_field_mismatch", field="element",
            message=f"Unrecognised element {_get(head.data, 'element')!r}.",
            raw_record=dict(head.data),
        )

    rune_type = vocab.rune_type(_opt(head.data, "rune_type"))
    if _opt(head.data, "rune_type") and rune_type is None:
        return Rejection(
            source_ref=head.source_ref, reason_code="type_field_mismatch", field="rune_type",
            message=f"Unrecognised rune_type {_get(head.data, 'rune_type')!r}.",
            raw_record=dict(head.data),
        )

    attack = _as_int(_get(head.data, "attack")) if _get(head.data, "attack") else None
    defence = _as_int(_get(head.data, "defence")) if _get(head.data, "defence") else None

    mismatch = _check_type_rules(
        card_type=card_type, element=element, rune_type=rune_type,
        attack_raw=_get(head.data, "attack"), defence_raw=_get(head.data, "defence"),
        attack=attack, defence=defence,
    )
    if mismatch is not None:
        field_name, message = mismatch
        return Rejection(
            source_ref=head.source_ref, reason_code="type_field_mismatch", field=field_name,
            message=message, raw_record=dict(head.data),
        )

    spirit_cost, cost_error = _parse_spirit_cost(_get(head.data, "spirit_cost"))
    if cost_error is not None:
        return Rejection(
            source_ref=head.source_ref, reason_code="invalid_spirit_cost", field="spirit_cost",
            message=cost_error, raw_record=dict(head.data),
        )

    printings: list[CanonicalPrinting] = []
    seen: set[tuple[str, str, str, str]] = set()
    for row in rows:
        printing_or_rejection = _normalise_printing(row)
        if isinstance(printing_or_rejection, Rejection):
            return printing_or_rejection
        printing = printing_or_rejection

        key = (printing.rarity, printing.finish, printing.language, printing.edition)
        if key in seen:
            return Rejection(
                source_ref=row.source_ref, reason_code="duplicate_printing_key", field="rarity",
                message=(
                    f"Two rows of card {collector_number} produce the same printing "
                    f"{key}. One of them is a duplicate."
                ),
                raw_record=dict(row.data),
            )
        seen.add(key)
        printings.append(printing)

    return CanonicalCard(
        set_code=set_code,
        collector_number=collector_number,
        name=_get(head.data, "name"),
        card_type=card_type,
        element=element,
        rune_type=rune_type,
        subtype=_opt(head.data, "subtype"),
        attack=attack,
        defence=defence,
        spirit_cost=spirit_cost,
        rules_text=_opt(head.data, "rules_text"),
        flavour_text=_opt(head.data, "flavour_text"),
        artist=_opt(head.data, "artist"),
        printings=tuple(printings),
    )


def _find_card_level_conflict(
    rows: list[RawRecord],
) -> tuple[str, str, str, str] | None:
    """Compare *raw* values so a typo is caught before parsing folds it away."""
    head = rows[0]
    for row in rows[1:]:
        for field_name in CARD_LEVEL_FIELDS:
            first = _get(head.data, field_name)
            other = _get(row.data, field_name)
            if first != other:
                return field_name, first, other, row.source_ref
    return None


def _check_type_rules(
    *, card_type: str, element: str | None, rune_type: str | None,
    attack_raw: str, defence_raw: str, attack: int | None, defence: int | None,
) -> tuple[str, str] | None:
    if attack_raw and attack is None:
        return "attack", f"`attack` must be an integer, got {attack_raw!r}."
    if defence_raw and defence is None:
        return "defence", f"`defence` must be an integer, got {defence_raw!r}."

    if card_type == "elestral":
        if element is None:
            return "element", "An elestral must have an element."
        if rune_type is not None:
            return "rune_type", "`rune_type` belongs to runes, not elestrals."
    elif card_type == "spirit":
        if element is None:
            return "element", "A spirit must have an element."
        if rune_type is not None:
            return "rune_type", "`rune_type` belongs to runes, not spirits."
        if attack is not None or defence is not None:
            return "attack", "`attack`/`defence` belong to elestrals, not spirits."
    elif card_type == "rune":
        if rune_type is None:
            return "rune_type", "A rune must have a rune_type."
        if attack is not None or defence is not None:
            return "attack", "`attack`/`defence` belong to elestrals, not runes."
    return None


def _parse_spirit_cost(raw: str) -> tuple[dict[str, int] | None, str | None]:
    if not raw:
        return None, None
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return None, f"`spirit_cost` must be a JSON object, got {raw!r}."
    if not isinstance(parsed, dict):
        return None, f"`spirit_cost` must be a JSON object, got {type(parsed).__name__}."

    cost: dict[str, int] = {}
    for key, value in parsed.items():
        canonical_element = vocab.element(str(key))
        if canonical_element is None:
            return None, f"`spirit_cost` names an unknown element {key!r}."
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            return None, f"`spirit_cost[{key}]` must be a non-negative integer, got {value!r}."
        cost[canonical_element] = value
    return cost, None


def _normalise_printing(row: RawRecord) -> CanonicalPrinting | Rejection:
    rarity = vocab.rarity(_get(row.data, "rarity"))
    if rarity is None:
        return Rejection(
            source_ref=row.source_ref, reason_code="unknown_rarity", field="rarity",
            message=(
                f"Unrecognised rarity {_get(row.data, 'rarity')!r}. Defaulting it would create "
                "a wrong SKU, so the card is rejected instead."
            ),
            raw_record=dict(row.data),
        )

    finish = vocab.finish(_get(row.data, "finish"))
    if finish is None:
        return Rejection(
            source_ref=row.source_ref, reason_code="unknown_finish", field="finish",
            message=f"Unrecognised finish {_get(row.data, 'finish')!r}.",
            raw_record=dict(row.data),
        )

    edition = vocab.edition(_get(row.data, "edition"))
    if edition is None:
        return Rejection(
            source_ref=row.source_ref, reason_code="unknown_edition", field="edition",
            message=f"Unrecognised edition {_get(row.data, 'edition')!r}.",
            raw_record=dict(row.data),
        )

    language = (_get(row.data, "language") or "en").lower()
    tracked = _get(row.data, "is_tracked_for_price").lower()

    return CanonicalPrinting(
        rarity=rarity,
        finish=finish,
        language=language,
        edition=edition,
        image_url=_opt(row.data, "image_url"),
        is_tracked_for_price=tracked not in ("0", "false", "no"),
    )
