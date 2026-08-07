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
    ("Goa", "2012", "ward"): {
        "total": 186, "basis": "seats", "unit": "panchayats",
        "source": "Goa SEC: 186 village panchayats went to poll in 2012. The "
                  "parsed file reproduces this exactly, which is what gives "
                  "confidence in the other two cycles' parsers.",
    },
    ("Jharkhand", "2015", "mukhiya"): {
        "total": 4345, "basis": "seats", "unit": "gram panchayats",
        "source": "Jharkhand SEC, 2015 three-tier panchayat election.",
    },
    ("Jharkhand", "2015", "panchayat_samiti"): {
        "total": 5423, "basis": "seats", "unit": "seats",
        "source": "Jharkhand SEC, 2015.",
    },
    ("Jharkhand", "2015", "zila_parishad"): {
        "total": 545, "basis": "seats", "unit": "seats",
        "source": "Jharkhand SEC, 2015.",
    },
    ("Jammu & Kashmir", "2010", "ward"): {
        "total": None, "basis": "unknown", "unit": "panch constituencies",
        "source": "No reliable published total, and the holdings are an ad-hoc "
                  "subset of districts rather than a full corpus. Measuring "
                  "against a made-up denominator would be worse than not "
                  "measuring.",
    },
    ("Jammu & Kashmir", "2016", "sarpanch"): {
        "total": None, "basis": "unknown", "unit": "halqas",
        "source": "As above.",
    },
    ("Jammu & Kashmir", "2016", "ward"): {
        "total": None, "basis": "unknown", "unit": "panch constituencies",
        "source": "As above.",
    },
    ("Jammu & Kashmir", "2018", "ward"): {
        "total": None, "basis": "unknown", "unit": "panch constituencies",
        "source": "As above, and these documents list only the reserved wards, "
                  "so a completeness figure would not mean what it looks like.",
    },
    ("Andhra Pradesh", "2020", "sarpanch"): {
        "total": None, "basis": "per-district", "unit": "gram panchayats",
        "source": "Each gazette states its own district total in its FORMAT-I "
                  "abstract, which is a better denominator than a state figure "
                  "because only 5 of 13 districts are held. scripts/ap/"
                  "validate.py reads it per district. Anantapur states each "
                  "seat twice, in a sarpanch-only proforma and again as the "
                  "first column of the ward table; the file holds their union "
                  "deduplicated, and the two agree on 98.4% of the seats "
                  "stated by both.",
    },
    ("Goa", "2017", "ward"): {
        "total": None, "basis": "per-taluka", "unit": "wards",
        "source": "Measured against 2012, which is complete, taluka by taluka.",
    },
    ("Goa", "2022", "ward"): {
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


def published(state, year, tier):
    return PUBLISHED.get((state, year, tier), {})


def districts_expected(state, year):
    return DISTRICT_COUNT.get((state, year))


def women_rule(state, year):
    return WOMEN_RULE.get((state, year), (None, None))
