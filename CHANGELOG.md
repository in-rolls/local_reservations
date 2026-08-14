# Changelog

What changed, and what it means for a number you may already have used. Entries
say when a figure moved and why, because a corpus that silently restates itself
is worse than one that does not change at all.

Corrections are listed first in each release, not last. The most useful thing
here is usually the thing that was wrong.

## Unreleased — v0.2.3

### Corrected

- **Andhra Pradesh under-counted women's seats, and it was a bias rather than a
  shortfall.** 1,754 ward rows stated a caste and no gender. Nellore, Prakasam
  and Anantapur mark *both* the women's and the open seats, so a bare `UR`
  there is unknown rather than male — and the markers are not lost at equal
  rates, so a women's share computed over those districts was wrong in a
  direction. **If you computed a women's share for AP 2020, redo it.**

  The cause is the OCR mode. `--psm 4` preserves the layout the parser reads
  positionally and pays for it by gluing the ruled table's own lines onto the
  cells: the marker arrives as `IBC)`, `|URW)`, `[URW`, `JURG)`, the opening
  bracket read as `I`, `|`, `[` or `J`. A second pass at `--psm 11` reads the
  same page far more cleanly and is matched back **by position** — a cell takes
  a reading only where exactly one clean token sits in the same place, so it
  can never assert a gender the document does not state.

      gender unstated                                 1,754 -> 1,174
      ward_list_complete = 1                         36,858 -> 37,642
      panchayats parsed short of their stated count      223 -> 203

### Known, and not fixed here

- **`ward_list_complete` can report a panchayat complete against a misread
  count.** Tesseract reads the "No. of Wards" column wrongly on 23 lines —
  Alurupadu prints 8 and reads 4 — and the parser truncates the ward list to
  it. Those rows then satisfy the completeness check while holding half their
  wards. This predates the correction above and is why Alurupadu now holds 4
  wards where a misaligned parse used to spill 7 of its 8.

## Unreleased — v0.2.2

No data changed. Every value in every master table was compared against v0.2.1
column by column; only `source_commit`, the build's own provenance stamp, moved.

### Changed

- **The scripts are a package.** `scripts/` became
  `src/local_reservations/{common,states,tools}`, tests moved to `tests/`, and
  no file manipulates `sys.path` any more. 32 of 74 did, and it was not
  cosmetic: it is why a module named `http.py` in the shared layer would have
  shadowed the standard library's `http` package and broken `requests`, and why
  one named `surya.py` would have shadowed the real `surya` package.

- **One repository root.** 42 modules each worked it out by counting parent
  directories, which is a silent assertion about where a file sits. It is now
  `local_reservations.paths.ROOT`, found by walking up for a marker. The proof
  it was needed: a test located a sibling repository by counting parents and,
  after the move, did not fail but **skipped** — reporting a checked-out
  sibling as absent.

- **pyproject + uv.lock.** The `pyarrow==23.0.1` pin was documented as
  load-bearing and enforced by nothing. Parquet stamps its writer into every
  footer, so a different version rewrites every hash in MANIFEST.json without
  changing a value.

- **The OCR dependencies are a conflicting dependency group.** savitr pins
  `pillow<11` where pdfplumber needs `>=12.2`; `uv sync --group ocr` replaces
  the hand-made `ocrenv/`, and uv refuses to install both rather than leaving
  whichever came second broken.

- **Fleet tooling via preen**, minus the parts built for shipping a package.
  The release workflow was removed rather than left in place: it fires on `v*`
  tags and can publish to PyPI, and this repository's tags are data releases
  gated by `release_check.py`. ruff went from 741 findings to zero.

### Corrected

- **A `TypeError` that had not fired yet.** `collapse.py` computed a
  two-candidate seat's margin as `top - runner`, where `votes_of()` returns
  `None` where a source recorded no count — its own docstring insists None is
  not zero, and Bihar writes 24 seats with no numeric vote plus one reading
  `"986+1 (BY LOT)"`. Found by pyright; a margin against an unknown is now
  blank, which is what blank already meant there.

