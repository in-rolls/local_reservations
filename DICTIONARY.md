# Data dictionary

Generated from `scripts/common/dictionary.py` by `make dictionary` — edit the
declarations, not this file.

Every column is checked against these rules by `make expect`, which writes
`data/expectations_report.csv`: one row per violated expectation, with the count
and the source document and page of the first offender, so a finding points at a
gazette page rather than at a number.

Severity is **error** when a value cannot be right (outside its enum or range),
**warn** when it is suspicious (blank more often than expected, an unusual
length), and **info** when it is known and accepted.

A column that is *entirely* blank in a file is reported as info, not warn: it
means the source has no such column — J&K's 2010 files carry no district, a
nomination list carries no winner — and that is a fact about the document rather
than a defect.


| Column | Type | Severity | Constraints | Notes |
|---|---|---|---|---|
| `state` | string | error | length 3–30; ≤0% blank | Printed name of the state or union territory. |
| `year` | integer | error | range 1990–2030; ≤0% blank | Election year. Four digits; a range would mean two cycles got merged into one file. |
| `tier` | enum | error | one of `gp_head`, `gp_ward`, `block_member`, `block_head`, `zp_member`, `zp_head`, `kachahari_head`, `kachahari_member`, `ulb_ward`, `ulb_head`; ≤0% blank | Which office the seat is, canonically. The same office is printed under different names by different states, and worse, the same name means different offices - Bihar's sarpanch heads a village court, not the panchayat. See canon.py. |
| `tier_local` | string | warn | length 2–40; ≤0% blank | The office as the state printed it: sarpanch, mukhiya, ward_member. Kept so nothing is lost to the canonical mapping and any row can be checked against its gazette. |
| `district` | string | warn | length 3–30; ≤20% blank | J&K's 2010 files carry no district column at all, so a blank share above zero is expected there but not elsewhere. |
| `block` | string | warn | length 2–40; ≤35% blank | Block, taluka or mandal depending on the state. |
| `gram_panchayat` | string | warn | length 2–45; ≤10% blank; also called `halqa` | The panchayat. Called halqa in J&K. Jharkhand printed it inside a compound seat identifier until that was taken apart; see seat_id_raw. A value far over the length bound has usually swallowed the next column - that is how AP's broken mandal split was found. |
| `ward_no` | roman_or_integer | warn | length 1–6; ≤30% blank | Blank on sarpanch and mukhiya rows by design. J&K and Goa number wards in Roman numerals, so this is not purely numeric. |
| `ward_name` | string | warn | length 2–40; ≤30% blank | J&K only. |
| `caste_reservation` | enum | error | one of `SC`, `ST`, `BC`, `NONE`; ≤0% blank | Orthogonal to woman_reserved: a seat can be both. |
| `woman_reserved` | boolean | error | ≤0% blank | 1 if reserved for a woman. |
| `reservation` | enum | error | one of `Woman`, `Other than Woman`, `SC Woman`, `SC Other than Woman`, `ST Woman`, `ST Other than Woman`, `BC Woman`, `BC Other than Woman`; ≤0% blank | The two fields above, joined. Written separately from them, so it can disagree with them - which is checked as a row rule. |
| `reservation_raw` | string | error | length 1–120; ≤0% blank | The source cell, untouched, so any row can be audited. |
| `district_declared` | boolean | info | — | Set where the district was declared from a roster outside the corpus rather than read from the document. Eight of J&K's 2010 blocks name no district anywhere in their file; saying so is the difference between a reading and an assertion. |
| `listing_scope` | enum | warn | one of `all_seats`, `reserved_only` | J&K's 2018 documents list only the reserved wards, so any share computed from them is a property of the document. Absent means all_seats. |
| `winner` | string | warn | length 2–60; ≤60% blank | Only some states publish the elected member. |
| `votes` | integer | warn | range 0–100000; ≤60% blank | Goa 2012 only. |
| `vacant` | boolean | warn | ≤0% blank | Seat unfilled or the election countermanded. Official 'elected' totals exclude these. |
| `unopposed` | boolean | warn | ≤0% blank | A '*' against the name in the source. |
| `block_no` | integer | warn | range 1–99; ≤90% blank |  |
| `seat_no` | integer | warn | range 1–999; ≤90% blank |  |
| `serial` | integer | warn | range 1–9999; ≤10% blank | AP's per-mandal running number; gaps in it mean lost rows. |
| `halqa` | string | warn | length 2–45; ≤10% blank |  |
| `seat_id_raw` | string | info | length 1–90; ≤5% blank | Jharkhand. The seat identifier exactly as printed, before it was taken apart - a compound of district, block, gram panchayat and constituency number run together with @ and /. Kept because the split is the kind of thing worth being able to re-check against the page. |
| `gp_no` | integer | warn | range 1–99; ≤60% blank | The gram panchayat's number within its block, where the source states one. |
| `pop_sc` | integer | warn | range 0–100000; ≤90% blank | J&K prints the populations the allocation was based on, which is the only place in this repo the rule can be checked against its own inputs. |
| `pop_st` | integer | warn | range 0–100000; ≤90% blank |  |
| `pop_oc` | integer | warn | range 0–100000; ≤90% blank |  |
| `pop_total` | integer | warn | range 0–200000; ≤90% blank |  |
| `ward_count` | integer | error | range 1–20; ≤75% blank | The number of wards the record itself states. The gazette header numbers ward columns 1 to 20, so anything above that is an OCR misread - 72 and 74 are 12 and 14 in this font. Blank for most of Andhra Pradesh because Anantapur's gazette is sarpanch-only and prints no ward column at all, which is why the blank tolerance is high. |
| `wards_parsed` | integer | warn | range 0–20; ≤0% blank |  |
| `ward_list_complete` | boolean | warn | ≤50% blank | 1 when the ward list matches the stated count. Only about a third of AP's ward rows qualify, so a consumer should filter on this rather than assume. |
| `ocr_repaired` | integer | warn | range 0–2; ≤0% blank | How many mends the row's category cell needed. A wrong mend is indistinguishable from a right one, so these stay findable. |
| `printings` | integer | warn | range 1–4; ≤0% blank | How many times the gazette states this seat. Anantapur prints the sarpanch reservation in two proformas - a sarpanch-only list and the ward table's first column - so where both carry a seat this is 2 and validate.py checks that the two agree rather than assuming it. |
| `gender_stated` | boolean | warn | ≤0% blank | Whether the source actually stated this seat's gender. Where a document marks only the women's seats a bare code is a man; where it marks both, a bare code is a marker that did not survive the scan, and woman_reserved=0 there is a guess. Filter on this before computing a women's share. |
| `printings_agree` | boolean | warn | — | Whether the gazette's separate statements of this seat say the same thing. Blank where the seat is stated only once - which is not the same as agreeing. Two independent typesettings agreeing is the strongest evidence available here that a row was read correctly. |
| `text_source` | enum | info | one of `ocr`, `embedded` | Whether the row came from our own OCR or the PDF's embedded text layer, which for AP is itself faulty OCR. |
| `script` | enum | error | one of `latin`, `krutidev`, `devanagari`; ≤0% blank | Which typesetting the row was read from. |
| `source_pdf` | string | error | length 4–80; ≤0% blank |  |
| `source_path` | path | error | ≤0% blank | Relative to data/, and checked by opening it rather than by matching a pattern - a first attempt at a filename regex rejected 1,783 perfectly good Jharkhand rows because one file is called 'Gomia_GPS, GPM & GPVM.pdf'. What matters is that the document is there, not what it is called. |
| `source_page` | integer | error | range 1–2000; ≤0% blank |  |

## Plausible row counts

A file outside its band has lost rows or double counted them.

| State | Tier | Expected rows |
|---|---|---|
| Andhra Pradesh | gp_head | 500–13,200 |
| Andhra Pradesh | gp_ward | 5,000–130,000 |
| Goa | gp_ward | 400–1,800 |
| Jammu & Kashmir | gp_head | 100–4,500 |
| Jammu & Kashmir | gp_ward | 500–35,000 |
| Jharkhand | block_member | 1,000–5,500 |
| Jharkhand | gp_head | 1,000–4,400 |
| Jharkhand | gp_ward | 1,000–12,000 |
| Jharkhand | zp_member | 50–600 |
