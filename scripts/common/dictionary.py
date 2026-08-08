"""What every column is supposed to look like.

One declaration per column, and it is the single source of truth for two things:
the expectations that get checked, and DICTIONARY.md, which is generated from
these entries. Documentation written separately from the rules it describes
drifts away from them - the readme in this repo did exactly that, twice.

The declarations are worth writing because every check in this repo up to now
was written to catch a problem someone had already hit. Declaring what a column
*should* be finds the ones nobody thought to look for: profiling against a first
draft of this file turned up an Andhra Pradesh ward count of 76 (the source says
at most 20), gram panchayat names holding "D. theemavaram 10 sr(w) sr(w)", and
Goa rows with no provenance at all.

`range` and `length` are the two that earn their keep. A column can be the right
type, non-blank, and still obviously wrong.
"""

import re

# Severity of a violated expectation.
ERROR, WARN, INFO = "error", "warn", "info"

# Reservation categories, after normalisation. BC covers Backward Class, BC(A)
# and OBC - the states do not agree on the name and the label does not carry
# enough to tell them apart.
CASTES = ["SC", "ST", "BC", "NONE"]

# The office a row is about. These states do not reserve the same one, which is
# why a pooled file without this column would silently compare different things.
TIERS = ["sarpanch", "mukhiya", "ward", "ward_member", "panchayat_samiti",
         "zila_parishad"]

RESERVATION_LABELS = [
    "Woman", "Other than Woman",
    "SC Woman", "SC Other than Woman",
    "ST Woman", "ST Other than Woman",
    "BC Woman", "BC Other than Woman",
]


def column(name, dtype, severity=ERROR, **kw):
    entry = {"name": name, "dtype": dtype, "severity": severity,
             "aliases": (), "required": False, "allowed": None, "pattern": None,
             "range": None, "length": None, "max_blank": None, "note": ""}
    entry.update(kw)
    return entry


