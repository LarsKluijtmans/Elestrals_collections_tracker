"""Catalog importer.

    Controllers / CLI → ImportRunner → SourceAdapter → Normaliser → CatalogUpsert → repositories

The normaliser and fingerprint modules are pure, so most of this package is testable without a
database. See `ddd-02-technical-design.md`.
"""
from __future__ import annotations

from .canonical import (
    CanonicalCard,
    CanonicalPrinting,
    ImportCounts,
    PrintingKey,
    RawRecord,
    Rejection,
    SetMeta,
    SourceDescriptor,
)
from .sources import available_sources, get_source

__all__ = [
    "CanonicalCard",
    "CanonicalPrinting",
    "ImportCounts",
    "PrintingKey",
    "RawRecord",
    "Rejection",
    "SetMeta",
    "SourceDescriptor",
    "available_sources",
    "get_source",
]
