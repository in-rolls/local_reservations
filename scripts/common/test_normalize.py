"""Every reservation string observed across the state corpora.

Each case here was taken from a real document. They are pinned because the
failure mode is silent: an unmatched spelling reads as an open seat, which is a
perfectly plausible value, so nothing raises and nothing looks wrong.
"""

import pytest

from normalize import (caste_of, is_krutidev, is_vacant, label,
                       normalize_reservation, strip_unopposed, woman_of)

# ---------------------------------------------------------------- Jharkhand
# Caste and gender sit in separate columns, so these are tested separately.
# "vuqlwfpr tutkfr" (janjati/ST) contains "tkfr" (jati/SC), and the corpus also
# splits it as "tu tkfr", so ST has to be decided before SC in both views.
JHARKHAND_CASTE = [
    ("vukjf{kr", "NONE"),          # anarakshit - unreserved
    ("vukfj{kr", "NONE"),          # same, misspelt
    ("vuqlwfpr tutkfr", "ST"),
    ("vuqlwfpr tu tkfr", "ST"),    # split mid-word
    ("vuqlwfpr tkfr", "SC"),
    ("vuqlwph tkfr", "SC"),
    ("vuqlqfpr tkfr", "SC"),
    ("vU; fiNM+k oxZ", "BC"),
    ("vU; foNMk oxZ", "BC"),
    ("fiNM+k oxZ", "BC"),
]

# ---------------------------------------------------------------- Goa codes
GOA = [
    ("General", "NONE", 0), ("Women", "NONE", 1), ("W", "NONE", 1),
    ("OBC", "BC", 0), ("O.B.C.", "BC", 0), ("O.B.C", "BC", 0),
    ("OBCW", "BC", 1), ("ST", "ST", 0), ("S.T.", "ST", 0), ("ST.", "ST", 0),
    ("STW", "ST", 1), ("SC", "SC", 0),
]

# ------------------------------------------------- Andhra Pradesh OCR codes
AP = [
    ("UR", "NONE", 0), ("UR (W)", "NONE", 1), ("UR(W)", "NONE", 1),
    ("SC", "SC", 0), ("sc (w)", "SC", 1), ("BC", "BC", 0),
    ("Bc (w)", "BC", 1), ("ST", "ST", 0),
]

# ------------------------------------------------------- Haryana, unchanged
HARYANA = [
    ("Women", "NONE", 1),
    ("Other than Women", "NONE", 0),
    ("Scheduled Caste Other than Women", "SC", 0),
    ("Backward Class 'A' Women", "BC", 1),
    ("Unreserved", "NONE", 0),
    ("Scheduled Caste", "SC", 0),
    ("Scheduled Class (Women)", "SC", 1),      # "Class" is Caste misspelt
    ("Seheduled Caste Women", "SC", 1),        # c -> e typo
    ("Scheduled Cast e Women", "SC", 1),       # stray space inside the word
    ("Sc Women", "SC", 1),
    ("BC (A) Other than Women", "BC", 0),
    ("efgyk", "NONE", 1),
    ("efgyk ds flok;", "NONE", 0),
    ("vuqlwfpr tkfr efgyk", "SC", 1),
    ("vuqlwfpr tkfr efgyk ds flok;", "SC", 0),
    ("eefgyk ds fll ok;", "NONE", 0),          # doubled chars, split word
    ("ljiap vuqlwfpr tkfr efgyk ds", "SC", 0),  # truncated to trailing "ds"
    ("fiN+Mk oxZ d efgyk", "BC", 1),           # floating "+" diacritic
]

NON_CATEGORIES = ["", None, "Sarpanch", "Panch", "iap", "5", "--", "Independent"]


@pytest.mark.parametrize("raw,caste", JHARKHAND_CASTE)
def test_jharkhand_caste_column(raw, caste):
    assert caste_of(raw) == caste


def test_jharkhand_gender_column():
    assert woman_of("efgyk") == 1
    assert woman_of("vU;") == 0


@pytest.mark.parametrize("raw,caste,woman", GOA + AP + HARYANA)
def test_single_cell_states(raw, caste, woman):
    result = normalize_reservation(raw)
    assert result is not None, f"{raw!r} was not recognised as a category"
    assert result[:2] == (caste, woman)
    assert result[2] == ("krutidev" if is_krutidev(raw) else "latin")


@pytest.mark.parametrize("raw", NON_CATEGORIES)
def test_rejects_non_categories(raw):
    assert normalize_reservation(raw) is None


def test_wrapped_cell_is_whitespace_insensitive():
    """pdfplumber joins a wrapped cell with a newline; that must not matter."""
    assert normalize_reservation("Scheduled Caste\nOther than Women") == ("SC", 0, "latin")
    assert normalize_reservation("vuqlwfpr tkfr efgyk\nds flok;") == ("SC", 0, "krutidev")


def test_script_detection():
    assert is_krutidev("vuqlwfpr tkfr efgyk")
    assert is_krutidev("efgyk")
    assert not is_krutidev("Scheduled Caste Women")
    assert not is_krutidev("OBCW")


def test_labels():
    assert label("NONE", 1) == "Woman"
    assert label("NONE", 0) == "Other than Woman"
    assert label("SC", 1) == "SC Woman"
    assert label("ST", 0) == "ST Other than Woman"
    assert label("BC", 1) == "BC Woman"


def test_unopposed_and_vacant():
    assert strip_unopposed("*Sunita Rani") == ("Sunita Rani", True)
    assert strip_unopposed("Sunita Rani") == ("Sunita Rani", False)
    assert is_vacant("Vacant") and is_vacant("fjDr in") and is_vacant("")
    assert not is_vacant("Sunita Rani")
