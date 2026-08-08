"""Andhra Pradesh's line layouts, pinned to real gazette lines.

AP is read positionally, and the districts do not agree on the positions -
neither does Krishna with itself, whose pages 12 and 13 put the ward count on
opposite sides of the sarpanch's own cell. Every case here is a line copied out
of a gazette, because each one of these got parsed plausibly and wrongly first:

  - Anantapur's mandal and panchayat came out as the same string
  - Nellore's revenue division was glued to the front of the mandal
  - Krishna's Pinapaka was recorded "Other than Woman" when the page says UR(W),
    because "uUR(W)" failed to match and the parser took ward 1's code instead
  - Nellore lost one ward on a quarter of its records to codes like "JUR(W)"

None of those raised. They are pinned so they cannot come back quietly.
"""

import pytest

import parsers

ap = parsers.load("ap")
apply_layout, as_category = ap.apply_layout, ap.as_category
mandal_vocabulary, recover_wards = ap.mandal_vocabulary, ap.recover_wards
scan_line, split_names = ap.scan_line, ap.split_names


# ------------------------------------------------------------ damaged codes

DAMAGED = [
    ("UR(W)", "UR(W)"),
    ("uUR(W)", "UR(W)"),        # Krishna p13, a doubled leading letter
    ("JUR(W)", "UR(W)"),        # Nellore, a table rule read as a J
    ("sccw)", "SC(W)"),         # the bracket read as a c
    ("SC (G)", "SC(G)"),
    ("sc", "SC"),
    ("Bc(w)", "BC(W)"),
]


@pytest.mark.parametrize("raw,expected", DAMAGED)
def test_recognises_a_damaged_code(raw, expected):
    assert as_category(raw) == expected


NOT_A_CODE = ["Amancherla", "Agali", "Kunavaram", "Buchireddypalem", ""]


@pytest.mark.parametrize("raw", NOT_A_CODE)
def test_a_place_name_is_not_a_code(raw):
    """The layout test turns on this: a name after the number means Nellore's
    panchayat index, a code after it means Krishna's count-first order."""
    assert as_category(raw) is None


# ------------------------------------------------------------- line layouts

def parsed(line):
    record = scan_line(line)
    assert record is not None, line
    return apply_layout(record)


def test_krishna_sarpanch_before_count():
    """Krishna p12: mandal, panchayat, SARPANCH, count, wards."""
    row = parsed("1 |Ghantasala Atchampalem UR 8 SC(W) | UR(W) | UR(W) UR "
                 "UR(W) | UR UR UR")
    assert row["sarpanch_raw"].strip() == "UR"
    assert row["ward_count"] == "8"
    assert len(row["ward_raws"]) == 8


def test_krishna_count_before_sarpanch():
    """Krishna p13, the same document, the other way round."""
    row = parsed("1 |G.Konduru Atkuru 8 UR(W) | UR(W) UR UR(w) sc UR sc(w) "
                 "sc sc(w)")
    assert row["sarpanch_raw"].strip() == "UR(W)"
    assert row["ward_count"] == "8"
    assert len(row["ward_raws"]) == 8


def test_krishna_damaged_sarpanch_is_not_ward_ones_code():
    """The bug this cost: "uUR(W)" does not match, so the first code the
    scanner sees belongs to ward 1, and the sarpanch silently takes it."""
    row = parsed("17 |G.Konduru _—|Pinapaka 10 | uUR(W)| UR | UR(W)| UR | "
                 "UR(W)| SC(W)} SC sc |sccw)|sc(w)| UR")
    assert row["sarpanch_raw"] == "UR(W)"
    assert row["code_repaired"] == 1
    assert row["ward_count"] == "10"


def test_nellore_index_marks_the_name_boundary():
    row = parsed("41 |Nellore Nellore Rural 1 |Amancherla ST(W) 14 UR(G) | "
                 "UR(G) | UR(G) |SC(W) ST(W) |ST(G) | UR(G) |SC(G) ST(W) "
                 "|SC(W)")
    assert row["place"] == "Nellore Nellore Rural"
    assert row["panchayat"] == "Amancherla"
    assert row["sarpanch_raw"] == "ST(W)"
    assert row["ward_count"] == "14"