- **An undeclared dependency that was silently dropping rows.** The first build
  inside a locked environment reported `quota_raj: pandas is not importable, so
  the parquet slices are skipped` and produced 39,520 fewer Rajasthan rows. The
  system interpreter happened to have pandas; nothing said the corpus needed
  it. It is declared now.

## Unreleased — v0.2.1

### Corrected

**Haryana ward reservations were wrong in three ways, and every version up to
and including v0.2.0 shipped them.** The gazettes are clean — this was ours.

- **1,678 rows named a person "Ward 1".** Karnal and Palwal 2022 print each
  notification twice, Hindi then English, and the English ward column reads
  `Ward 1` where the Hindi reads `1`. The parser tested `isdigit()`, which is
  false there, so the cell stayed put and every field after it shifted one
  place right: the ward label landed in `winner` and the winner's name in
  `father_husband`. **If you counted distinct winners in Haryana 2022, 1,678 of
  them were column labels.**

- **1,014 rows carried the neighbouring seat's reservation.** Where a category
  wraps, the ward digit and the category are top-aligned in their cells while
  the name sits lower, so one printed line comes out as two rows. `split_row`
  anchors on the office cell, so the half holding the ward was discarded — and
  the continuation logic, which is correct for tails that belong to the row
  *above*, then attached that category to the **previous** seat. Ajit Nagar's
  ward 1 was published as Unreserved; the gazette says Backward Class. **If you
  used Kaithal, Mewat or Sirsa 2016 ward reservations, redo it.**

- **Rows were deleted by a typo in the gazette.** `normalize_reservation`
  returned `None` for `Unresreved`, and a `None` reservation does not blank a
  field — it discards the whole row, the elected member's name with it. Ambala
  prints that misspelling 79 times. Barnala shipped five of its nine panches
  and every count said the table was full.

  2016: 61,618 → 61,879 ward rows, 1,014 → 164 without a ward number
  2022: 1,678 → 719 without a ward number, 639 → 0 named "Ward N"
  Pooled seats: 829,351 → 829,593

### What made these invisible

None of the three appeared on any gap list, because a gap list counts rows that
have a problem and these rows had been deleted or silently rewritten. The check
that finds them is the one Karnataka already had and Haryana did not: **a
panchayat's wards are numbered 1..N, so a seat nobody read shows up as a hole.**
`validate.py` now runs it, along with checks that no ward number repeats, that
every seat states one, and that no winner is a column label.

It reports what is still wrong rather than hiding it: 159 panchayats in 2016
and 344 in 2022 still have a gap. Some of those are real — a seat can go
unfilled — and some are still ours.

Duplicate ward keys rose by 10 in 2022, which is not a regression. Those rows
had no ward number before and so collided with nothing; numbering them
correctly revealed that Chirao and Babain each hold two panchayats sharing a
name — a separate defect that was invisible while the rows were unnumbered.

## Unreleased — v0.2.0

### Added

- **Karnataka's 2016 taluk and zilla panchayat members: 4,366 seats across
  30 districts and 166 taluks.** Two tiers the corpus held no row for, and the
  state's first winners — everything Karnataka had before was a gram panchayat
  reservation roster for 1993–2007, which names nobody by construction. 3,478
  taluk panchayat seats against the 3,884 the state polled, and 888 zilla
  panchayat against 1,083; the archive holds 169 of 176 taluks and 26 of 30
  zilla panchayats, so the rest was never captured rather than lost here.

- **A `party` column with something in it.** These notifications print the
  party the winner represented, which almost nothing else in the corpus does:
  Congress 1,852, BJP 1,460, JD(S) 632, Independent 178, JD(U) 5. It is
  canonicalised against a fixed list and left **blank rather than guessed**
  where the cell does not settle the question — a reading truncated to
  ಭಾರತೀಯ fits both of the two largest parties. 237 rows are blank on that
  basis, and `party_local` keeps what the page actually said.