COLUMNS = [
    # ----------------------------------------------------------- identity
    column("state", "string", required=True, length=(3, 30), max_blank=0.0,
           note="Printed name of the state or union territory."),
    column("year", "integer", required=True, range=(1990, 2030), max_blank=0.0,
           pattern=r"^\d{4}$",
           note="Election year. Four digits; a range would mean two cycles got "
                "merged into one file."),
    column("tier", "enum", required=True, allowed=TIERS, max_blank=0.0,
           note="Which office the seat is. Goa reserves wards and elects its "
                "sarpanch indirectly; Jharkhand reserves the mukhiya; Haryana "
                "the sarpanch; J&K 2016 gives both."),
    column("district", "string", length=(3, 30), max_blank=0.20,
           severity=WARN,
           note="J&K's 2010 files carry no district column at all, so a blank "
                "share above zero is expected there but not elsewhere."),
    column("block", "string", length=(2, 40), max_blank=0.35, severity=WARN,
           note="Block, taluka or mandal depending on the state."),

    # ------------------------------------------------------ the seat itself
    column("gram_panchayat", "string",
           aliases=("halqa",), length=(2, 45), max_blank=0.10,
           severity=WARN,
           note="The panchayat. Called halqa in J&K. Jharkhand printed it "
                "inside a compound seat identifier until that was taken apart; "
                "see seat_id_raw. A value far over the length bound has "
                "usually swallowed the next column - that is how AP's broken "
                "mandal split was found."),
    column("ward_no", "roman_or_integer", length=(1, 6), max_blank=0.30,
           severity=WARN,
           note="Blank on sarpanch and mukhiya rows by design. J&K and Goa "
                "number wards in Roman numerals, so this is not purely numeric."),
    column("ward_name", "string", length=(2, 40), max_blank=0.30, severity=WARN,
           note="J&K only."),

    # ------------------------------------------------------- the assignment
    column("caste_reservation", "enum", required=True, allowed=CASTES,
           max_blank=0.0,
           note="Orthogonal to woman_reserved: a seat can be both."),
    column("woman_reserved", "boolean", required=True, max_blank=0.0,
           note="1 if reserved for a woman."),
    column("reservation", "enum", required=True, allowed=RESERVATION_LABELS,
           max_blank=0.0,
           note="The two fields above, joined. Written separately from them, so "
                "it can disagree with them - which is checked as a row rule."),
    column("reservation_raw", "string", length=(1, 120), max_blank=0.0,
           note="The source cell, untouched, so any row can be audited."),
    column("listing_scope", "enum", allowed=["all_seats", "reserved_only"],
           severity=WARN,
           note="J&K's 2018 documents list only the reserved wards, so any "
                "share computed from them is a property of the document. Absent "
                "means all_seats."),

    # ------------------------------------------------------------ the person
    column("winner", "string", length=(2, 60), max_blank=0.60, severity=WARN,
           note="Only some states publish the elected member."),
    column("votes", "integer", range=(0, 100000), max_blank=0.60, severity=WARN,
           note="Goa 2012 only."),
    column("vacant", "boolean", max_blank=0.0, severity=WARN,
           note="Seat unfilled or the election countermanded. Official "
                "'elected' totals exclude these."),
    column("unopposed", "boolean", max_blank=0.0, severity=WARN,
           note="A '*' against the name in the source."),

    # ---------------------------------------------------- state-specific keys
    column("block_no", "integer", range=(1, 99), max_blank=0.90, severity=WARN),
    column("seat_no", "integer", range=(1, 999), max_blank=0.90, severity=WARN),
    column("serial", "integer", range=(1, 9999), max_blank=0.10, severity=WARN,
           note="AP's per-mandal running number; gaps in it mean lost rows."),
    column("halqa", "string", length=(2, 45), max_blank=0.10, severity=WARN),
    column("seat_id_raw", "string", length=(1, 90), max_blank=0.05,
           severity=INFO,
           note="Jharkhand. The seat identifier exactly as printed, before it "
                "was taken apart - a compound of district, block, gram "
                "panchayat and constituency number run together with @ and /. "
                "Kept because the split is the kind of thing worth being able "
                "to re-check against the page."),
    column("gp_no", "integer", range=(1, 99), max_blank=0.60, severity=WARN,
           note="The gram panchayat's number within its block, where the "
                "source states one."),

    # --------------------------------------------------------- J&K population
    column("pop_sc", "integer", range=(0, 100000), max_blank=0.90, severity=WARN,
           note="J&K prints the populations the allocation was based on, which "
                "is the only place in this repo the rule can be checked against "
                "its own inputs."),
    column("pop_st", "integer", range=(0, 100000), max_blank=0.90, severity=WARN),
    column("pop_oc", "integer", range=(0, 100000), max_blank=0.90, severity=WARN),
    column("pop_total", "integer", range=(0, 200000), max_blank=0.90,
           severity=WARN),

    # ------------------------------------------------------------- AP quality
    column("ward_count", "integer", range=(1, 20), max_blank=0.75,
           note="The number of wards the record itself states. The gazette "
                "header numbers ward columns 1 to 20, so anything above that is "
                "an OCR misread - 72 and 74 are 12 and 14 in this font. Blank "
                "for most of Andhra Pradesh because Anantapur's gazette is "
                "sarpanch-only and prints no ward column at all, which is why "
                "the blank tolerance is high."),
    column("wards_parsed", "integer", range=(0, 20), max_blank=0.0,
           severity=WARN),
    column("ward_list_complete", "boolean", max_blank=0.50, severity=WARN,
           note="1 when the ward list matches the stated count. Only about a "
                "third of AP's ward rows qualify, so a consumer should filter "
                "on this rather than assume."),
    column("ocr_repaired", "integer", range=(0, 2), max_blank=0.0, severity=WARN,
           note="How many mends the row's category cell needed. A wrong mend "
                "is indistinguishable from a right one, so these stay "
                "findable."),
    column("printings", "integer", range=(1, 4), max_blank=0.0, severity=WARN,
           note="How many times the gazette states this seat. Anantapur "
                "prints the sarpanch reservation in two proformas - a "
                "sarpanch-only list and the ward table's first column - so "
                "where both carry a seat this is 2 and validate.py checks that "
                "the two agree rather than assuming it."),
    column("printings_agree", "boolean", severity=WARN,
           note="Whether the gazette's separate statements of this seat say "
                "the same thing. Blank where the seat is stated only once - "
                "which is not the same as agreeing. Two independent "
                "typesettings agreeing is the strongest evidence available "
                "here that a row was read correctly."),
    column("text_source", "enum", allowed=["ocr", "embedded"], severity=INFO,
           note="Whether the row came from our own OCR or the PDF's embedded "
                "text layer, which for AP is itself faulty OCR."),

    # ------------------------------------------------------------ provenance
    column("script", "enum", allowed=["latin", "krutidev"], max_blank=0.0,
           note="Which typesetting the row was read from."),
    column("source_pdf", "string", required=True, length=(4, 80), max_blank=0.0),
    column("source_path", "path", required=True, max_blank=0.0,
           note="Relative to data/, and checked by opening it rather than by "
                "matching a pattern - a first attempt at a filename regex "
                "rejected 1,783 perfectly good Jharkhand rows because one file "
                "is called 'Gomia_GPS, GPM & GPVM.pdf'. What matters is that "
                "the document is there, not what it is called."),
    column("source_page", "integer", required=True, range=(1, 2000),
           max_blank=0.0),
]

BY_NAME = {c["name"]: c for c in COLUMNS}
ALIAS_OF = {alias: c["name"] for c in COLUMNS for alias in c["aliases"]}

# Plausible row counts per state and tier, as a band rather than a number - a
# file outside its band has either lost rows or double counted them.
ROW_BANDS = {
    ("Goa", "ward"): (400, 1800),
    ("Jharkhand", "mukhiya"): (1000, 4400),
    ("Jharkhand", "panchayat_samiti"): (1000, 5500),
    ("Jharkhand", "zila_parishad"): (50, 600),
    ("Jammu & Kashmir", "sarpanch"): (100, 4500),
    ("Jammu & Kashmir", "ward"): (500, 35000),
    ("Andhra Pradesh", "sarpanch"): (500, 13200),
}

ROMAN = re.compile(r"^[IVXLC]+$", re.I)
