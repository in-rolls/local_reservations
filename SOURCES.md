# Where GP-level reservation data comes from, state by state

A feasibility survey, not a summary of what we hold. Every format claim below
comes from opening the file and measuring how much extractable text it has —
never from what a website says it publishes.

Two scripts back this document and both can be re-run:

```
python scripts/inventory.py       # classify the documents already in data/
python scripts/probe_sources.py   # fetch candidate web sources and classify them
```

They write `data/inventory.csv` and `data/sources_probe.csv`.

## The one thing worth knowing first

**Whether a PDF has a text layer decides the cost of a state, and nothing on the
publisher's website tells you.** `local_elections_haryana` was cheap to build for
exactly one reason: its notifications were digitally generated text, so no OCR
was involved. That turned out to be unusual. Of the sources opened for this
survey, Punjab, Maharashtra, Chhattisgarh, West Bengal and Madhya Pradesh are
all images.

So the classification here is `digital-text` (≥800 chars/page), `mixed`, or
`scan`, measured with `pdftotext`. A scan is not a dead end — `savitr` (Surya on
MLX) and `parse_unsearchable_rolls` exist for exactly this — but it changes a
week of work into a month.

## The surprise: much of the acquisition is already done

`data/` already holds ~2 GB of source documents for states the coverage table in
[readme.md](readme.md) still shows as blank. For these the question is not "can
we get it" but "what is in it".

| state | text | scan | mixed | pages | what is held |
|---|---|---|---|---|---|
| Bihar | 290 | 0 | 0 | 9,193 | PRI winners 2006–2016; also `local_elections_bihar` |
| Rajasthan | 23 | 9 | 5 | 7,888 | panchayat 2005–2021 |
| **Jharkhand** | 108 | 28 | 8 | 4,970 | **2015 mukhiya (GP head) reservation by district; 2022 Form-23 ZP members** |
| **Jammu & Kashmir** | 105 | 8 | 0 | 1,488 | **2010/2016/2018 block-wise, panch-ward reservation with SC/ST/OC population** |
| **Andhra Pradesh** | 19 | 19 | 0 | 809 | **2020 district gazettes: GP, MPTC, ZPTC, MPP reservation** |
| **Goa** | 37 | 4 | 0 | 687 | **2012/2017/2022 `panres_<taluka>` panchayat reservation + ward category** |
| West Bengal | 0 | 39 | 1 | 603 | 2018 SEC delimitation-and-reservation gazettes, per district |
| Madhya Pradesh | 0 | 2 | 0 | 351 | two large OmniPage-OCR'd volumes |
| Odisha | 6 | 0 | 0 | 254 | 2017 reservation of sarpanch/ward member — **district totals, not seat-level** |
| Tamil Nadu | 11 | 1 | 0 | 74 | gazettes, but **municipal/corporation**, not village panchayat |
| Chandigarh, Puducherry, Delhi | 7 | 2 | 0 | 707 | mostly urban local bodies |
| Karnataka | 0 | 1 | 0 | 7 | `Karnataka_GP_ReservationHistory.dta` — already processed |
| Assam, Himachal | 1 | 1 | 0 | 11 | one file each; Assam's is municipal |

Bold rows are the ones holding **GP-level reservation in machine-readable form
already on disk**. That is the shortest path to new coverage in this repo, and it
needs no network access at all.

### Four states buildable now, without acquisition

- **Jammu & Kashmir** — the cleanest of the lot. `jk/2016/Annex A Doda.pdf` and
  its siblings are plain English tables: district, block, halqa, panch ward,
  SC/ST/OC population, percentages, and *proposed reservation*. 105 text
  documents, 1,488 pages. Population alongside reservation is unusual and makes
  the assignment rule auditable.
- **Goa** — `panres_2012_<Taluka>.pdf` is a "Report of Winning Candidate for
  V.P. Election" carrying taluka, panchayat, ward number, **category of the ward**
  (`G/ST/OBC/W/OBCW/STW`), the elected representative, their address and votes
  polled — one clean English table, ~4,900 chars/page. `details-pan-2012.pdf`
  adds nomination and elector counts. Three cycles held (2012, 2017, 2022), so
  it is a panel out of the box. Note the reservation is at **ward** level: Goa's
  sarpanch is elected indirectly by the members, so there is no directly
  reserved sarpanch seat to collect. Small state, ~190 panchayats.
- **Jharkhand** — `jharkhand/2015/<N>. <DISTRICT> MUKHIYA PSS/` is GP-head
  (mukhiya) data for 24 districts; the 2022 set is `Prapatra 23`, which is the
  Zila Parishad tier, so check the folder before assuming the tier. Typeset in
  legacy Kruti Dev-style Hindi — **the same mojibake already solved** in
  `local_elections_haryana/scripts/normalize.py`, which handles nine spellings
  of *anusuchit* and the doubled-character damage.
- **Andhra Pradesh** — 2020 district gazettes, GP reservation among them. Also a
  legacy-font problem, but Telugu rather than Devanagari, so the Haryana
  mapping does not transfer — only the technique does.

### Traps in what is already held

- **Odisha's files are aggregates.** `2017_RESERVATION-OF-SARPANCH-DISTRICT-WISE.pdf`
  is one row per district with counts by category (SC 426, ST 1,237 … 6,794
  total), not one row per gram panchayat. Seat-level Odisha still has to be
  acquired.