def test_anantapur_has_no_boundary_in_the_line():
    """Both names are Title Case and there is no number, so the line alone
    cannot be split - split_names() does it from the record order."""
    row = parsed("2 Agali H.D.Halli UR(G)")
    assert row["place"] == "Agali H.D.Halli"
    assert row["panchayat"] == ""


# ------------------------------------------------- learning the mandal names

def test_mandal_is_one_word_when_the_second_varies():
    names = ["Atmakur B.Yaleru", "Atmakur Goridindla", "Atmakur Muttala",
             "Atmakur Talupur"]
    assert mandal_vocabulary(names)["atmakur"] == "Atmakur"
    assert "atmakur b.yaleru" not in mandal_vocabulary(names)


def test_mandal_is_two_words_when_every_record_repeats_both():
    names = ["Anantapur Rural Bandlapalli", "Anantapur Rural Itukalapalli",
             "Anantapur Rural Kondampalli", "Anantapur Rural Marur"]
    assert mandal_vocabulary(names)["anantapur rural"] == "Anantapur Rural"


def test_three_hamlets_do_not_invent_a_two_word_mandal():
    """Consecutive records sharing two words look exactly like a two-word
    mandal from close up. Only the records that do *not* share the second word
    settle it, which is why the vocabulary is built over the whole document."""
    names = ["Pamidi Ramagiri", "Pamidi Ramagiri Thanda", "Pamidi Ramagiri X",
             "Pamidi Kothapalli", "Pamidi Somalapuram"]
    assert mandal_vocabulary(names)["pamidi"] == "Pamidi"
    assert "pamidi ramagiri" not in mandal_vocabulary(names)


def test_split_names_uses_the_whole_document():
    records = [{"place": p, "panchayat": "", "mandal": ""} for p in
               ["Kalyandurg Garudapuram", "Kalyandurg Golla",
                "Kalyandurg Hulikal", "Agali Agali"]]
    split_names(records)
    assert [r["mandal"] for r in records[:3]] == ["Kalyandurg"] * 3
    assert [r["panchayat"] for r in records[:3]] == ["Garudapuram", "Golla",
                                                     "Hulikal"]
    # a panchayat named after its own mandal keeps the name in both columns
    assert (records[3]["mandal"], records[3]["panchayat"]) == ("Agali", "Agali")


def test_revenue_division_is_dropped_only_when_it_spans_mandals():
    records = [{"place": p, "panchayat": "x", "mandal": ""} for p in
               ["Nellore Nellore Rural", "Nellore Kodavalur", "Nellore Podalakur",
                "Nellcre Podalakur", "Gudur Chillakur"]]
    split_names(records)
    assert [r["mandal"] for r in records] == [
        "Nellore Rural", "Kodavalur", "Podalakur",
        # a division whose own name is misread still heads a place string
        "Podalakur",
        # ...but a division seen only once is not one, so this keeps both words
        "Gudur Chillakur"]


# ------------------------------------------------------- recovering a ward

def test_recovers_only_as_many_wards_as_are_declared_missing():
    region = " 8 UR(G) JUR(W) UR(W)"
    spans = [(3, 9), (17, 22)]
    assert [c for _, c in recover_wards(region, spans, 1)] == ["UR(W)"]


def test_recovers_nothing_when_more_candidates_than_are_missing():
    """More candidates than the shortfall means the shortfall is not
    understood, and guessing which to take would be worse than leaving it."""
    assert recover_wards(" JUR(W) JSC(G) JBC(W)", [], 1) == []


def test_never_reads_a_ward_out_of_a_place_name():
    """With the word boundary relaxed, "Surareddypalem" contains UR. Nothing is
    recovered from a region that is only a name."""
    assert recover_wards(" Surareddypalem Thakur", [], 3) == []
