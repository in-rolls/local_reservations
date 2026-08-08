"""Published figures used as denominators, with where each one comes from.

These were scattered across four validators. Keeping them together matters
because they are not all the same kind of number, and the last time that was
treated casually it produced a real error: Haryana's 2022 figure was announced
before polling and counts *seats*, while its 2016 figure was published afterwards
and counts *people elected*. Comparing seat rows against the second made 2016
look like a 102% over-count.

So every entry records its `basis`:

    seats     the number of seats to be filled, announced before the election
    elected   the number of people returned, published after - excludes seats
              left vacant or countermanded, so vacant rows must be dropped
              before comparing

`None` is a real answer. J&K has no reliable published total for its panchayat
seats and its holdings are an ad-hoc subset rather than a corpus, so inventing a
denominator there would be worse than admitting there isn't one.
"""

# (state, year, tier) -> {"total": int|None, "basis": str, "source": str}
PUBLISHED = {
    ("Goa", "2012", "gp_ward"): {
        "total": 186, "basis": "seats", "unit": "panchayats",
        "source": "Goa SEC: 186 village panchayats went to poll in 2012. The "
                  "parsed file reproduces this exactly, which is what gives "
                  "confidence in the other two cycles' parsers.",
    },
    ("Jharkhand", "2015", "gp_head"): {
        "total": 4345, "basis": "seats", "unit": "gram panchayats",
        "source": "Jharkhand SEC, 2015 three-tier panchayat election.",
    },
    ("Jharkhand", "2015", "block_member"): {
        "total": 5423, "basis": "seats", "unit": "seats",
        "source": "Jharkhand SEC, 2015.",
    },
    ("Jharkhand", "2015", "zp_member"): {
        "total": 545, "basis": "seats", "unit": "seats",
        "source": "Jharkhand SEC, 2015.",
    },
    ("Jammu & Kashmir", "2010", "gp_ward"): {
        "total": None, "basis": "unknown", "unit": "panch constituencies",
        "source": "No reliable published total, and the holdings are an ad-hoc "
                  "subset of districts rather than a full corpus. Measuring "
                  "against a made-up denominator would be worse than not "
                  "measuring.",
    },
    ("Jammu & Kashmir", "2016", "gp_head"): {
        "total": None, "basis": "unknown", "unit": "halqas",
        "source": "As above.",
    },
    ("Jammu & Kashmir", "2016", "gp_ward"): {
        "total": None, "basis": "unknown", "unit": "panch constituencies",
        "source": "As above.",
    },
    ("Jammu & Kashmir", "2018", "gp_ward"): {
        "total": None, "basis": "unknown", "unit": "panch constituencies",
        "source": "As above, and these documents list only the reserved wards, "
                  "so a completeness figure would not mean what it looks like.",
    },
    # Bihar's six tiers, 2016. No denominator, and the reason is specific.
    #
    # The State Election Commission does publish per-tier totals, in a 434-page
    # scan with no text layer; OCR'd, its summary table reads "पंचायत आम
    # निर्वाचन, 2021 एक नजर में" - **2021**, not 2016. It gives 8,067 gram
    # panchayats, 533 blocks, 38 districts and 247,658 directly elected seats.
    # Those are the wrong cycle for this data and are recorded here as context
    # rather than as a total, because `coverage_vs_published` would treat a
    # total as authoritative and report a completeness figure against a
    # delimitation these rows were not drawn under.
    #
    # They are still worth having: against 2021's 8,067 panchayats the scrape's
    # 7,997 mukhiya seats are 99.1%, and its 10,837 panchayat samiti seats are
    # 97.7% of 2021's 11,094. The zila parishad tier is the one that does not
    # look like that.
    #
    # Recovering the 2016 totals means finding the 2016 report; that is on the
    # worklist. What is available without it is internal: the mukhiya and the
    # sarpanch are elected over the same set of panchayats, and the ward member
    # and the panch over the same set of wards, so each pair should agree. They
    # differ by 81 and 4,790 - a measurable statement about completeness that
    # needs no outside number at all.
    ("Bihar", "2016", "gp_head"): {
        "total": None, "basis": "unknown", "unit": "gram panchayats",
        "source": "Bihar SEC's published per-tier totals are for the 2021 "
                  "cycle (8,067 gram panchayats), not 2016. No 2016 total "
                  "recovered.",
    },
    ("Bihar", "2016", "gp_ward"): {
        "total": None, "basis": "unknown", "unit": "panchayat wards",
        "source": "As above.",
    },
    ("Bihar", "2016", "kachahari_head"): {
        "total": None, "basis": "unknown", "unit": "gram kachaharis",
        "source": "As above.",
    },
    ("Bihar", "2016", "kachahari_member"): {
        "total": None, "basis": "unknown", "unit": "kachahari wards",
        "source": "As above.",
    },
    ("Bihar", "2016", "block_member"): {
        "total": None, "basis": "unknown", "unit": "seats",
        "source": "As above.",
    },
    ("Bihar", "2016", "zp_member"): {
        "total": None, "basis": "unknown", "unit": "seats",
        "source": "As above. The scrape is visibly short here in a way the "
                  "other five tiers are not: Sheikhpura holds 1 seat and "
                  "Nawada 2, against 44 for Patna and 55 for Madhubani.",
    },
    ("Andhra Pradesh", "2020", "gp_head"): {
        "total": None, "basis": "per-district", "unit": "gram panchayats",
        "source": "Each gazette states its own district total in its FORMAT-I "
                  "abstract, which is a better denominator than a state figure "
                  "because only 6 of 13 districts are held. scripts/ap/"
                  "validate.py reads it per district. Anantapur states each "
                  "seat twice, in a sarpanch-only proforma and again as the "
                  "first column of the ward table; the file holds their union "
                  "deduplicated, and the two agree on 98.4% of the seats "
                  "stated by both.",
    },
    ("Goa", "2017", "gp_ward"): {
        "total": None, "basis": "per-taluka", "unit": "wards",
        "source": "Measured against 2012, which is complete, taluka by taluka.",
    },
    ("Goa", "2022", "gp_ward"): {
        "total": None, "basis": "per-taluka", "unit": "wards",
        "source": "As above.",
    },
}

