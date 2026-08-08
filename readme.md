### Local Electoral Body Reservations

Data on local electoral body (ULB and PRI) reservations.

See **[SOURCES.md](SOURCES.md)** for a state-by-state feasibility survey: where
each state publishes its reservation data, whether the files are text or scans,
and what it would take to extend coverage.

The table below is **generated** — `make coverage` rebuilds it from the parsed
files, from `data/inventory.csv` for states still raw, and from the sibling
repositories, then checks that every link resolves. It drifted twice while
hand-maintained, so it is no longer hand-maintained.

<!-- worklist:start -->

| | Entries | Rows affected |
|---|---|---|
| [Open gaps](WORKLIST.md) | 26 | 33,002 |
| [Blocked](WORKLIST.md) | 2 | 50,431 |
| [Undetermined](WORKLIST.md) | 6 | 12,985 |
| [Accepted properties of the sources](WORKLIST.md) | 6 | 53,548 |

<!-- worklist:end -->

Every release is pinned by **[MANIFEST.json](MANIFEST.json)** — a SHA-256 for
every file, the exact master column order, and the commit each sibling
repository was read at. Verify a checkout with `python3
scripts/verify_manifest.py`, which is standard library only and imports nothing
else here, so it works from a bare checkout or an unpacked tarball.

## What we have

One row per state, year and tier — the grain the data actually has. The notes
are derived from the rows themselves rather than written by hand, so they cannot
drift from what is in the files.

Each state directory also has its own generated readme — what is in it, which
documents each row came from, what to be careful of, and how to rebuild it.

Read the notes before the numbers. J&K 2018's 82% women is a property of a
document that lists only the reserved wards, not a fact about J&K; Goa's 2017
and 2022 cycles are nomination lists and name no winner; Jharkhand's place names
are still in the legacy font they were printed in.

<!-- slices:start -->

| State | Year | Tier | Rows | Women | Districts | vs published | Notes | Where |
|---|---|---|---|---|---|---|---|---|
| Andhra Pradesh | 2020 | `gp_head` | 4,738 | 49% | 5 | — | no winner published; partial: 5 of 13 districts; ward list complete for 94% of rows with a stated count | [data/ap/](data/ap/) |
| Andhra Pradesh | 2020 | `gp_ward` | 45,693 | 47% | 5 | — | no winner published; partial: 5 of 13 districts; ward list complete for 94% of rows with a stated count | [data/ap/](data/ap/) |
| Goa | 2012 | `gp_ward` | 1,471 | 32% | 2 | 99% of 186 panchayats | — | [data/goa/](data/goa/) |
| Goa | 2017 | `gp_ward` | 684 | 27% | 2 | — | no winner published | [data/goa/](data/goa/) |
| Goa | 2022 | `gp_ward` | 793 | 39% | 2 | — | no winner published | [data/goa/](data/goa/) |
| Jammu & Kashmir | 2010 | `gp_ward` | 7,340 | 48% | 10 | — | no winner published | [data/jk/](data/jk/) |
| Jammu & Kashmir | 2016 | `gp_head` | 410 | 33% | 5 | — | no winner published | [data/jk/](data/jk/) |
| Jammu & Kashmir | 2016 | `gp_ward` | 2,326 | 32% | 5 | — | no winner published | [data/jk/](data/jk/) |
| Jammu & Kashmir | 2018 | `gp_ward` | 1,432 | 82% | 12 | — | no winner published; **reserved seats only** — shares are a property of the document, not of the state | [data/jk/](data/jk/) |
| Jharkhand | 2015 | `block_member` | 4,354 | 52% | 21 | 80% of 5,423 seats | partial: 21 of 24 districts | [data/jharkhand/](data/jharkhand/) |
| Jharkhand | 2015 | `gp_head` | 4,214 | 52% | 23 | 97% of 4,345 gram panchayats | partial: 23 of 24 districts | [data/jharkhand/](data/jharkhand/) |
| Jharkhand | 2015 | `gp_ward` | 11,113 | 53% | 9 | — | partial: 9 of 24 districts | [data/jharkhand/](data/jharkhand/) |
| Jharkhand | 2015 | `zp_member` | 181 | 52% | 8 | 33% of 545 seats | partial: 8 of 24 districts | [data/jharkhand/](data/jharkhand/) |

<!-- slices:end -->

## What is still missing

*Status* means: **parsed** — in this schema, one row per seat-year;
**held, unparsed** — documents or tables are here, in someone else's
layout, and nobody has parsed them into this schema yet; **raw, unparsed** — source documents on disk, no parser yet;
**not held** — nothing acquired; **no PRI** — nothing to collect.


