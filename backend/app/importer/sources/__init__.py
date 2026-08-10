"""The source registry.

Adapters register themselves here; `import_runner` resolves by name and never imports an
adapter module directly. That indirection is the whole reason adding a source is "one file
plus one config row" — the requirement from the unit brief, and the reason ADR-001's fallback
to a curated seed touches exactly one file and no domain rule.
"""
from __future__ import annotations

from ..canonical import SourceAdapter

SOURCES: dict[str, SourceAdapter] = {}


class UnknownSource(LookupError):
    pass


def register(adapter: SourceAdapter) -> SourceAdapter:
    SOURCES[adapter.name] = adapter
    return adapter


def get_source(name: str) -> SourceAdapter:
    try:
        return SOURCES[name]
    except KeyError:
        raise UnknownSource(
            f"Unknown source {name!r}. Registered: {', '.join(sorted(SOURCES)) or '(none)'}"
        ) from None


def available_sources() -> list[str]:
    return sorted(SOURCES)


# The one place adapter modules are imported. Adding a source means adding a line here and a
# file next to it — nothing else in the codebase learns the source's name.
from .csv_seed import CsvSeedAdapter  # noqa: E402

register(CsvSeedAdapter())
