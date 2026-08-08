"""The candidate-to-seat collapse.

The riskiest transformation here, because it is the only one that changes the
row count by design - so a bug is indistinguishable from correct behaviour by
row count alone. Every case below is a shape that actually occurs in Bihar,
Uttar Pradesh or Uttarakhand.
"""

import pytest

import collapse


def rows(*specs):
    out = []
    for district, panchayat, caste, woman, votes, name in specs:
        out.append({"district": district, "gram_panchayat": panchayat,
                    "caste_reservation": caste, "woman_reserved": woman,
                    "valid_vote": votes, "candidate_name": name})
    return out


KEY = ["district", "gram_panchayat"]


def test_many_candidates_become_one_seat():
    got = collapse.to_seats(
        rows(("A", "X", "SC", "0", "10", "One"),
             ("A", "X", "SC", "0", "30", "Two"),
             ("A", "X", "SC", "0", "20", "Three")),
        KEY, vote_field="valid_vote")
    assert len(got) == 1
    assert got[0]["seat_candidates"] == 3
    assert got[0]["winner"] == "Two"
    assert got[0]["winner_basis"] == "argmax_votes"
    assert got[0]["unit_of_observation"] == "seat_from_candidates"


def test_a_seat_whose_candidates_disagree_on_reservation_raises():
    """Every candidate for a seat contests the same seat. Two reservations
    under one key means the key is wrong, and picking the majority would hide
    a key that merges two real seats."""
    with pytest.raises(collapse.ReservationVaries):
        collapse.to_seats(
            rows(("A", "X", "SC", "0", "10", "One"),
                 ("A", "X", "NONE", "0", "30", "Two")),
            KEY, vote_field="valid_vote")


def test_a_tie_leaves_the_winner_blank():
    """Two people cannot both have won, and a coin toss recorded as fact is
    worse than a gap. Bihar has four of these."""
    got = collapse.to_seats(
        rows(("A", "X", "SC", "0", "30", "One"),
             ("A", "X", "SC", "0", "30", "Two")),
        KEY, vote_field="valid_vote")
    assert got[0]["winner"] == ""
    assert got[0]["winner_basis"] == ""
    assert got[0]["seat_candidates"] == 2


def test_no_recorded_vote_is_not_zero_votes():
    """An uncontested seat and a seat nobody voted in are different things, and
    Bihar writes both. 24 of its seats carry no numeric vote at all."""
    got = collapse.to_seats(rows(("A", "X", "SC", "0", "--", "One")),
                            KEY, vote_field="valid_vote")
    assert got[0]["winner"] == ""
    assert collapse.votes_of("--") is None
    assert collapse.votes_of("0") == 0


def test_a_vote_count_with_a_tiebreak_note_still_reads():
    """Bihar writes one seat as "986+1 (BY LOT)"."""
    assert collapse.votes_of("986+1 (BY LOT)") == 986


def test_an_explicit_winner_marker_beats_counting_votes():
    """UP's 2021 file marks the winner, so nothing has to be inferred."""
    marked = rows(("A", "X", "SC", "0", "10", "One"),
                  ("A", "X", "SC", "0", "99", "Two"))
    marked[0]["result"] = "विजेता"
    marked[1]["result"] = "उपविजेता"
    got = collapse.to_seats(marked, KEY, vote_field="valid_vote",
                            winner_field="result", winner_value="विजेता")
    assert got[0]["winner"] == "One"
    assert got[0]["winner_basis"] == "published"


def test_two_marked_winners_fall_back_rather_than_guess():
    marked = rows(("A", "X", "SC", "0", "10", "One"),
                  ("A", "X", "SC", "0", "99", "Two"))
    marked[0]["result"] = marked[1]["result"] = "विजेता"
    got = collapse.to_seats(marked, KEY, vote_field="valid_vote",
                            winner_field="result", winner_value="विजेता")
    assert got[0]["winner"] == "Two"
    assert got[0]["winner_basis"] == "argmax_votes"


def test_seats_stay_separate_when_the_key_distinguishes_them():
    got = collapse.to_seats(
        rows(("A", "X", "SC", "0", "10", "One"),
             ("B", "X", "NONE", "0", "10", "Two")),
        KEY, vote_field="valid_vote")
    assert len(got) == 2


def test_varies_measures_without_raising():
    """For sizing a source before deciding how to treat it - Uttarakhand's nine
    disagreeing seats are a finding to look at, not a reason to refuse a state."""
    got = collapse.varies(
        rows(("A", "X", "SC", "0", "10", "One"),
             ("A", "X", "NONE", "0", "30", "Two"),
             ("A", "Y", "SC", "0", "10", "Three")),
        KEY)
    assert len(got) == 1
    assert ("A", "X") in got