# How many districts each state-year should cover, for the "partial: N of M"
# note. Jharkhand had 24 districts in 2015; Goa's 12 talukas sit under 2
# districts; AP had 13 districts in 2020; J&K's holdings are a subset by
# construction so it has no target.
DISTRICT_COUNT = {
    ("Goa", "2012"): 2, ("Goa", "2017"): 2, ("Goa", "2022"): 2,
    ("Jharkhand", "2015"): 24,
    ("Andhra Pradesh", "2020"): 13,
}

# Where the women's quota is a floor ("not less than one third", the wording of
# the 73rd Amendment) rather than an exact split. Passing the wrong one turned
# J&K's compliant 48% into a failure.
WOMEN_RULE = {
    ("Goa", "2012"): ("floor", 1 / 3),
    ("Goa", "2017"): ("floor", 1 / 3),
    ("Goa", "2022"): ("floor", 1 / 3),
    ("Jharkhand", "2015"): ("floor", 0.50),
    ("Jammu & Kashmir", "2010"): ("floor", 1 / 3),
    ("Jammu & Kashmir", "2016"): ("floor", 1 / 3),
    ("Jammu & Kashmir", "2018"): (None, None),   # reserved-only listing
    ("Andhra Pradesh", "2020"): ("target", 0.50),
}


# Whether a slice's document lists every seat. A statutory share cannot be
# checked against a subset, and the difference between "this state under-reserves"
# and "this document is a partial listing" is the whole finding.
#
#   all_seats      a full roster
#   reserved_only  only the reserved seats are listed, so the share is a
#                  property of the document (J&K 2018)
#   partial        a real but incomplete roster - Goa's 2017 and 2022 files are
#                  nomination-stage listings covering roughly half the wards
#                  that 2012 covers
LISTING_SCOPE = {
    ("Goa", "2017", "gp_ward"): "partial",
    ("Goa", "2022", "gp_ward"): "partial",
}


# What stage of document a slice came from. This decides whether "no winner
# recorded" is a fact about the document or a gap in our collecting: a pre-poll
# reservation roster names no winner and never will, while for anything else a
# results notification may exist that nobody has looked for. An absent entry is
# an open question, not a default.
#
#   pre_poll   a reservation roster drawn before the election
#   result     a notification published after, naming who won
DOCUMENT_STAGE = {
    ("Goa", "2012", "gp_ward"): "result",
    ("Goa", "2017", "gp_ward"): "pre_poll",
    ("Goa", "2022", "gp_ward"): "pre_poll",
    ("Jharkhand", "2015", "gp_head"): "result",
    ("Jharkhand", "2015", "gp_ward"): "result",
    ("Jharkhand", "2015", "block_member"): "result",
    ("Jharkhand", "2015", "zp_member"): "result",
    ("Andhra Pradesh", "2020", "gp_head"): "pre_poll",
    ("Andhra Pradesh", "2020", "gp_ward"): "pre_poll",
    # J&K's files are reservation *proposals*: they carry SC/ST/OC populations
    # and the reservation being proposed, and no winner column appears in any
    # of the 105 documents. A pre-poll roster names no winner and never will.
    ("Jammu & Kashmir", "2010", "gp_ward"): "pre_poll",
    ("Jammu & Kashmir", "2016", "gp_head"): "pre_poll",
    ("Jammu & Kashmir", "2016", "gp_ward"): "pre_poll",
    ("Jammu & Kashmir", "2018", "gp_ward"): "pre_poll",
}


# Whether the documents that would close a state's coverage can be fetched from
# here at all. Recorded because "nobody has done it" and "nobody here can do it"
# are different things, and a worklist that mixes them is a worklist nobody
# trusts. Verified by request, not assumed: the state SEC domains below refuse
# connections from two independent egresses, which is the network path rather
# than the sites being down.
SOURCE_ACCESS = {
    # Blocked at the state election commission, not everywhere. The Wayback
    # Machine crawled sec.ap.gov.in in 2022 and served six of the thirteen
    # gazettes from anywhere - that is how West Godavari was recovered - and the
    # district collectorate portals answer directly: chittoor.ap.gov.in and
    # kurnool.ap.gov.in both return 200, as does cdn.s3waas.gov.in where they
    # host their PDFs. Those portals publish documents under opaque names across
    # seven years, so finding the 2020 rosters means crawling each district's
    # list rather than fetching a known URL. A project, but not a wall.
    "Andhra Pradesh": ("blocked", "sec.ap.gov.in refuses connections from "
                                  "outside India; the archive holds 6 of 13 "
                                  "and the district portals answer, so the "
                                  "rest is a crawl rather than an egress"),
    "Jharkhand": ("reachable", ""),
    "Goa": ("reachable", ""),
    "Jammu & Kashmir": ("reachable", ""),
}


def source_access(state):
    return SOURCE_ACCESS.get(state, ("unknown", ""))


def document_stage(state, year, tier):
    return DOCUMENT_STAGE.get((state, year, tier))


def listing_scope(state, year, tier):
    return LISTING_SCOPE.get((state, year, tier), "all_seats")


def published(state, year, tier):
    return PUBLISHED.get((state, year, tier), {})


def districts_expected(state, year):
    return DISTRICT_COUNT.get((state, year))


def women_rule(state, year):
    return WOMEN_RULE.get((state, year), (None, None))
