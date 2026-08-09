"""The cross-state vocabulary: what an office is, and what a caste category means.

States print the same office under different names and different offices under
the same name. Pooling on the printed name is therefore not a naming
inconvenience, it is a correctness problem, and it fails silently - the row
counts stay plausible either way.

The one that proves it: **Bihar's "Sarpanch" is not the head of the gram
panchayat.** It heads the *gram kachahari*, the village court, which is a
separate elected body sharing the same geography. Bihar's gram panchayat head is
the Mukhiya. 7,849 panchayats hold both contests, and 88,868 wards hold both a
panch and a ward-member contest. Map Bihar's sarpanch onto Haryana's and a
pooled count of gram panchayat heads gains 7,849 seats that are not gram
panchayat heads at all - a 6% overstatement with nothing anywhere to flag it.

So every row carries two columns: `tier`, the canonical office, and
`tier_local`, the name the state actually printed. Nothing is lost, and anyone
who wants to group by the local vocabulary still can.
"""

import re

import dictionary

# The canonical offices, with the body each belongs to.
TIER = {
    "gp_head": "head of the gram panchayat",
    "gp_ward": "member of a gram panchayat ward",
    "block_member": "member of the block-level body",
    "block_head": "head of the block-level body",
    "zp_member": "member of the district-level body",
    "zp_head": "head of the district-level body",
    # The gram kachahari is a village court, elected alongside the panchayat but
    # not part of it. Bihar is the state in this corpus that elects one.
    "kachahari_head": "head of the gram kachahari (village court)",
    "kachahari_member": "member of the gram kachahari (village court)",
    # Declared so a urban row can be recognised and excluded by name rather
    # than by falling through as unknown.
    "ulb_ward": "member of an urban local body ward",
    "ulb_head": "head of an urban local body",
}

# Printed name -> canonical office, where the name means one thing everywhere.
TIER_OF_LOCAL = {
    "mukhiya": "gp_head",
    "pradhan": "gp_head",
    "ward": "gp_ward",
    "ward_member": "gp_ward",
    "panchayat_samiti": "block_member",
    "panchayat_samiti_member": "block_member",
    "zila_parishad": "zp_member",
    "zila_parishad_member": "zp_member",
    "zila_pramukh": "zp_head",
    # Karnataka's gram panchayat president
    "adhyaksha": "gp_head",
    # Kerala names the body rather than the seat
    "grama_panchayat_member": "gp_ward",
    "block_panchayat_member": "block_member",
    "district_panchayat_member": "zp_member",
    # Uttarakhand
    "kshetra_panchayat_sadasya": "block_member",
    "zila_panchayat_sadasya": "zp_member",
    "pradhan_(gram_panchayat)": "gp_head",
}

# Printed name -> canonical office, where the state has to decide it. Keep this
# table small: every entry here is a name that means two different things, and
# each one is a chance to pool two different offices together.
TIER_BY_STATE = {
    ("Bihar", "sarpanch"): "kachahari_head",
    ("Bihar", "panch"): "kachahari_member",
    ("Andhra Pradesh", "sarpanch"): "gp_head",
    ("Telangana", "sarpanch"): "gp_head",
    ("Jammu & Kashmir", "sarpanch"): "gp_head",
    ("Haryana", "sarpanch"): "gp_head",
    ("Rajasthan", "sarpanch"): "gp_head",
    ("Rajasthan", "panch"): "gp_ward",
}


# Rural, i.e. panchayati raj. The urban local bodies are out of scope for now -
# the Trivedi Centre holds that material - so the master is built from these and
# what it leaves out is recorded rather than quietly dropped. Kerala and
# Rajasthan both ship urban wards in the same file as rural ones, so this has to
# be a filter, not an assumption about which file a row came from.
RURAL_TIERS = {"gp_head", "gp_ward", "block_member", "block_head",
               "zp_member", "zp_head", "kachahari_head", "kachahari_member"}
URBAN_TIERS = {"ulb_ward", "ulb_head"}


def is_rural(tier):
    return tier in RURAL_TIERS


def tier_of(local, state):
    """The canonical office for a printed name, or None if it is not known.

    None is a real answer and callers must treat it as one. Guessing that an
    unrecognised office is a gram panchayat head is how Bihar's village court
    would get pooled with everyone else's panchayat.
    """
    # "Ward Member", "ward_member" and "ward member" are one name. Bihar prints
    # them spaced and this table is written with underscores.
    key = re.sub(r"[\s_]+", "_", (local or "").strip().lower())
    if (state, key) in TIER_BY_STATE:
        return TIER_BY_STATE[(state, key)]
    return TIER_OF_LOCAL.get(key)


# Which categories a state reserves for, so that a category never seen is
# checkable rather than merely absent. Kerala reserving no BC seat is the law,
# not a parsing failure; Goa suddenly reserving none would be a parsing failure.
CASTE_SCHEME = {
    "Andhra Pradesh": "sc_st_bc",
    # the same commission's house style as Andhra Pradesh, and the same scheme
    "Telangana": "sc_st_bc",
    "Goa": "sc_st_bc",
    "Jharkhand": "sc_st_bc",
    # Haryana reserves for Block A of the Backward Classes list in panchayats
    # and prints it as BC_A, so the local label is finer than the pooled one.
    "Haryana": "sc_st_bca_only",
    "Bihar": "sc_st_obc",
    "Rajasthan": "sc_st_obc",
    "Uttar Pradesh": "sc_st_obc",
    "Uttarakhand": "sc_st_obc",
    # No backward-class reservation exists in local bodies in either.
    "Karnataka": "sc_st_bca_bcb",
    "Kerala": "sc_st_only",
    "Jammu & Kashmir": "sc_st_only",
}

# The pooled categories each scheme can produce.
SCHEME_CATEGORIES = {
    "sc_st_bc": {"SC", "ST", "BC", "NONE"},
    "sc_st_bca_only": {"SC", "ST", "BC", "NONE"},
    "sc_st_obc": {"SC", "ST", "BC", "NONE"},
    "sc_st_only": {"SC", "ST", "NONE"},
    # Karnataka reserves separately for Backward Class A and Backward Class B,
    # which is finer than the single BC other states print. Both fold to BC
    # here and caste_reservation_local says which.
    "sc_st_bca_bcb": {"SC", "ST", "BC", "NONE"},
}


def caste_scheme(state):
    return CASTE_SCHEME.get(state)


def allowed_castes(state):
    """The pooled categories this state's rows may take, or None if unknown."""
    return SCHEME_CATEGORIES.get(CASTE_SCHEME.get(state, ""))


# The panchayat's name arrives under whichever term the state prints. The
# mapping lives in dictionary.py so there is one place that decides it; this
# reads it rather than repeating the list, which is how the two drifted before.
UNIT_COLUMNS = ["gram_panchayat"] + sorted(
    alias for alias, canonical in dictionary.ALIAS_OF.items()
    if canonical == "gram_panchayat")


def unit_name(row):
    """The panchayat's name, whatever the source calls the column.

    Raises when a row carries two of them. The whole point of coalescing is that
    exactly one is ever populated; if two were, the coalesce would silently
    prefer one and drop the other, and nobody would see which.
    """
    present = [c for c in UNIT_COLUMNS if (row.get(c) or "").strip()]
    if len(present) > 1:
        raise ValueError(f"row names the panchayat in {present}: "
                         f"{ {c: row[c] for c in present} }")
    return row.get(present[0], "") if present else ""
