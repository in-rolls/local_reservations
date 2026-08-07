"""Read a reservation label, whatever shape the state prints it in.

Generalised from local_elections_haryana/scripts/normalize.py. Every state
publishes the same two facts - which caste category a seat is reserved for, and
whether it is reserved for a woman - but no two print them alike:

    Haryana    "Scheduled Caste Other than Women", or Kruti Dev
               "vuqlwfpr tkfr efgyk ds flok;"
    Goa        codes in one cell: G, ST, OBC, W, OBCW, STW
    Jharkhand  two separate columns: "vuqlwfpr tutkfr" and "efgyk"/"vU;"
    J&K        "Open", "Women", "SC", "ST", "OC"
    Andhra     OCR'd codes: UR, SC, BC, ST, with "(W)" - and "5C", "8c"

So the module exposes the two facts separately - caste_of() and woman_of() -
and normalize_reservation() for the states that print both in one cell. States
whose caste and gender live in different columns call the two directly.

Output is always caste_reservation in {SC, ST, BC, NONE} and woman_reserved in
{0, 1}. BC covers Backward Class, BC(A) and OBC; the states do not agree on the
name and the distinction is not recoverable from the label anyway.

The failure mode this guards against is not an exception. An unmatched spelling
silently downgrades a reserved seat to an open one, which looks entirely
plausible in the output. That is why matching is deliberately loose and why
every observed string is pinned in test_normalize.py.
"""

import re
import unicodedata

# --------------------------------------------------------------- Kruti Dev
# Legacy font encoding, byte-for-byte deterministic rather than OCR guesses.
# "anusuchit" is spelt at least a dozen ways across Haryana and Jharkhand, so it
# is matched as "vuq + anything + jati" rather than by literal.
KD_SC = re.compile(r"vuq\S*\s+tkfr")            # anusuchit jati
KD_ST = re.compile(r"vuq\S*\s+tu\s*tkfr")       # anusuchit janjati
KD_SC_TIGHT = re.compile(r"vuq\w*tkfr")
KD_ST_TIGHT = re.compile(r"vuq\w*tutkfr")
KD_BC = re.compile(r"f[io]NM|fiNM")             # pichhda varg, and its typos
KD_UNRESERVED = re.compile(r"vuk[fj]+\{kr")     # anarakshit, incl. "vukfj{kr"
KD_WOMAN = "efgyk"                              # mahila
KD_OTHER = "vU;"                                # anya - the "not a woman" cell
KD_OTHER_THAN = "flok;"                         # sivay - "other than"

VACANT = ("rikt", "riet", "vacant", "fjDr", "[kkyh")

# ------------------------------------------------------------- short codes
# Goa, Andhra and J&K print codes rather than phrases. Matched on the
# letters-only form, so "O.B.C.", "OBC" and "Obc" all land here, and so does
# "UR (W)" -> "urw".
CODES = {
    "g": ("NONE", 0), "gen": ("NONE", 0), "general": ("NONE", 0),
    "ur": ("NONE", 0), "unreserved": ("NONE", 0), "open": ("NONE", 0),
    "oc": ("NONE", 0), "o": ("NONE", 0),
    "w": ("NONE", 1), "women": ("NONE", 1), "woman": ("NONE", 1),
    "gw": ("NONE", 1), "genw": ("NONE", 1), "generalw": ("NONE", 1),
    "urw": ("NONE", 1), "openw": ("NONE", 1), "ocw": ("NONE", 1),
    "sc": ("SC", 0), "scw": ("SC", 1), "scwomen": ("SC", 1),
    "st": ("ST", 0), "stw": ("ST", 1), "stwomen": ("ST", 1),
    "bc": ("BC", 0), "bcw": ("BC", 1), "bcwomen": ("BC", 1),
    "obc": ("BC", 0), "obcw": ("BC", 1), "obcwomen": ("BC", 1),
    "bca": ("BC", 0), "bcaw": ("BC", 1),
}


def _squash(s):
    """Collapse whitespace and fold the apostrophe variants together."""
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("‘", "'").replace("’", "'").replace("‛", "'")
    return re.sub(r"\s+", " ", s).strip()


def _undouble(s):
    """Collapse runs of a repeated character to one.

    Some notifications are typeset with every character doubled - "vuqllwfpr"
    for "vuqlwfpr", whole lines as "EEXXTTRRAAOORRDDIINNAARRYY". None of the
    strings matched here contain a genuine doubled character, so collapsing runs
    is safe and makes the match survive it.
    """
    return re.sub(r"(.)\1+", r"\1", s)


def _kd_forms(s):
    """The two Kruti Dev views: run-collapsed, and also space-stripped.

    Words arrive split by stray spaces ("fll ok;" for "flok;", "tu tkfr" for
    "tutkfr"), and "+" is a diacritic that floats position, so "fiNM+k" is also
    typeset "fiN+Mk". Both views are tried against every pattern.
    """
    return _undouble(s).replace("+", ""), _undouble(re.sub(r"[\s+]", "", s))