- **Every row says where its document came from.** `source_url` and
  `source_capture` join from the harvest manifest, so a row refetches the exact
  bytes it was read from. `source_path` and `source_page` already said which
  file and which page; nothing said which URL.

- **`scripts/archive_sweep.py`** asks all 31 state election commissions what
  the web archive holds for them — 23 resolve, ~14,000 PDFs. Karnataka's 828
  are what this release came from, and they were found by accident before this
  existed.

### What to know before using the Karnataka rows

- **50.1% of seats are reserved for women**, against the 50% the Karnataka
  Panchayat Raj Act requires. That comes from a column nothing here was tuned
  against and is the best evidence available that the reservation is read
  correctly. Caste: 2,224 unreserved, 864 BC, 854 SC, 424 ST, with BC split
  A/B in `caste_reservation_local` because Karnataka reserves for them
  separately.

- **6.6% of rows have no resolved party.** That is the honest measure of how
  many cells did not read cleanly, not a claim that those seats were
  independent — `Independent` is a value in its own right, 178 of them.

- **Three of 195 documents contribute nothing, and 25 of 586 pages.** Both are
  printed by the parser rather than left to be inferred from a row count.

- **~100 rows carry no constituency number**, so they share a seat key within
  their taluk. Those documents print only a name where others print `1-name`;
  where a document's serials run 1..N they are adopted and flagged
  `seat_no_from_serial`, and where they do not, the number is left empty rather
  than invented. Carried on the worklist.

- **24 documents lose a seat**, usually where a row straddles a page break, and
  Bidar loses two more to three washed-out rows at the top of a page. Every gap
  is reported: a taluk's constituencies are numbered consecutively, so a lost
  row shows as a hole rather than as a plausibly short table.

### Changed

- **Uttar Pradesh and Rajasthan are `parked`, not open gaps.** Their remaining
  entries are real and are deliberately not being worked; open gaps fell from
  60 entries to 51. Rajasthan's 2020 is the clearest case — quota_raj declares
  `winner_name_2020` and never fills it, 0 of 7,882 rows where 2015 is filled
  on all 7,882 — so no amount of parsing here closes it.

- **All archive traffic is rate-limited properly.** `requests-ratelimiter` and
  urllib3's `Retry`, in one adapter, honouring `Retry-After`. The Internet
  Archive firewalls an IP for an hour if 429s are ignored for a minute, and the
  previous hand-rolled sleep loop never read the header.

- **Karnataka's other 244 harvested documents are deliberately not parsed.**
  211 reservation gazettes restate a reservation these notifications already
  print; 33 gram panchayat 2015 files name nobody, being nomination counts,
  turnout and district totals. Recorded in `data/karnataka/readme.md` and
  `SOURCES.md` so the decision is not made twice.

### Corrected

- **The archive sweep could report a state as holding nothing when the archive
  had simply not answered.** Gujarat came back as 614 PDFs and then 0, Odisha
  817 then 0, Mizoram 0 then 168. An unanswered question and an empty answer
  now cannot share a value, and a state whose query fails carries its previous
  number forward marked stale.

## Unreleased — v0.1.1

### Corrected

- **17,115 winner names shipped as mojibake, labelled as Unicode.** Jharkhand's
  parser transliterated `block` and `gram_panchayat` from Kruti Dev and never
  `winner`, then stamped `script = devanagari` on the row regardless. So
  अनिता देवी appeared 92 times as `vfurk nsoh` and 55 times as अनिता देवी — the
  same woman, counted as two people, in a column that said the encoding was
  clean. **If you joined v0.1.0 on winner name, redo it.** She is now one person,
  147 times, and `script` describes the row rather than asserting about it.

- **A caption was published as a place name.** The seat identifier puts its
  number after "territorial constituency no.", and only the Kruti Dev spelling of
  that label was recognised, so on a Devanagari page the caption itself became
  the gram panchayat. 18 rows named `प्रा0नि0क्षे0 सं0` instead of a place.

- **501 seats were published twice.** Two readers of the same page rendered one
  person differently — `1 रेखा देवी` against `रेखा देवी` — and the dedupe keyed
  on the name. Panchayat samiti read 109% of the seats Jharkhand has.

