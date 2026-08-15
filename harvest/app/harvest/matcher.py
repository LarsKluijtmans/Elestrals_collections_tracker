"""Title → SKU. The step where a price becomes a fact about a specific card, or does not.

FR-3: *"matches below the confidence floor are rejected, not stored as low-confidence
facts."* Everything here serves that sentence. A seller writes

    "Elestrals Vipyro FE01 012/126 Holo 1st Edition NM"

and the catalog holds a `printing` keyed by set, number, rarity, finish, language and edition.
Getting that mapping wrong is not a small error: a foil price recorded against the non-foil
printing moves a median that someone's collection valuation is computed from.

So the matcher is built to **refuse** rather than to guess:

* A **graded** card is rejected outright. A PSA 10 and a raw copy of the same card are two
  different markets, our schema has nowhere to put a grade, and a slab price in a raw median
  is the single most effective way to make every valuation wrong at once.
* A **lot** is rejected. "3x Vipyro" at $30 is not a $30 Vipyro, and dividing by a quantity
  parsed out of a title is arithmetic performed on a guess.
* A **proxy or custom** is rejected. It is not the card.
* A **language** we have no printing for is rejected, never folded onto the English one.
* An **ambiguous** title — two card names, or several printings and nothing to choose between
  them — loses confidence and usually falls under the floor.

Rejection is not data loss: the listing is still written to `market_listings` with the reason
in `match_note`, because an unmatched listing is a lead. It is either a product missing from
the catalog or a gap in this file, and those are told apart by reading the notes, not by
re-running anything.

The weights below are a starting calibration, not a result. They are meant to be tuned against
the accept-rate trend in the operations console, which is why every one of them is a named
constant rather than a number inline in an expression.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from . import vocabulary as vocab
from .canonical import CONFIDENCE_FLOOR
from .catalog_index import CatalogIndex, PrintingEntry, SealedEntry, normalise
from .vocabulary import CONDITIONS, RARITIES, SEALED_KINDS

# --- scoring weights ---------------------------------------------------------------

W_CARD_NAME = Decimal("0.45")       # the name matched a catalog card
W_SET = Decimal("0.25")             # set code or set name present and consistent
W_NUMBER = Decimal("0.20")          # collector number present and consistent
W_ATTRIBUTES = Decimal("0.10")      # finish / edition / rarity stated and narrowed the choice
W_UNIQUE = Decimal("0.10")          # exactly one printing survived
P_AMBIGUOUS_PRINTING = Decimal("0.15")  # several survived; the default was taken
P_TWO_NAMES = Decimal("0.25")       # a second catalog card name is in the title

W_SEALED_NAME = Decimal("0.75")
W_SEALED_SET = Decimal("0.15")
W_SEALED_KIND = Decimal("0.10")

# --- rejection patterns ------------------------------------------------------------

#: A graded slab. `\b(psa|bgs|cgc|sgc)\s*\d` catches "PSA 10" and "BGS9.5"; the bare words
#: catch "graded" and "slabbed" with no number.
_GRADED = re.compile(r"\b(?:psa|bgs|cgc|sgc|ace)\s*\d|\bgraded\b|\bslab(?:bed)?\b")
_FAKE = re.compile(r"\bproxy\b|\bproxies\b|\bcustom\b|\borica\b|\bfan\s?(?:made|art)\b|\breplica\b")
#: Multiples and grab-bags. `\d+\s*x` catches "3x" and "10 x"; `x\s*\d+` catches "x3".
_LOT = re.compile(
    r"\blot\b|\bjob\s?lot\b|\bbulk\b|\bplayset\b|\bmystery\b|\brepack\b|\brandom\b"
    r"|\bcollection\s+of\b|\bbundle\s+of\b|\bset\s+of\b|\b\d+\s*x\b|\bx\s*\d+\b"
)

# --- vocabulary ---------------------------------------------------------------------

#: Longest first — "near mint" must win over "mint", and "moderately played" over "played".
_CONDITION_TOKENS: tuple[tuple[str, str], ...] = (
    ("near mint", "near_mint"), ("moderately played", "moderately_played"),
    ("heavily played", "heavily_played"), ("lightly played", "lightly_played"),
    ("light play", "lightly_played"), ("moderate play", "moderately_played"),
    ("heavy play", "heavily_played"), ("damaged", "damaged"), ("poor", "damaged"),
    ("mint", "mint"), ("nm", "near_mint"), ("lp", "lightly_played"),
    ("mp", "moderately_played"), ("hp", "heavily_played"), ("dmg", "damaged"),
)

_LANGUAGE_TOKENS: tuple[tuple[str, str], ...] = (
    ("japanese", "ja"), ("japan", "ja"), ("jpn", "ja"), ("jp", "ja"),
    ("korean", "ko"), ("kor", "ko"),
)

#: Phrases that state a finish. Checked longest-first for the same reason as conditions:
#: "reverse holo" is not a holo.
_FINISH_PHRASES: tuple[tuple[str, str], ...] = (
    ("reverse holo", "reverse_foil"), ("reverse foil", "reverse_foil"),
    ("non foil", "normal"), ("prismatic", "prismatic"),
    ("holofoil", "foil"), ("holo", "foil"), ("foil", "foil"),
)

_EDITION_PHRASES: tuple[tuple[str, str], ...] = (
    ("1st edition", "first"), ("first edition", "first"), ("unlimited", "unlimited"),
)

_RARITY_PHRASES: tuple[tuple[str, str], ...] = (
    ("full art", "full_art"), ("alt art", "alt_art"), ("alternate art", "alt_art"),
    ("secret rare", "secret"), ("holo rare", "holo_rare"), ("promo", "promo"),
)

#: Sealed kinds as a buyer writes them. Bare "pack" and bare "deck" are absent on purpose —
#: "deck" appears in half the singles listings on any marketplace ("deck ready", "for deck").
_SEALED_PHRASES: tuple[tuple[str, str], ...] = (
    ("booster box", "booster_box"), ("booster pack", "booster_pack"),
    ("sealed pack", "booster_pack"), ("starter deck", "starter_deck"),
    ("elite box", "elite_box"), ("elite trainer", "elite_box"),
    ("sealed case", "case"), ("booster case", "case"),
)


@dataclass(frozen=True, slots=True)
class Match:
    """What the matcher concluded, and why. `note` is written to the listing either way."""

    kind: str                       # single | sealed | lot | unknown
    confidence: Decimal
    note: str
    printing_id: str | None = None
    sealed_product_id: str | None = None
    condition: str | None = None

    @property
    def is_placed(self) -> bool:
        return bool(self.printing_id or self.sealed_product_id)

    def clears(self, floor: Decimal) -> bool:
        """Placed *and* confident. Both, or the observation is not written."""
        return self.is_placed and self.confidence >= floor


class TitleMatcher:
    def __init__(self, index: CatalogIndex, *, floor: Decimal = CONFIDENCE_FLOOR) -> None:
        self._index = index
        self._floor = floor

    @property
    def floor(self) -> Decimal:
        return self._floor

    def match(self, title: str, *, kind_hint: str | None = None) -> Match:
        text = normalise(title)
        if not text:
            return Match(kind="unknown", confidence=Decimal("0"), note="empty title")

        rejection = self._rejects(text)
        if rejection is not None:
            return rejection

        sealed = self._match_sealed(text)
        # The single matcher gets the raw title too: `normalise` strips the punctuation that
        # a collector number is made of, so "012/126" and "#012" only exist before folding.
        single = self._match_single(text, title)

        # Both can fire — "Vipyro booster box" is a real title. Take the higher confidence,
        # and let `kind_hint` break an exact tie rather than override a better answer.
        if sealed and single:
            if single.confidence > sealed.confidence:
                return single
            if sealed.confidence > single.confidence:
                return sealed
            return sealed if kind_hint == "sealed" else single
        if sealed:
            return sealed
        if single:
            return single

        return Match(
            kind="unknown",
            confidence=Decimal("0"),
            note="no catalog card or product name found in the title",
        )

    # --- rejections ----------------------------------------------------------------

    def _rejects(self, text: str) -> Match | None:
        if _GRADED.search(text):
            return Match(
                kind="single", confidence=Decimal("0"),
                note="graded slab — a different market from a raw card, and the schema has "
                     "nowhere to record the grade",
            )
        if _FAKE.search(text):
            return Match(kind="unknown", confidence=Decimal("0"),
                         note="proxy / custom / replica — not the card")
        if _LOT.search(text):
            return Match(kind="lot", confidence=Decimal("0"),
                         note="multiple items in one listing — the price is not per card")
        return None

    # --- sealed --------------------------------------------------------------------

    def _match_sealed(self, text: str) -> Match | None:
        kind = _first_phrase(text, _SEALED_PHRASES)
        best: tuple[Decimal, SealedEntry] | None = None

        for entry in self._index.sealed:
            name = entry.normalised_name
            if not name or name not in text:
                continue
            score = W_SEALED_NAME
            if entry.set_code and normalise(entry.set_code) in text.split():
                score += W_SEALED_SET
            if kind and kind == entry.kind:
                score += W_SEALED_KIND
            if best is None or score > best[0]:
                best = (score, entry)

        if best is not None:
            score, entry = best
            return Match(
                kind="sealed", confidence=_clamp(score), note=f"sealed product: {entry.name}",
                sealed_product_id=entry.sealed_product_id,
            )

        if kind is not None and kind in SEALED_KINDS:
            # A real sealed product we do not have a catalog row for. Worth writing down: it
            # is the deep scan finding something the catalog is missing, which is one of the
            # two things a deep scan is for.
            return Match(
                kind="sealed", confidence=Decimal("0"),
                note=f"sealed {kind} with no matching catalog product — candidate for the "
                     "sealed catalog",
            )
        return None

    # --- singles -------------------------------------------------------------------

    def _match_single(self, text: str, raw_title: str) -> Match | None:
        names = self._names_in(text)
        if not names:
            return None

        candidates = self._index.printings_for_name(names[0])
        if not candidates:
            return None

        score = W_CARD_NAME
        note_parts = [f"card: {candidates[0].card_name}"]

        if len(names) > 1:
            score -= P_TWO_NAMES
            note_parts.append(f"ambiguous: also matched {names[1]!r}")

        # Set
        set_entry = self._index.find_set_in(text)
        if set_entry is not None:
            narrowed = [c for c in candidates if c.set_code.upper() == set_entry.code.upper()]
            if narrowed:
                candidates = narrowed
                score += W_SET
                note_parts.append(f"set: {set_entry.code}")

        # Collector number, read off the unfolded title — see `match()`.
        number = _collector_number(raw_title)
        if number is not None:
            narrowed = [c for c in candidates if _same_number(c.collector_number, number)]
            if narrowed:
                candidates = narrowed
                score += W_NUMBER
                note_parts.append(f"number: {number}")

        # Language. A mismatch is fatal rather than a penalty: an English printing is not a
        # cheaper version of a Japanese card, it is a different card.
        language = _first_phrase_token(text, _LANGUAGE_TOKENS) or "en"
        narrowed = [c for c in candidates if c.language == language]
        if not narrowed:
            return Match(
                kind="single", confidence=Decimal("0"),
                note=f"title is {language}, and no {language} printing exists for "
                     f"{candidates[0].card_name}",
            )
        candidates = narrowed

        # Finish / edition / rarity — each narrows only if it narrows to something.
        stated = False
        for value, attribute in (
            (_first_phrase(text, _FINISH_PHRASES), "finish"),
            (_first_phrase(text, _EDITION_PHRASES), "edition"),
            (_first_phrase(text, _RARITY_PHRASES), "rarity"),
        ):
            if value is None:
                continue
            canonical = getattr(vocab, attribute)(value)
            if canonical is None:
                continue
            narrowed = [c for c in candidates if getattr(c, attribute) == canonical]
            if narrowed:
                candidates = narrowed
                stated = True
                note_parts.append(f"{attribute}: {canonical}")
        if stated:
            score += W_ATTRIBUTES

        if len(candidates) == 1:
            score += W_UNIQUE
        else:
            score -= P_AMBIGUOUS_PRINTING
            note_parts.append(f"{len(candidates)} printings matched; took the plainest")

        chosen = min(candidates, key=_default_first)
        return Match(
            kind="single",
            confidence=_clamp(score),
            note="; ".join(note_parts)[:255],
            printing_id=chosen.printing_id,
            condition=_first_phrase_token(text, _CONDITION_TOKENS),
        )

    def _names_in(self, text: str) -> list[str]:
        """Catalog card names present in the title, longest first, non-overlapping.

        Non-overlapping matters: "Vipyro Ascended" contains "Vipyro", and counting both would
        report an ambiguity that is not there. The longer name is consumed out of the string
        before the shorter one is tried.
        """
        found: list[str] = []
        consumed = text
        for name in self._index.candidate_names_for(text):
            if not name or name not in consumed:
                continue
            pattern = rf"\b{re.escape(name)}\b"
            if re.search(pattern, consumed):
                found.append(name)
                consumed = re.sub(pattern, " ", consumed)
                # One is a match, two is an ambiguity; a third tells us nothing more.
                if len(found) == 2:
                    break
        return found


# --- helpers -------------------------------------------------------------------------

def _clamp(score: Decimal) -> Decimal:
    return max(Decimal("0"), min(Decimal("1"), score)).quantize(Decimal("0.01"))


def _first_phrase(text: str, phrases: tuple[tuple[str, str], ...]) -> str | None:
    """Substring match, in the order given — the tables are written longest-first."""
    for phrase, value in phrases:
        if phrase in text:
            return value
    return None


def _first_phrase_token(text: str, phrases: tuple[tuple[str, str], ...]) -> str | None:
    """Whole-word match. Two-letter codes like `nm` and `jp` need it: without a boundary,
    "jp" matches inside "jpeg" and every listing becomes Japanese."""
    tokens = text.split()
    for phrase, value in phrases:
        if " " in phrase:
            if phrase in text:
                return value
        elif phrase in tokens:
            return value
    return None


_NUMBER_SLASH = re.compile(r"\b(\d{1,3})\s*/\s*\d{1,3}\b")
_NUMBER_HASH = re.compile(r"#\s*(\d{1,3})\b")


def _collector_number(raw_title: str) -> str | None:
    """`012/126` first, then `#012`. Never a bare number: "2021" and "4th" are not SKUs.

    Reads the raw title because both forms are punctuation, and `normalise` removes it.
    """
    match = _NUMBER_SLASH.search(raw_title) or _NUMBER_HASH.search(raw_title)
    return match.group(1) if match else None


def _same_number(catalog_number: str, found: str) -> bool:
    """`012` and `12` are the same card; `12a` is not `12`."""
    left, right = catalog_number.strip().lower(), found.strip().lower()
    if left == right:
        return True
    return left.isdigit() and right.isdigit() and int(left) == int(right)


def _default_first(entry: PrintingEntry) -> tuple[int, int, int, int]:
    """Sort key for "the plainest printing", used only when the title did not say.

    English, non-foil, unlimited, lowest rarity — the printing a listing that mentions no
    attributes is most likely to be. It is still a guess, which is why taking it costs
    `P_AMBIGUOUS_PRINTING` and usually lands the match under the floor.
    """
    return (
        0 if entry.language == "en" else 1,
        0 if entry.finish == "normal" else 1,
        0 if entry.edition == "unlimited" else 1,
        RARITIES.index(entry.rarity) if entry.rarity in RARITIES else len(RARITIES),
    )


#: Re-exported so callers can validate a parsed condition without importing the model.
KNOWN_CONDITIONS = frozenset(CONDITIONS)
