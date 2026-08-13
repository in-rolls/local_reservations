"""Turn a state's rows into the pooled schema.

The master's point is that you can group by it, so its columns are fixed and
declared rather than a union of whatever each state happens to carry. The 23
state-specific extras stay out and go to master_extras.parquet long-form, so nothing
is lost and the table does not become mostly blank.

**What is deliberately not carried.** Three sources publish contact details for
named individuals - Bihar a mobile number, postal address and email for each of
645,605 candidates, Kerala an address, phone, mobile and photograph for each of
its 65,296 elected members, Uttar Pradesh 2010 an address. Those columns are
read and dropped, and this is the one place in the repository where dropping
data is not a defect to be fixed. Everything else a source states about a person
is kept: name, relation, gender, age, caste, education, occupation, marital
status, party, votes.

**A reservation is a property of the seat, never of the person who won it.**
`caste_reservation` and `woman_reserved` say what the seat was reserved for.
The winner's own category and gender are `winner_caste` and `winner_gender` on a
seat row, and `candidate_caste` and `candidate_gender` in the candidate table.
They are different facts and the data says so: Uttar Pradesh 2005 states both,
and they agree on 19,324 of 51,872 rows. A scheduled-caste person winning an
unreserved seat is the thing most of these data exist to measure, and collapsing
the two columns would delete it.

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

from local_reservations.common import canon, dictionary, reference

MASTER_COLUMNS = [
    # grain
    "dataset_id", "row_id", "seat_key", "seat_key_unique",
    # place
    "state", "year", "district", "block", "gram_panchayat", "gp_term",
    "ward_no", "ward_name", "seat_no",
    # office
    "tier", "tier_local",
    # reservation
    "caste_reservation", "caste_reservation_local", "caste_scheme",
    "woman_reserved", "reservation", "reservation_raw", "listing_scope",
    # what a row is
    "unit_of_observation", "seat_candidates",
    # who won, and - where the source states a contest rather than a seat -
    # who came second and by how much. These are facts about the seat, so they
    # belong here; the full field of candidates is a fact about the contest and
    # lives in the candidate table.
    "winner", "winner_basis", "votes", "runner_up", "runner_up_votes",
    "margin", "vacant", "unopposed",
    # provenance
    "script", "source_repo", "source_commit", "source_path", "source_page",
    "provenance_level", "quality_flags",
]

# Columns that the master carries under its own name, so an adapter's leftovers
# can be identified as extras rather than silently dropped.
CARRIED = set(MASTER_COLUMNS) | {"halqa", "gender_stated", "seat_members",
                                 "winner_votes"}

# The long form, and a table in its own right rather than an appendage. Four of
# the sources state a contest, not a seat: every candidate who stood, what they
# polled, and who they were. That is a different unit of observation, not a
# lesser one, so it gets its own declared schema, its own files, its own row
# identifiers and its own place in the manifest.
#
# It carries place and office rather than only a join key, so it can be read on
# its own without reconstructing the seat first, and it carries the seat's
# reservation so the obvious question - who contests a seat reserved for whom -
# is answerable in one table. `row_id` joins it back to the wide one.
CANDIDATE_COLUMNS = [
    # grain
    "dataset_id", "candidate_id", "row_id", "seat_key", "candidate_no",
    # place
    "state", "year", "district", "block", "gram_panchayat", "ward_no",
    "seat_no",
    # office
    "tier", "tier_local",
    # what the seat was reserved for, so the long form stands on its own
    "caste_reservation", "woman_reserved",
    # who stood
    "candidate_name", "relation_name", "candidate_gender", "candidate_woman",
    "candidate_age", "candidate_caste", "candidate_education", "party",
    # how they did
    "votes", "candidate_rank", "elected", "result",
    # provenance, the same as the seat it belongs to
    "source_repo", "source_commit", "source_path", "source_page",
]

# What an adapter supplies per candidate. Everything else on a candidate row is
# copied from the seat it belongs to, so an adapter states each fact once.
CANDIDATE_FIELDS = [
    "candidate_name", "relation_name", "candidate_gender", "candidate_woman",
    "candidate_age", "candidate_caste", "candidate_education", "party",
    "votes", "candidate_rank", "elected", "result",
]

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
    # the source stated this contest twice, with vote counts that disagree
    if str(row.get("duplicate_candidacy") or "0") not in ("0", ""):
        flags.append("duplicate_candidacy")
    # one serial number carrying two different candidates, unresolvable
    if str(row.get("serial_not_unique") or "0") not in ("0", ""):
        flags.append("serial_not_unique")
    # two places in one block printed under one name, told apart only by the
    # fact that they are reserved differently
    if str(row.get("shared_place_name") or "0") not in ("0", ""):
        flags.append("shared_place_name")
    if row.get("script") in ("krutidev", "devanagari"):
        flags.append("name_untransliterated")
    return ";".join(flags)


def gp_term(row):
    """Which word the source used for the panchayat, since the master keeps one
    column and the term itself is information about the state.
    """
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
        # A block or district seat is numbered within its body and has no
        # panchayat, so this is the whole of its identity. It was named in
        # SEAT_FIELDS but never in MASTER_COLUMNS, so every seat key was built
        # with an empty slot where it belonged and Jharkhand's 181 zila
        # parishad seats all collided with each other.
        "seat_no": row.get("seat_no", ""),
        "tier": tier, "tier_local": row.get("tier_local", ""),
        "caste_reservation": row.get("caste_reservation", ""),
        "caste_reservation_local": local,
        "caste_scheme": canon.caste_scheme(state) or "",
        "woman_reserved": row.get("woman_reserved", ""),
        "reservation": row.get("reservation", ""),
        "reservation_raw": row.get("reservation_raw", ""),
        # The row's own value first, then what reference declares for the
        # slice, and only then the convention. Writing "all_seats" without
        # asking reference overwrote Goa 2017 and 2022 - declared partial
        # listings - and the statutory check then measured half a roster
        # against the statute and failed a state that had done nothing wrong.
        "listing_scope": (row.get("listing_scope")
                          or reference.listing_scope(state, row.get("year", ""),
                                                     tier)),
        "unit_of_observation": unit_of_observation,
        "seat_candidates": seat_candidates,
        "winner": row.get("winner", ""),
        "winner_basis": row.get("winner_basis", ""),
        # winner_votes where a collapse worked it out, votes where the source
        # stated it directly against the seat
        "votes": row.get("winner_votes") or row.get("votes", ""),
        "runner_up": row.get("runner_up", ""),
        "runner_up_votes": row.get("runner_up_votes", ""),
        "margin": row.get("margin", ""),
        "vacant": row.get("vacant", ""),
        "unopposed": row.get("unopposed", ""),
        "script": row.get("script", ""),
        "source_repo": source_repo, "source_commit": source_commit,
        "source_path": row.get("source_path", ""),
        "source_page": row.get("source_page", ""),
        "provenance_level": provenance_level,
    }
    out["quality_flags"] = quality_flags(dict(row, **out))
    out["seat_key"] = seat_key(dict(row, gram_panchayat=out["gram_panchayat"]))
    # Every value is a string, as it will be once written. An adapter that sets
    # woman_reserved to the integer 1 produces a row that behaves differently
    # in memory than after a round trip through the CSV, and the checks - which
    # were written against rows read back from disk - then fail on .strip().
    return {k: "" if v is None else str(v) for k, v in out.items()}


def candidates(row, seat):
    """The long-form rows for one seat, in the candidate schema.

    `row` is the adapter's row, which carries `seat_members`; `seat` is the
    finished master row, which carries the place, the office, the reservation
    and the provenance. Each is stated once and copied here, so the two tables
    cannot drift from each other.

    A seat-level source contributes nothing and that is not a gap - Haryana
    states seats, so there are no candidates to state.
    """
    shared = {c: seat.get(c, "") for c in CANDIDATE_COLUMNS if c in seat}
    out = []
    for position, member in enumerate(row.get("seat_members") or (), 1):
        got: dict[str, object] = dict(shared, candidate_no=position,
                                      row_id=seat.get("row_id", ""))
        got.update({c: member.get(c, "") for c in CANDIDATE_FIELDS})
        got["candidate_id"] = hashlib.sha1(
            f"{seat.get('row_id', '')}|{position}".encode()
        ).hexdigest()[:12]
        out.append({c: "" if got.get(c) is None else str(got.get(c, ""))
                    for c in CANDIDATE_COLUMNS})
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