### Changed

- **Jharkhand is read per document by whichever reader worked.** All 117
  documents were OCR'd with Surya and scored against their own text layer. The
  model wins on 88 and fails on 29 — those PDFs set Devanagari in Kruti Dev
  without embedding it, so the page renders as raw Latin codepoints and the model
  transcribes the wreckage. Preferring OCR everywhere would have cost 3,206 rows;
  the text layer everywhere would have cost about 1,500.

  | | v0.1.0 | v0.1.1 |
  |---|---|---|
  | Jharkhand rows | 23,599 | 27,698 |
  | mukhiya, of published | 84.1% | 93.3% |
  | panchayat samiti | 91.5% | 94.2% |
  | `gp_ward` seats that cannot be told apart | 8.1% | 3.2% |
  | seat identifiers still drawn as pictures | 1.9% | 0.7% |

  **The trade, so nobody has to find it themselves:** rows naming no panchayat
  rise from 2.9% to 3.5% of `gp_ward`, and rows with no seat number from 2.3% to
  3.9%. 4,099 seats were recovered that did not exist in the corpus before, and a
  larger share of *those* are incompletely identified.

### How to read "94% of published"

Not as precision. Coverage compares rows we hold against the seat count a state publishes, and
a reader that **invents** rows scores better on it than one that does not. Jharkhand's mukhiya
count read 102% of the gram panchayats the state has before any of this work — impossible, and
it looked like excellent coverage.

Both readers here get pages wrong in both directions. On one Ranchi page the model returned
nothing, the text layer returned four rows, and the page holds three. So coverage is a
floor-and-ceiling sanity check, not an accuracy measure, and the honest error bar on any
per-state figure in this release is wider than the figure's own precision suggests.

### Known and not fixed

- **`seat_id_raw` is still Kruti Dev on 66% of rows** — `I x<+ok@01@01&lq.Mh`.
  It is the raw record, and for the 29 documents whose render is broken it is the
  only form available. Installing the font and re-rendering those would close it.

## Unreleased — v0.1.0

The first tagged release, and the first time the whole corpus is pinned by hash.

### Corrected

- **A worklist note had been false for two commits.** `panchayat_not_named` told
  every reader that Jharkhand's scanned districts named the panchayat on 34% of
  rows against 92% for the typeset ones, and prescribed re-OCR. Measured against
  the parse it shipped with: **99.9% against 96.2%** — the scanned districts were
  the *better* arm, and 519 of the 524 rows still unnamed were in digital-text
  documents that re-OCR would never touch. The claim outlived the two commits
  that made it false (`1c858f4`, `5144d09`). WORKLIST.md is generated from these
  notes, so the false statement shipped with the data. Now rewritten, and the
  three defects behind those rows named separately.

- **Koderma's 261 unnamed rows were not a naming failure.** On pages 30–35 of its
  notification the seat column is *drawn*, 33–51 embedded images a page, so the
  text layer keeps only the district's roman numeral and every row reads `VI`.
  This is the same defect already documented for Lohardaga, and it is now read:
  drawn seats recovered across the state go from 135 to **1,235**.

- **18 rows named a caption rather than a place.** The identifier puts its number
  after "territorial constituency no.", and only the Kruti Dev spelling of that
  label was recognised, so on a Devanagari page the caption itself was published
  as the gram panchayat. A reader joining on the name got a match that was not a
  place. `बगदा` and its neighbours are now read correctly.

### Changed

- **The per-state tables are parquet, not gzipped CSV.** Reading a state table
  drops from 0.80 s to 0.06 s, which a consumer pays on every grouping. Types come
  from `dictionary.py` rather than inference, so a ward number of `07` cannot be an
  integer in one state and a string in another, and **null is now distinct from
  blank** — `woman_reserved` unknown and `woman_reserved` false are different
  facts, and CSV could only write both as the empty string.

  A value that will not cast now stops the build. That found two real parser
  defects rather than two reasons to loosen a type: Uttarakhand was writing whole
  constituency strings such as `17-गुलडिया` into `seat_no`, declared an integer,
  and Goa was writing `Unopposed` into `votes`.

  `pyarrow` is pinned, and the manifest records the version that wrote it, because
  parquet stamps its writer into every footer — upgrading it rewrites every
  SHA-256 without a single value changing.

