import collections

import pytest

from local_reservations.common import canon
from local_reservations.common.adapters import rajasthan
from local_reservations.paths import ROOT


@pytest.fixture(scope="module")
def sibling():
    path = ROOT.parent / rajasthan.REPO
    if not path.exists():
        pytest.skip("Rajasthan sibling repository is not checked out")
    return path


@pytest.fixture(scope="module")
def slices(sibling):
    return list(rajasthan.slices(sibling))


def test_all_structured_rural_seats_are_adapted(slices):
    counts = collections.Counter(
        (row["tier"], row["year"]) for slice_ in slices for row in slice_["rows"]
    )
    assert counts == collections.Counter(rajasthan.DECLARED_UNITS)
    assert sum(counts.values()) == 149951


def test_all_sarpanch_candidates_are_retained(slices):
    heads = [
        row for slice_ in slices for row in slice_["rows"] if row["tier"] == "gp_head"
    ]
    members = [member for row in heads for member in row.get("seat_members", [])]
    assert len(members) == rajasthan.DECLARED[rajasthan.CONTESTING_FILE]
    assert sum(member["result"] == "winner" for member in members) == 11257
    assert all(
        "MobileNo" not in member and "EmailAddress" not in member for member in members
    )
    assert members[0]["candidate_occupation"]
    assert members[0]["candidate_marital_status"]
    ambiguous = [row for row in heads if row.get("winner_candidate_ambiguous")]
    assert len(ambiguous) == 175


def test_result_and_roster_limits_are_explicit(slices):
    heads_2020 = [
        row
        for slice_ in slices
        for row in slice_["rows"]
        if row["tier"] == "gp_head" and row["year"] == "2020"
    ]
    roster_only = [row for row in heads_2020 if not row.get("seat_members")]
    assert {row["gram_panchayat"].upper() for row in roster_only} == {
        "RIBIYA",
        "KALEWA",
        "GOLA KA BAS",
        "SAMBHARIA",
    }
    candidate_only = [
        row
        for slice_ in slices
        for row in slice_["rows"]
        if row["tier"] == "gp_head"
        and row.get("seat_members")
        and not row.get("winner")
    ]
    assert len(candidate_only) == 13
    assert all(row["listing_scope"] == "all_seats" for row in candidate_only)


def test_old_panel_winner_gender_is_not_dropped(slices):
    rows = [
        row
        for slice_ in slices
        for row in slice_["rows"]
        if row["tier"] == "gp_head" and row["year"] == "2015"
    ]
    assert {row["winner_gender"] for row in rows} == {
        "Woman",
        "Other than Woman",
    }


def test_old_panel_printed_gp_name_controls_seat_identity(slices):
    rows = [
        row
        for slice_ in slices
        for row in slice_["rows"]
        if row["tier"] == "gp_head" and row["year"] == "2005"
    ]
    keys = collections.Counter(canon.seat_identity(row) for row in rows)
    collisions = {key: count for key, count in keys.items() if count > 1}
    assert sum(collisions.values()) == 7
    assert len(collisions) == 3

    daulatpura = [
        row
        for row in rows
        if row["district"] == "AJMER"
        and row["block"] == "MASUDA"
        and row["winner"] in {"DESHRAJ", "KARAN SINGH"}
    ]
    assert {row["gram_panchayat"] for row in daulatpura} == {
        "DAULATPURA-I",
        "DAULATPURA-II",
    }
    assert len({row["gram_panchayat_standardized"] for row in daulatpura}) == 1


def test_blank_ward_winners_are_explicitly_vacant(slices):
    rows = [
        row
        for slice_ in slices
        for row in slice_["rows"]
        if row["tier"] == "gp_ward" and not row["winner"]
    ]
    assert len(rows) == 2
    assert all(row["vacant"] == 1 for row in rows)
    assert all(not row["winner_gender"] and not row["winner_caste"] for row in rows)
    assert {row["winner_category_raw"] for row in rows} == {"ST", "ST (Woman)"}


def test_nomination_summaries_keep_their_own_grain(sibling):
    table = rajasthan.supplemental(sibling)
    assert table["name"] == "supplemental_rajasthan_nomination_stats.parquet"
    assert len(table["rows"]) == rajasthan.DECLARED[rajasthan.NOMINATION_FILE]
    assert collections.Counter(
        row["year"] for row in table["rows"]
    ) == collections.Counter(rajasthan.NOMINATION_UNITS)
    assert len({row["row_id"] for row in table["rows"]}) == len(table["rows"])
