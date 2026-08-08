"""OCR the Jharkhand districts whose notifications are photographs.

Six districts - Dumka, Jamtara, Ramgarh, Latehar, Chatra and Godda - ship the
same PROFORMA-23 form as the rest of the state, but scanned rather than typeset,
so pdftotext returns nothing and they contributed no rows at all.

They are easier to read than the text districts, not harder. A scan OCRs into
Unicode Devanagari, while the typeset documents are Kruti Dev and have to be
transliterated afterwards.

Cached to data/jharkhand/ocr/<stem>.txt, form-feed separated so page numbers
survive, and gitignored: 604 pages take about forty minutes and the output is
reproducible from the committed PDFs.
"""

import argparse
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
JHARKHAND = ROOT / "data" / "jharkhand" / "2015"
CACHE = ROOT / "data" / "jharkhand" / "ocr"

DPI = 300
# psm 4 is one column of text of variable sizes, which is what a ruled table is.
# psm 6 reads the table rules as pipe characters and is markedly worse - the
# same finding as Andhra Pradesh.
PSM = "4"
LANG = "hin"


# A tier name in one of the two encodings we can actually read. Any of these
# means the text layer is usable; none means it is not, whatever its length.
READABLE = ("eqf[k;k", "xzke iapk;r", "iapk;r lfefr", 'ftyk ifj"kn',
            "मुखिया", "ग्राम पंचायत", "पंचायत समिति", "जिला परिषद")


def has_text(path):
    """True when the text layer is one we can read - not merely present.

    Asking "is there text?" skipped Chatra, Godda and Godda's blocks, which
    carry 86,000 to 375,000 characters of a legacy font that is neither Kruti
    Dev nor Unicode and decodes to "grgo-s r€-.Ff{ 6rzr rorRrf,". Length is not
    readability, and those three districts sat in the worklist as a source
    ceiling on the strength of it.
    """
    out = subprocess.run(["pdftotext", "-layout", str(path), "-"],
                         capture_output=True, text=True, errors="replace").stdout
    return any(token in out for token in READABLE)


def page_count(path):
    out = subprocess.run(["pdfinfo", str(path)], capture_output=True,
                         text=True).stdout
    for line in out.split("\n"):
        if line.startswith("Pages:"):
            return int(line.split()[1])
    return 0


def rotation(image):
    """How far the page is turned, from Tesseract's own orientation pass.

    Godda's blocks are printed sideways - the content is perfectly legible and
    OCR returned pure noise, because nothing had turned the page the right way
    up. Confidence is checked because the same call returns 1.03 on a page that
    is merely a little skewed, and acting on that would rotate a good page into
    a bad one.
    """
    out = subprocess.run(["tesseract", str(image), "stdout", "--psm", "0"],
                         capture_output=True, text=True, errors="replace",
                         timeout=300).stdout
    degrees = confidence = 0.0
    for line in out.split("\n"):
        if line.startswith("Rotate:"):
            degrees = float(line.split(":")[1])
        elif line.startswith("Orientation confidence:"):
            confidence = float(line.split(":")[1])
    return degrees if confidence >= 2.0 else 0.0


def ocr(path):
    pages = []
    total = page_count(path)
    for number in range(1, total + 1):
        with tempfile.TemporaryDirectory() as scratch:
            stem = pathlib.Path(scratch) / "p"
            subprocess.run(
                ["pdftoppm", "-f", str(number), "-l", str(number), "-r",
                 str(DPI), "-png", str(path), str(stem)],
                capture_output=True, timeout=300)
            rendered = sorted(pathlib.Path(scratch).glob("p-*.png"))
            if not rendered:
                pages.append("")
                continue
            turn = rotation(rendered[0])
            if turn:
                from PIL import Image
                with Image.open(rendered[0]) as image:
                    image.rotate(-turn, expand=True).save(rendered[0])
            pages.append(subprocess.run(
                ["tesseract", str(rendered[0]), "stdout", "-l", LANG,
                 "--psm", PSM],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=600).stdout)
        print(f"\r  {path.name[:44]:44s} {number}/{total}", end="",
              file=sys.stderr)
    print(file=sys.stderr)
    return "\f".join(pages)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="substring of the path to OCR")
    ap.add_argument("--force", action="store_true", help="ignore the cache")
    args = ap.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    done = 0
    for path in sorted(JHARKHAND.rglob("*.pdf")):
        if args.only and args.only.lower() not in str(path).lower():
            continue
        cached = CACHE / f"{path.stem}.txt"
        if cached.exists() and not args.force:
            continue
        if has_text(path):
            continue          # already readable, nothing to gain
        text = ocr(path)
        cached.write_text(text, encoding="utf-8")
        done += 1
        print(f"  {path.name}: {len(text.split(chr(12)))} pages -> "
              f"{cached.relative_to(ROOT)}")
    print(f"\n{done} document(s) OCR'd into {CACHE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
