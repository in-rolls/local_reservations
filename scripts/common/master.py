"""Turn a state's rows into the pooled schema.

The master's point is that you can group by it, so its columns are fixed and
declared rather than a union of whatever each state happens to carry. The 23
state-specific extras stay out and go to master_extras.csv long-form, so nothing
is lost and the table does not become mostly blank.

Three columns exist because one could not carry the fact:

  tier / tier_local              the same office is printed under different
                                 names, and the same name means different
                                 offices - see canon.py
  caste_reservation / _local /   the fold to BC is lossy and not the same fold
  caste_scheme                   in every state, so the local label and the
                                 regime are both kept
  unit_of_observation /          three sources are candidate-level and get
  seat_candidates                collapsed to seats; a row that came from a
                                 collapse has to say so

The grain is **one row per seat as a source document states it**, which is not
the same as one row per seat. 1,435 rows in the current corpus do not identify a
distinct seat, so `seat_key_unique` is a column and the collisions are exported
rather than hidden behind a claim the data does not support.
"""

import hashlib

import canon
import dictionary

MASTER_COLUMNS = [
    # grain
    "dataset_id", "row_id", "seat_key", "seat_key_unique",
    # place
    "state", "year", "district", "block", "gram_panchayat", "gp_term",
    "ward_no", "ward_name",
    # office
    "tier", "tier_local",
    # reservation
    "caste_reservation", "caste_reservation_local", "caste_scheme",
    "woman_reserved", "reservation", "reservation_raw", "listing_scope",
    # what a row is
    "unit_of_observation", "seat_candidates",
    # person
    "winner", "winner_basis", "votes", "vacant", "unopposed",
    # provenance
    "script", "source_repo", "source_commit", "source_path", "source_page",
    "provenance_level", "quality_flags",
]

# Columns that the master carries under its own name, so an adapter's leftovers
# can be identified as extras rather than silently dropped.
CARRIED = set(MASTER_COLUMNS) | {"halqa", "gender_stated"}

SEAT_FIELDS = ["state", "year", "tier", "district", "block", "gram_panchayat",
               "ward_no", "seat_no"]


def seat_key(row):
    return "|".join((row.get(f) or "").strip() for f in SEAT_FIELDS)


def row_id(row, occurrence):
    """A stable identifier for a row.

    Built from where the row came from plus its seat key plus which occurrence
    it is, so it survives a rebuild and changes when the provenance changes.
    `occurrence` disambiguates rows that a source states more than once, which
    it does - the key alone is not unique.
    """
    material = "|".join([
        row.get("source_repo", ""), row.get("source_path", ""),
        str(row.get("source_page", "")), seat_key(row), str(occurrence),
    ])
    return hashlib.sha1(material.encode("utf-8")).hexdigest()[:12]


def quality_flags(row):
    """What a consumer should know about this row before trusting it."""
    flags = []
    if str(row.get("ocr_repaired") or "0") not in ("0", ""):
        flags.append("ocr_repaired")
    if row.get("printings_agree") == "0":
        flags.append("printings_disagree")
    if row.get("ward_list_complete") == "0":
        flags.append("ward_list_incomplete")
    # woman_reserved is 0 by default where the marker did not survive the scan,
    # so a row whose gender was never stated is a guess, not a reading
    if row.get("gender_stated") == "0":
        flags.append("gender_not_stated")
    if row.get("winner_basis") == "argmax_votes":
        flags.append("winner_inferred")
    if row.get("script") in ("krutidev", "devanagari"):
        flags.append("name_untransliterated")
    return ";".join(flags)


def gp_term(row):
    """Which word the source used for the panchayat, since the master keeps one
    column and the term itself is information about the state."""
    for column in canon.UNIT_COLUMNS:
        if (row.get(column) or "").strip():
            return column
    return ""


def to_master(row, dataset_id, source_repo, source_commit, provenance_level,
              unit_of_observation="seat", seat_candidates=""):
    """One parsed row in the pooled schema. Returns None for an urban seat."""
    state = row.get("state", "")
    tier = row.get("tier", "")
    if not canon.is_rural(tier):
        return None

    local = row.get("caste_reservation_local") or row.get("caste_reservation", "")
    out = {
        "dataset_id": dataset_id,
        "state": state, "year": row.get("year", ""),
        "district": row.get("district", ""), "block": row.get("block", ""),
        "gram_panchayat": canon.unit_name(row), "gp_term": gp_term(row),
        "ward_no": row.get("ward_no", ""), "ward_name": row.get("ward_name", ""),
        "tier": tier, "tier_local": row.get("tier_local", ""),
        "caste_reservation": row.get("caste_reservation", ""),
        "caste_reservation_local": local,
        "caste_scheme": canon.caste_scheme(state) or "",
        "woman_reserved": row.get("woman_reserved", ""),
        "reservation": row.get("reservation", ""),
        "reservation_raw": row.get("reservation_raw", ""),
        # absent means all_seats by convention everywhere but J&K, and a
        # convention that lives only in a docstring is one nobody can filter on
        "listing_scope": row.get("listing_scope") or "all_seats",
        "unit_of_observation": unit_of_observation,
        "seat_candidates": seat_candidates,
        "winner": row.get("winner", ""),
        "winner_basis": row.get("winner_basis", ""),
        "votes": row.get("votes", ""), "vacant": row.get("vacant", ""),
        "unopposed": row.get("unopposed", ""),
        "script": row.get("script", ""),
        "source_repo": source_repo, "source_commit": source_commit,
        "source_path": row.get("source_path", ""),
        "source_page": row.get("source_page", ""),
        "provenance_level": provenance_level,
    }
    out["quality_flags"] = quality_flags(dict(row, **out))
    out["seat_key"] = seat_key(dict(row, gram_panchayat=out["gram_panchayat"]))
    return out


def extras(row, row_id_value):
    """The state-specific columns, long-form.

    Widening the master to a sparse union of every state's extras is the thing
    to avoid; dropping them is worse. This keeps ward_count, printings_agree,
    pop_sc and the rest recoverable by a join on row_id.
    """
    out = []
    for column, value in row.items():
        if column in CARRIED or not str(value or "").strip():
            continue
        if column not in dictionary.BY_NAME:
            continue
        out.append({"row_id": row_id_value, "column": column,
                    "value": str(value)})
    return out