def is_krutidev(text):
    kd, tight = _kd_forms(_squash(text))
    return bool(KD_WOMAN in kd or KD_WOMAN in tight or KD_OTHER in kd
                or KD_UNRESERVED.search(kd) or KD_SC_TIGHT.search(tight))


def caste_of(text):
    """SC / ST / BC / NONE, or None when the cell says nothing about caste."""
    s = _squash(text)
    if not s:
        return None
    kd, tight = _kd_forms(s)

    # Scheduled Tribe must be tested before Scheduled Caste: "vuqlwfpr tutkfr"
    # (janjati) contains "tkfr" (jati), so an SC test would claim it first.
    if KD_ST.search(kd) or KD_ST_TIGHT.search(tight):
        return "ST"
    if KD_SC.search(kd) or KD_SC_TIGHT.search(tight):
        return "SC"
    if KD_BC.search(kd) or KD_BC.search(tight):
        return "BC"
    if KD_UNRESERVED.search(kd) or KD_UNRESERVED.search(tight):
        return "NONE"

    letters = re.sub(r"[^a-z]", "", s.lower())
    if letters in CODES:
        return CODES[letters][0]

    # Phrase form. Key on the head noun, not the qualifier: "Scheduled Caste"
    # also appears as "Schedule Cast", "Schedulded Caste" and "Seheduled
    # Caste", so chasing the qualifier means chasing each new misspelling.
    # "sched" decides it even when the noun is wrong - the 2016 Haryana gazette
    # prints "Scheduled Class", which is Caste misspelt, not Backward Class.
    tokens = {re.sub(r"[^a-z]", "", t) for t in s.lower().split()}
    if "trib" in letters or "st" in tokens:
        return "ST"
    if "cast" in letters or "sched" in letters or "sc" in tokens:
        return "SC"
    if "clas" in letters or "back" in letters or tokens & {"bc", "obc", "bca"}:
        return "BC"
    if "unreserv" in letters or "general" in letters or "open" in letters:
        return "NONE"
    return None


def woman_of(text):
    """1 if reserved for a woman, 0 if explicitly not, None if the cell is silent.

    Note the asymmetry: "efgyk" alone means woman, but "efgyk ds flok;" means
    *other than* woman, so the negation has to be checked first.
    """
    s = _squash(text)
    if not s:
        return None
    kd, tight = _kd_forms(s)

    if KD_OTHER_THAN in kd or KD_OTHER_THAN in tight:
        return 0
    # a label truncated mid-phrase to a trailing "ds" is still "ke sivay":
    # that word occurs nowhere else in this vocabulary
    if kd.rstrip().endswith(" ds") or tight.endswith("ds"):
        return 0
    if KD_WOMAN in kd or KD_WOMAN in tight:
        return 1
    if KD_OTHER in kd or KD_OTHER in tight:
        return 0

    letters = re.sub(r"[^a-z]", "", s.lower())
    if letters in CODES:
        return CODES[letters][1]
    if "wom" in letters:
        return 0 if "otherthan" in letters else 1
    if "unreserv" in letters or "general" in letters or "open" in letters:
        return 0
    return None


def normalize_reservation(raw):
    """For states that print caste and gender in one cell.

    Returns (caste, woman, script) or None. States with separate columns should
    call caste_of() and woman_of() directly instead.
    """
    s = _squash(raw)
    if not s:
        return None
    script = "krutidev" if is_krutidev(s) else "latin"

    caste = caste_of(s)
    woman = woman_of(s)
    if caste is None and woman is None:
        return None
    # A bare caste name with no gender marker means caste-reserved but open to
    # anyone - that is how the 2016 gazettes write it.
    return caste or "NONE", woman if woman is not None else 0, script


def is_vacant(name):
    """True when nobody holds the seat - unfilled, or the election was
    countermanded. Official "elected" totals exclude these."""
    # Both sides are lowercased. Kruti Dev is case-sensitive mojibake, so
    # folding only one side silently stops "fjDr" from ever matching.
    n = _squash(name).lstrip("*").strip().lower()
    return not n or any(n.startswith(v.lower()) for v in VACANT)


def strip_unopposed(name):
    """A leading '*' marks a candidate elected unopposed."""
    n = _squash(name)
    return n.lstrip("*").strip(), n.startswith("*")


def label(caste, woman):
    """Canonical human-readable label."""
    prefix = {"SC": "SC", "ST": "ST", "BC": "BC", "NONE": ""}[caste or "NONE"]
    suffix = "Woman" if woman else "Other than Woman"
    return f"{prefix} {suffix}".strip()