- **Tamil Nadu's gazettes are urban.** Gazette 326 concerns municipalities and
  corporations. Village panchayat president reservation is not in what we hold.
- **Maharashtra is Mumbai only** — `data/maharashtra/mumbai/`, BMC 1997–2012.
  The ~28,000 rural GPs are absent entirely.
- **AP's tiers are mixed together.** Of its 38 documents, the GP-level set
  (`2020_res_gp/`) is only 5; the rest are MPTC, ZPTC, MPP and MPL. Do not read
  the state-level text/scan split as applying to the GP files.

## States needing acquisition

Probed live; see `data/sources_probe.csv` for the machine-written record.

**Read that file with one caveat.** The probe opens the *first* document linked
from a seed URL. When the seed is a specific reservation page that is the right
document; when the seed is a district homepage it is whatever happens to be top
of the notice board. On the first run that produced two confident-looking
`digital-text` rows which turned out to be an NIC computer-disposal tender
(Chhattisgarh) and a Guntur staff transfer list (Andhra Pradesh) — neither has
anything to do with reservation.

So the probe records `topic_match`, and a row is only evidence when it says
`yes`. Getting that check right took three passes, which is itself the lesson:
bare `ward` matches *award*, `gram` matches *programme*, and the stem `reserv`
matches the tender boilerplate *"NIC reserves the right to reject any/all
quotations"*. It now requires a panchayat body term **and** a reservation
category term together. Seed specific pages, not homepages.

| state | ~GPs | source | format | verdict |
|---|---|---|---|---|
| Maharashtra | 27.9k | district portals (`washim.gov.in`), SEC reachable | **scan** (CamScanner) | OCR then build; biggest prize |
| Madhya Pradesh | 22.9k | SEC portal blocked; district portals reachable | **scan** | OCR then build |
| Punjab | 13.2k | district portals, 2024 election, block-wise | **scan** (CamScanner / print-to-image) | OCR then build |
| Chhattisgarh | 11.6k | district portals (`raigarh` notice page) | **scan** | OCR then build |
| Gujarat | 14.5k | `sec.gujarat.gov.in`, `panchayat.gujarat.gov.in` | unverified | needs India egress |
| Tamil Nadu | 12.5k | `tnsec.tn.gov.in` | unverified | needs India egress |
| Odisha (seat-level) | 6.8k | `sec.odisha.gov.in` | unverified | needs India egress |
| Himachal Pradesh | 3.6k | `sec.hp.gov.in` | unverified | needs India egress |
| Assam | 2.2k | `sec.assam.gov.in` | unverified | needs India egress |

### Reachability

There is a clean split. **NIC-template district portals answer** — `washim.gov.in`,
`raigarh.gov.in`, `bilaspur.gov.in`, `dhule.gov.in`, `indore.nic.in`,
`guntur.ap.gov.in`, and the Punjab districts — and they serve their PDFs from
`cdn.s3waas.gov.in`, which also answers. **State-specific SEC domains refuse**:
`sec.odisha.gov.in`, `sec.gujarat.gov.in`, `tnsec.tn.gov.in`, `sec.hp.gov.in`,
`sec.assam.gov.in`, `panchayat.gujarat.gov.in`, `egramswaraj.gov.in`. These give
`ECONNREFUSED` from two independent egresses, so it is the network path, not the
sites being down — the same wall the TN RTI work hits, and the reason those rows
say *needs India egress*.

Practical consequence: **most states are reachable through their district
collectorate portals even when the SEC is not.** That is more crawling surface —
20 to 36 districts per state instead of one index — but it is not blocked.

### The national shortcut, unverified

`egramswaraj.gov.in/ElectedRepresentativeReport.do` is a Ministry of Panchayati
Raj report covering every state, which would beat per-state scraping outright.
Two caveats before anyone gets excited: it is geo-blocked from here, and it very
likely carries the **representative's** caste and gender rather than the
**seat's** reservation. Those are different variables, and only the seat's
reservation is the assignment — a woman winning an unreserved seat is not a
reserved seat. Worth verifying behind a VPN; worth not assuming.

## Recommended order

1. **Jammu & Kashmir and Goa** — clean English text, already downloaded, and Goa
   gives three cycles. Days, not weeks.
2. **Jharkhand** — GP-level, already downloaded, and its legacy-Hindi encoding is
   a solved problem in this codebase.
3. **Andhra Pradesh** — already downloaded, but needs a Telugu legacy-font
   mapping built from scratch.
4. **Maharashtra** — the largest missing state by far. Requires OCR and a
   36-district crawl, so it is the first real project rather than a cleanup.
5. Anything behind the geo-block, once a VPN run confirms what is actually there.

## Caveat on what "reservation data" means

Two different artifacts get called this, and they are not interchangeable:

- the **seat reservation roster**, drawn by lot before the election, which is the
  assignment; and
- the **elected-members notification**, published after, which in some states
  (Haryana, Jharkhand) carries the seat's reservation *and* the winner's name in
  the same row, and in others carries only the winner.

Where both exist the second is better — it gives the outcome for free. Where only
a winners list exists without the seat's category, it does not substitute for the
roster, however tempting the caste and gender columns look.
