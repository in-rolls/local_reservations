"""Contracts for the generated coverage table."""

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from local_reservations.common import notes, slice_checks
from local_reservations.tools import build_coverage, build_sources


def test_sibling_parquet_rows_are_counted_from_metadata(tmp_path, monkeypatch):
    sibling = tmp_path / "sibling"
    sibling.mkdir()
    pq.write_table(pa.table({"seat": [1, 2, 3]}), sibling / "seats.parquet")
    monkeypatch.setattr(build_coverage, "ROOT", tmp_path / "local_reservations")
    spec = {"repo": "sibling", "files": ["seats.parquet"]}
    assert build_coverage.sibling_rows(spec) == "3"


def test_source_holdings_use_inventory_directory_names(tmp_path, monkeypatch):
    inventory = tmp_path / "inventory.csv"
    inventory.write_text(
        "state,format,pages\nmadhya_pradesh,digital-text,351\ntamil_nadu,scan,74\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(build_sources, "INVENTORY", inventory)
    rendered = build_sources.render()
    assert "| Madhya Pradesh | 1 | 0 | 0 | 0 | 351 |" in rendered
    assert "| Tamil Nadu | 0 | 1 | 0 | 0 | 74 |" in rendered


def test_coverage_describes_held_unparsed_pdfs_plainly():
    assam = next(row for row in build_coverage.build_rows() if row[0] == "Assam")
    assert assam[4] == "parsed"
    assert assam[5] == "23 held 2025 district PRI scans remain unparsed"
    ap = next(row for row in build_coverage.build_rows() if row[0] == "Andhra Pradesh")
    assert "all 13 GP district gazettes are held" in ap[5]
    assert "8 are parsed and 5 remain unparsed" in ap[5]


def test_complete_manifest_changes_missing_districts_to_held_unparsed(tmp_path):
    manifest = tmp_path / "data" / "ap" / "2020_res_gp" / "manifest.csv"
    manifest.parent.mkdir(parents=True)
    districts = [f"District {number}" for number in range(1, 14)]
    manifest.write_text(
        "state,year,district\n"
        + "".join(f"Andhra Pradesh,2020,{district}\n" for district in districts),
        encoding="utf-8",
    )
    rows = [{"district": district, "woman_reserved": "0"} for district in districts[:7]]
    a_slice = slice_checks.Slice("Andhra Pradesh", "2020", "gp_head", rows, tmp_path)
    found = notes.districts_missing(a_slice)
    assert found["text"] == "some held districts are unparsed"
    assert "13 of 13 district source PDFs held" in found["detail"]
    assert found["status"] is None


def test_coverage_does_not_call_every_unlinked_pdf_missing_work():
    rows = {row[0]: row for row in build_coverage.build_rows()}
    assert "not missing seats" in rows["Karnataka"][5]
    assert "not additional final seats" in rows["West Bengal"][5]


def test_coverage_names_sources_that_still_have_to_be_acquired():
    rows = {row[0]: row for row in build_coverage.build_rows()}
    assert "acquire seat-level rural data" in rows["Odisha"][5]
    assert "acquire a village-panchayat" in rows["Tamil Nadu"][5]


def test_every_parsed_state_with_unlinked_pdfs_has_a_reviewed_classification():
    parsed = build_coverage.parsed_datasets()
    unlinked = build_coverage.unlinked_source_pdfs()
    states = {
        state for state, entry in parsed.items() if unlinked.get(entry["dir"], set())
    }
    assert states <= set(build_coverage.REMAINING_WORK)


def test_sibling_source_record_counts_are_reported():
    rows = {row[0]: row for row in build_coverage.build_rows()}
    assert "local_elections_rajasthan" in rows["Rajasthan"][6]
    required = [
        build_coverage.ROOT.parent / build_coverage.SIBLINGS[state]["repo"]
        for state in ("Rajasthan", "Uttar Pradesh")
    ]
    if not all(path.exists() for path in required):
        pytest.skip("state sibling repositories are not checked out")
    assert rows["Rajasthan"][3] == "248,196"
    assert rows["Uttar Pradesh"][3] == "535,848"
