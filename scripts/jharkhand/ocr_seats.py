"""Read the seat identifiers that Jharkhand printed as pictures.

On three pages of the Lohardaga notification the whole seat column is embedded
images rather than text - 40 of them per page - so pdfplumber sees only the
district's roman numeral and 121 rows end up identifying no seat at all. They
are the largest single key collision in the corpus.

The information is not missing. Those images render clean Unicode Devanagari,
easier to read than the Kruti Dev the rest of the state is printed in:

    XVII लोहरदगा /6/1/ अलौदी - (6)
         district  block/gp  panchayat  ward

**The names are OCR'd; the numbers are not.** Tesseract reads the Devanagari
reliably and the Latin digits badly - 10 comes back as 20, 11 as 2, 12 as 22 -
and a wrong ward number is worse than none, because it silently points at
another seat. So the ward number is derived from the document's own ordering
instead: wards run consecutively within a panchayat, so the longest clean run
the OCR did read anchors the rest.

Writes data/jharkhand/2015/image_seats.csv, which parse.py reads. Cached and
committed, because OCR is slow and its output should be reviewable rather than
regenerated silently on every parse.
"""

import argparse
import collections
import csv
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
JHARKHAND = ROOT / "data" / "jharkhand" / "2015"
OUT = JHARKHAND / "image_seats.csv"

COLUMNS = ["source_pdf", "source_page", "serial", "name_ocr", "district_roman",
           "block_no", "gp_no", "gram_panchayat", "ward_no", "ward_no_ocr"]

# The whole page is read, not just the seat column. The serial number in the
# first column is what joins an OCR line back to a parsed row, and the name
# beside it confirms the join - the OCR finds more rows on a page than the
# parser does (38 against 34 on page 22), so matching by position would file
# every seat against the wrong person.
CROP_FROM = 0.0

# A page whose seat column is text runs its words out to about 0.92 of the
# width; one whose column is pictures stops around 0.71, because the text ends
# where the images begin. Measured, not guessed.
TEXT_REACHES = 0.75
DPI = 400

LINE = re.compile(r"/(\S*)/(\S*)/\s*(\S+)\s*-\s*\((\S*)\)")
ROMAN = re.compile(r"([IVXLC]{2,6})")
# serial, then the name up to the post - both sides of the join
HEAD = re.compile(r"^\W*(\d{1,3})\s*[|.]?\s*([\u0900-\u097F][\u0900-\u097F\s]{2,40}?)\s*(?:ग्राम|\|)")


def image_pages(path):
    """Pages whose seat column is drawn rather than typed.

    Identified by the text stopping short of the column: a page with real text
    there runs to the page's right edge, one without stops well before it.
    """
    import pdfplumber
    found = []
    with pdfplumber.open(str(path)) as pdf:
        for number, page in enumerate(pdf.pages, 1):
            words = page.extract_words()
            if not words or not page.images:
                continue
            # Pages 21 and 25 are mixed - some rows typeset, some pasted in as
            # pictures - so their words reach the right edge and the threshold
            # skipped them, leaving 54 rows unidentified. Any page carrying a
            # crop of images is read; the join is on the serial number and
            # confirmed by the name, and only fills rows that named no
            # panchayat, so reading a page that did not need it costs nothing.
            rightmost = max(w["x1"] for w in words)
            if len(page.images) > 5 or rightmost < TEXT_REACHES * page.width:
                found.append((number, page.width))
    return found


