"""OCR Karnataka's 2016 taluk and zilla panchayat result notifications.

195 documents, 586 pages, harvested from the Wayback Machine's copy of
karsec.gov.in - 169 taluk panchayats and 26 zilla panchayats. Karnataka
contributes nothing to either tier today; what it has is a gram panchayat
reservation history for 1993-2007, which names no winner by construction.

Every one of them is a photograph. The producer string on all 195 is
`RICOH Aficio MP 5002` - a copier - and pdfplumber extracts zero characters
from page 1 of each, so there is no text layer to prefer and no encoding
question to settle. Surya reads them directly.

**Surya reads Kannada.** Measured on the first page of Badami taluk before
committing to the run: it returned the notification prose and the five-column
table cell by cell, with `<br/>` where the winner's name is stacked above the
address. Its errors are concentrated in a systematic confusion of
sibilants - ಸೂ read as ಕೂ, ಕ್ಷ as ಕ್ನ - which lands mostly on the two closed
vocabularies, the reservation category and the party name. Those canonicalise
against a fixed list. The open field, the winner's name, does not, and its
error rate is what the bench has to measure.

The table is worth more than the tier count suggests. Column 5 is
`ಪ್ರತಿನಿಧಿಸಿದ ರಾಜಕೀಯ ಪಕ್ಷದ ಹೆಸರು` - the party the winner represented - which
almost nothing else in the corpus carries.

Cached to data/karnataka/ocr/<stem>.txt, form-feed separated so page numbers
survive, and committed: the run takes ~2.7 hours on Apple Silicon, so leaving
it out would mean only one machine could rebuild Karnataka.

    python3 -m venv ocrenv
    ./ocrenv/bin/pip install -r requirements-ocr.txt
    ./ocrenv/bin/python scripts/karnataka/ocr.py
"""

import argparse
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "common"))
import ocr_engine  # noqa: E402

DATA = ROOT / "data" / "karnataka"
CACHE = DATA / "ocr"

# All three sets go through Surya. The elected-member notifications have no
# text layer at all; the other two have one and it is Nudi/Baraha ASCII-encoded
# Kannada - "£ÀªÀÄÆ£É-1" for "ನಮೂನೆ-1" - with the zilla gazettes tripling their
# characters on top of that. The only maintained decoder found was
# aravindavk/ascii2unicode: GPL, no LICENSE file, absent from PyPI and
# self-described as Linux-only. Reading the picture is cheaper than adopting
# that, and it is the same call Jharkhand's Kruti Dev pages got.
SETS = ["tzp_2016_elected", "tzp_2016_reservation", "gp_2015"]

# Procedure, not data: a rule book, a returning-officer manual, a presiding-
# officer manual, and a general guide to the election. 402 of gp_2015's 544
# pages, about two hours of OCR, and not one row among them.
SKIP = ("Rules_Book", "GP_RO_Manual", "GP_PRO_Manual",
        "Karnataka_panchayatraj_chunavane")

MODEL = os.environ.get("SURYA_MLX_PATH")


def main():
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--only", help="substring of the filename to OCR")
    ap.add_argument("--force", action="store_true", help="ignore the cache")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    documents = [p for name in SETS
                 for p in sorted((DATA / name).glob("*.pdf"))
                 if not any(token in p.name for token in SKIP)]
    if args.only:
        documents = [p for p in documents if args.only.lower() in p.name.lower()]
    if args.limit:
        documents = documents[:args.limit]

    CACHE.mkdir(parents=True, exist_ok=True)
    # One flat cache. Every filename already carries its set - the harvester
    # names files after the archive path they came from - so a stem collision
    # across the three is not possible.
    stems = [p.stem for p in documents]
    assert len(set(stems)) == len(stems), "cache stems are not unique"

    done = skipped = 0
    for path in documents:
        target = CACHE / f"{path.stem}.txt"
        if target.exists() and not args.force:
            skipped += 1
            continue
        # deskew=False: these are flatbed copier scans, all portrait. The
        # orientation pass costs a tesseract call per page and Jharkhand needed
        # it only for one district printed sideways.
        text = ocr_engine.ocr(path, model=MODEL, deskew=False)
        target.write_text(text, encoding="utf-8")
        done += 1

    print(f"{done} read, {skipped} already cached -> "
          f"{CACHE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
