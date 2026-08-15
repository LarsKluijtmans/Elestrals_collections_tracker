"""The seed adapter: comments, defaults, and honest failures."""
from __future__ import annotations

import pytest

from app.importer.sources.csv_seed import CsvSeedAdapter, SeedNotFound

SETS = """# a comment line
set_code,name,series,released_on,card_count,logo_asset_url
FE01,Base,First Edition,2022-11-01,126,
DC01,Firestorm,Divine Champions,,90,
"""

CARDS = """# leading comment
set_code,collector_number,name,card_type,element,rune_type,attack,defence,spirit_cost,rarity,finish,language,edition,image_url
FE01,BS1-001,Teratlas,elestral,earth,,2400,2100,"{""earth"": 2}",holo_rare,,,,
"""


@pytest.fixture()
def seed_root(tmp_path):
    (tmp_path / "sets.csv").write_text(SETS, encoding="utf-8")
    (tmp_path / "FE01.csv").write_text(CARDS, encoding="utf-8")
    return tmp_path


def test_describe_declares_no_network(seed_root):
    """Load-bearing: the robots.txt / rate-limit machinery hangs off this flag, and none of
    it ships while the seed is the source (adr-001)."""
    descriptor = CsvSeedAdapter(seed_root).describe()
    assert descriptor.requires_network is False
    assert descriptor.name == "csv_seed"


def test_available_sets_reads_the_registry(seed_root):
    assert CsvSeedAdapter(seed_root).available_sets() == ["DC01", "FE01"]


def test_set_meta_carries_the_declared_printed_size(seed_root):
    meta = CsvSeedAdapter(seed_root).set_meta("FE01")
    assert meta.card_count == 126
    assert meta.name == "Base"
    assert meta.released_on == "2022-11-01"


def test_unknown_set_is_a_clear_failure(seed_root):
    with pytest.raises(SeedNotFound):
        CsvSeedAdapter(seed_root).set_meta("ZZ99")


def test_declared_set_without_a_card_file_fails_loudly(seed_root):
    """DC01 is declared but never compiled — the runner turns this into a failed set with a
    reason, not a silent zero."""
    with pytest.raises(SeedNotFound):
        list(CsvSeedAdapter(seed_root).fetch("DC01"))


def test_defaults_are_applied_by_the_adapter_not_guessed_downstream(seed_root):
    (record,) = list(CsvSeedAdapter(seed_root).fetch("FE01"))
    assert record.data["finish"] == "normal"
    assert record.data["language"] == "en"
    # FE* is the First Edition series.
    assert record.data["edition"] == "first"


def test_source_ref_names_the_file_and_line(seed_root):
    (record,) = list(CsvSeedAdapter(seed_root).fetch("FE01"))
    assert record.source_ref.startswith("FE01.csv:")


def test_comment_lines_are_skipped(seed_root):
    assert len(list(CsvSeedAdapter(seed_root).fetch("FE01"))) == 1


def test_shipped_seed_declares_fe01(tmp_path):
    """The seed that actually ships: FE01 declared at its printed size, no rows yet."""
    adapter = CsvSeedAdapter()
    assert "FE01" in adapter.available_sets()
    assert adapter.set_meta("FE01").card_count == 126
    assert list(adapter.fetch("FE01")) == []
