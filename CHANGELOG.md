# Changelog

What changed, and what it means for a number you may already have used. Entries
say when a figure moved and why, because a corpus that silently restates itself
is worse than one that does not change at all.

Corrections are listed first in each release, not last. The most useful thing
here is usually the thing that was wrong.

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