<!-- coverage:start -->

| State | Tier | Years | Rows | Status | Where |
|---|---|---|---|---|---|
| Andaman & Nicobar Islands | - | - | - | not held | - |
| Andhra Pradesh | gp_head, gp_ward | 2020 | 50,431 | parsed | [data/ap/](data/ap/) |
| Arunachal Pradesh | - | - | - | not held | - |
| Assam | - | - | - | documents, no parser | [data/assam/](data/assam/) - 1 digital-text |
| Bihar | gp_head, gp_ward, block_member, zp_member, kachahari | 2016 | 692,314 | parsed | [local_elections_bihar](https://github.com/in-rolls/local_elections_bihar) |
| Chandigarh | - | - | - | documents, no parser | [data/chandigarh/](data/chandigarh/) - 4 digital-text, 1 scan |
| Chhattisgarh | - | - | - | not held | - |
| Dadra & Nagar Haveli and Daman & Diu | - | - | - | not held | - |
| Goa | gp_ward | 2012, 2017, 2022 | 2,948 | parsed | [data/goa/](data/goa/) |
| Gujarat | - | - | - | not held | - |
| Haryana | gp_head, gp_ward | 2016, 2022 | 135,218 | parsed | [local_elections_haryana](https://github.com/in-rolls/local_elections_haryana) |
| Himachal Pradesh | - | - | - | documents, no parser | [data/himachal/](data/himachal/) - 1 scan |
| Jammu & Kashmir | gp_head, gp_ward | 2010, 2016, 2018 | 11,508 | parsed | [data/jk/](data/jk/) |
| Jharkhand | block_member, gp_head, gp_ward, zp_member | 2015 | 19,862 | parsed | [data/jharkhand/](data/jharkhand/) |
| Karnataka | - | gram panchayat head, 1993/2000/2002/2005/2007 | - | tables, other layout | [data/karnataka/](data/karnataka/) |
| Kerala | gp_ward, block_member, zp_member, ulb_ward | 2010, 2015, 2020 | 65,296 | parsed | [local_elections_kerala](https://github.com/in-rolls/local_elections_kerala) |
| Ladakh | - | - | - | not held | - |
| Lakshadweep | - | - | - | not held | - |
| Madhya Pradesh | - | - | - | documents, no parser | [data/madhya_pradesh/](data/madhya_pradesh/) - 2 scan |
| Maharashtra | `ulb_ward` | Mumbai 2007, 2012, 2017 | - | urban only | [data/maharashtra/](data/maharashtra/) |
| Manipur | - | - | - | not held | - |
| Meghalaya | - | - | - | no PRI | Sixth Schedule - autonomous district councils, no PRI |
| Mizoram | - | - | - | no PRI | Sixth Schedule - village councils, no PRI |
| Nagaland | - | - | - | no PRI | Article 371A - village councils, no PRI |
| NCT of Delhi | `ulb_ward` | 2007, 2012, 2017 | - | urban only | [data/delhi/](data/delhi/) |
| Odisha | - | - | - | documents, no parser | [data/odisha/](data/odisha/) - 6 digital-text |
| Puducherry | - | - | - | documents, no parser | [data/puducherry/](data/puducherry/) - 1 digital-text, 1 scan |
| Punjab | - | - | - | not held | - |
| Rajasthan | gp_head | 2005, 2010, 2015, 2020 | 4 parquet | parsed | [quota_raj](https://github.com/in-rolls/quota_raj) |
| Sikkim | - | - | - | not held | - |
| Tamil Nadu | - | - | - | documents, no parser | [data/tamil_nadu/](data/tamil_nadu/) - 11 digital-text, 1 scan |
| Telangana | - | gram panchayat + ward 2019, municipal 2020-21 | - | tables, other layout | [data/telangana/](data/telangana/) |
| Tripura | - | - | - | not held | - |
| Uttar Pradesh | gp_head | 2005, 2010, 2015, 2021 | 4 parquet | parsed | [local_elections_up](https://github.com/in-rolls/local_elections_up) |
| Uttarakhand | gp_head, block_member, zp_member | 2008, 2014, 2019 | 116,514 | parsed | [local_elections_uttarakhand](https://github.com/in-rolls/local_elections_uttarakhand) |
| West Bengal | - | 2018 delimitation-and-reservation gazettes, 20 districts | - | tables, other layout | [data/wb/](data/wb/) |

<!-- coverage:end -->


### Other Sources

* https://github.com/tcpd/Urban_Local_Body