- **`master_dropped.csv` and `master_key_collisions.csv` stay CSV.** Neither is the
  published product; they exist to be opened by someone chasing a defect, and a
  format you cannot grep is the wrong one for that.

- **Jharkhand's scans are read with Surya, not tesseract.** Tesseract read this
  form's Devanagari reliably and its numerals badly — the separators of a seat
  identifier survived and the digits between them came back as commas, so
  `IV/चतरा /5/18/सलैया –(1)` was read as `[४/चतरा /5,//8,//सलैया -(7)`. Worse than a
  blank: `18` arriving as `8` is a plausible wrong value pointing at a different
  seat.

  Measured on a seeded sample of 22 pages across 10 documents, scored by whether
  the identifier resolves to a complete seat identity:

  | | tesseract | Surya |
  |---|---|---|
  | complete seat identities | 106 | 350 |
  | recovery rate | 28.6% | 91.4% |

  No document scored worse. Chatra went from 4/133 to 133/133.

  **Checked against known answers, not only against itself.** Parseability is
  not accuracy: a wrong digit parses as happily as a right one, which is how
  tesseract's reading of सलैया's panchayat as 8 rather than 18 passed every
  check for so long. The digital-text districts are the only pages here whose
  answers are already known — a typesetter wrote them, so their block, panchayat
  and ward numbers come out of the file rather than out of a camera. Rendered to
  images and re-read, Surya got **245 of 245 digits right**. Those pages are
  cleaner than a photocopy of the same form, so this bounds scan accuracy from
  above rather than measuring it; it is a necessary result, not a sufficient one.

  What moved in the corpus:

  | | before | after |
  |---|---|---|
  | Jharkhand rows | 23,599 | 26,555 |
  | `gp_ward` rows that cannot be told apart | 1,161 | 92 |
  | open gaps, excluding the missing-district estimate | 3,828 | 3,032 |
  | districts holding more heads than gram panchayats | 292 | 131 |
  | seats uniquely keyed, whole corpus | 99.1% | 99.2% |

  Mukhiya falls from 4,429 to 3,654 and that is the correction, not a loss. The
  old figure was 102% of the 4,345 gram panchayats Jharkhand has, which cannot
  happen; Latehar alone claimed 407 heads for about 116 panchayats.

- **`data/jharkhand/ocr/` is now committed** (~4 MB). It was ignored while
  tesseract produced it, on the grounds that anyone could regenerate it from the
  committed PDFs in forty minutes. Surya needs an Apple-Silicon Mac and about six
  hours, so ignoring it would have left one machine in the world able to rebuild
  the state.

### Fixed

- **Seat numbers printed with a trailing hyphen** were not read. `SEAT_TAIL`
  recognised `(01)`, `¼01½` and `&01`, but the panchayat samiti form prints
  `XII दुमका/04/काठीकुण्ड-01`. Three documents resolved no seat number at all for
  want of it — on tesseract and on Surya alike, so it was a parser gap rather than
  a scan one. **+393 seat numbers, no row whose value changed.**

- **Kruti Dev place names split down the middle.** `/` is both a separator and the
  letter ध, guarded by "a separator is never followed by `k`" — but ध is written
  `/k` in खरौंधी and `/;` in `e/; ckxcsM+k`, which is मध्य बागबेड़ा. East Singhbhum's
  names came apart in half and the rows named no panchayat while the name sat in
  the string. **+116 panchayat names, no row whose value changed.**

### Notes for anyone holding earlier numbers

Jharkhand's seat-level figures move in this release, and they move because rows
that previously identified no seat now identify one. Row counts and reservation
shares are not intended to move; the release check requires that no other state
moves at all.