def ocr_page(path, number, width):
    """Render the seat column and read it.

    Uses tempfile rather than a fixed /tmp path: a hardcoded one is not always
    readable by another process, and tesseract then returns nothing at all
    rather than an error, which reads exactly like a page with no text on it.
    """
    left = int(CROP_FROM * width / 72 * DPI)
    with tempfile.TemporaryDirectory() as scratch:
        stem = pathlib.Path(scratch) / "page"
        subprocess.run(
            ["pdftoppm", "-f", str(number), "-l", str(number), "-r", str(DPI),
             "-x", str(left), "-W", str(int(width / 72 * DPI) - left),
             "-png", str(path), str(stem)],
            capture_output=True, timeout=300)
        rendered = sorted(pathlib.Path(scratch).glob("page-*.png"))
        if not rendered:
            return []
        # hin alone mangles the roman numeral and the digits; eng alone cannot
        # read the Devanagari. psm 4 is single column, which a ruled table is.
        text = subprocess.run(
            ["tesseract", str(rendered[0]), "stdout", "-l", "hin+eng",
             "--psm", "4"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=600).stdout
    return [line.strip() for line in text.split("\n") if LINE.search(line)]


def anchor_wards(values):
    """Ward numbers from the ordering, not from the digits.

    Within a panchayat the wards are consecutive, so any run the OCR did read
    correctly fixes the whole sequence. Take the longest run of values that
    increase by one at consecutive positions and extrapolate from it. Falling
    back to the OCR would mean shipping a number that points at another seat.
    """
    numbers = [int(v) if v.isdigit() else None for v in values]
    best = (0, 0, 0)          # length, index, value
    for start in range(len(numbers)):
        if numbers[start] is None:
            continue
        length = 1
        while (start + length < len(numbers)
               and numbers[start + length] == numbers[start] + length):
            length += 1
        if length > best[0]:
            best = (length, start, numbers[start])
    if not best[0]:
        return [""] * len(values)
    _, index, value = best
    first = value - index
    if first < 1:
        first = 1
    return [str(first + offset) for offset in range(len(values))]


def read(path):
    rows = []
    for number, width in image_pages(path):
        lines = ocr_page(path, number, width)
        parsed = []
        for line in lines:
            found = LINE.search(line)
            roman = ROMAN.search(line)
            head = HEAD.match(line)
            parsed.append({
                "serial": head.group(1) if head else "",
                "name_ocr": head.group(2).strip() if head else "",
                "district_roman": roman.group(1) if roman else "",
                "block_no": found.group(1),
                "gp_no": found.group(2),
                "gram_panchayat": found.group(3),
                "ward_no_ocr": found.group(4),
            })
        # the block number is the same all down a page, so the majority wins
        block = collections.Counter(
            p["block_no"] for p in parsed if p["block_no"].isdigit())
        block_no = block.most_common(1)[0][0] if block else ""

        # panchayats appear in runs; number them within the page and fix each
        # run's ward sequence
        start = 0
        for index in range(len(parsed) + 1):
            same = (index < len(parsed)
                    and parsed[index]["gram_panchayat"]
                    == parsed[start]["gram_panchayat"])
            if same:
                continue
            group = parsed[start:index]
            wards = anchor_wards([p["ward_no_ocr"] for p in group])
            for offset, item in enumerate(group):
                item["ward_no"] = wards[offset]
            start = index

        # Serials run consecutively down a page, so the ones the OCR did read
        # fix the ones it did not - the same anchoring the ward numbers use.
        # Without it only 69 of 109 rows could be joined back to a parsed row.
        serials = anchor_wards([p["serial"] for p in parsed])
        for item, serial in zip(parsed, serials):
            item["serial"] = serial

        for item in parsed:
            rows.append(dict(item, source_pdf=path.name, source_page=number,
                             block_no=block_no))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", help="only this document")
    args = ap.parse_args()

    rows = []
    for path in sorted(JHARKHAND.rglob("*.pdf")):
        if args.pdf and args.pdf.lower() not in path.name.lower():
            continue
        try:
            got = read(path)
        except Exception as exc:  # noqa: BLE001 - report and continue
            print(f"  {path.name}: {type(exc).__name__}", file=sys.stderr)
            continue
        if got:
            print(f"  {path.name}: {len(got)} seats from "
                  f"{len({r['source_page'] for r in got})} image pages")
            rows += got

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore",
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n{len(rows)} seats -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
