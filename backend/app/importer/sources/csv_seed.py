"""The curated CSV seed — phase 1's source of truth.

Chosen in `adr-001-catalog-data-source.md`: the publisher's Terms of Use prohibit scraping,
prohibit accessing the site to build a competing product, and prohibit reproducing site
content. All three land on this project at once, so the catalog is hand-compiled instead.

`requires_network = False`, and that is load-bearing: none of the robots.txt / rate-limit /
user-agent machinery the unit brief demands of scrapers ships in phase 1, because this
importer makes no outbound request at all.

Layout — `backend/data/catalog/`:

    sets.csv        one row per set, carrying the **printed** card_count
    FE01.csv        one row per printing; card-level fields repeat across a card's rows

Lines beginning with `#` are comments, so a hand-maintained file can carry notes.
"""
from __future__ import annotations

import csv
from collections.abc import Iterable, Iterator
from pathlib import Path

from .. import vocabulary as vocab
from ..canonical import RawRecord, SetMeta, SourceDescriptor

#: backend/data/catalog
DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "data" / "catalog"


class SeedNotFound(FileNotFoundError):
    pass


def _rows(path: Path) -> Iterator[tuple[int, dict[str, str]]]:
    """Yield (line number **in the real file**, row), skipping comments and blank lines.

    The line number has to survive comment stripping, because `source_ref` is the whole point
    of a rejection: "FE01.csv:42" has to send someone to line 42 of the file they can open.
    Feeding a filtered generator to `DictReader` and trusting `reader.line_num` would report
    positions in the filtered stream instead.

    Limitation: a field containing a literal newline breaks the 1:1 line mapping. Hand-edited
    seed files do not have those, and a wrong line number is a worse failure than a missing
    one only when it is silent — this is documented rather than silent.
    """
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        kept = [
            (number, line)
            for number, line in enumerate(handle, start=1)
            if line.strip() and not line.lstrip().startswith("#")
        ]

    if len(kept) < 2:  # header only, or nothing at all
        return

    reader = csv.DictReader([line for _, line in kept])
    for (number, _), row in zip(kept[1:], reader):
        yield number, {(k or "").strip(): (v or "") for k, v in row.items()}


class CsvSeedAdapter:
    name = "csv_seed"

    def __init__(self, root: Path | None = None) -> None:
        self._root = Path(root) if root else DEFAULT_ROOT

    def describe(self) -> SourceDescriptor:
        return SourceDescriptor(
            name=self.name,
            display_name="Curated CSV seed",
            requires_network=False,
            terms_url=None,
        )

    @property
    def root(self) -> Path:
        return self._root

    def available_sets(self) -> list[str]:
        return sorted(meta.code for meta in self._all_set_meta())

    def set_meta(self, set_code: str) -> SetMeta:
        for meta in self._all_set_meta():
            if meta.code.upper() == set_code.upper():
                return meta
        raise SeedNotFound(
            f"Set {set_code!r} is not declared in {self._root / 'sets.csv'}. "
            "A set must be declared with its printed card_count before it can be imported."
        )

    def fetch(self, set_code: str) -> Iterable[RawRecord]:
        meta = self.set_meta(set_code)
        path = self._root / f"{meta.code}.csv"
        if not path.exists():
            raise SeedNotFound(
                f"No seed file at {path}. Declared in sets.csv with card_count="
                f"{meta.card_count}, but nothing has been compiled yet."
            )

        default_edition = vocab.default_edition_for_set(meta.code)
        records: list[RawRecord] = []
        for line_no, row in _rows(path):
            # Defaults are applied *here*, by the adapter — never guessed by the normaliser,
            # which must reject what it does not recognise rather than invent a value.
            row.setdefault("set_code", meta.code)
            if not row.get("finish", "").strip():
                row["finish"] = "normal"
            if not row.get("language", "").strip():
                row["language"] = "en"
            if not row.get("edition", "").strip():
                row["edition"] = default_edition
            records.append(RawRecord(source_ref=f"{path.name}:{line_no}", data=row))
        return records

    def _all_set_meta(self) -> list[SetMeta]:
        path = self._root / "sets.csv"
        if not path.exists():
            raise SeedNotFound(f"No set registry at {path}.")

        out: list[SetMeta] = []
        for _, row in _rows(path):
            code = (row.get("set_code") or "").strip()
            if not code:
                continue
            try:
                card_count = int((row.get("card_count") or "0").strip() or 0)
            except ValueError:
                card_count = 0
            out.append(SetMeta(
                code=code,
                name=(row.get("name") or code).strip(),
                card_count=card_count,
                series=(row.get("series") or "").strip() or None,
                released_on=(row.get("released_on") or "").strip() or None,
                logo_asset_url=(row.get("logo_asset_url") or "").strip() or None,
            ))
        return out
