"""OCR the Jharkhand districts whose notifications are photographs.

Six districts - Dumka, Jamtara, Ramgarh, Latehar, Chatra and Godda - ship the
same PROFORMA-23 form as the rest of the state, but scanned rather than typeset,
so pdftotext returns nothing and they contributed no rows at all.

They are easier to read than the text districts, not harder. A scan OCRs into
Unicode Devanagari, while the typeset documents are Kruti Dev and have to be
transliterated afterwards.

**Surya, not tesseract, and the reason is the digits.** Tesseract reads this
form's Devanagari reliably and its numerals badly: the separators of a seat
identifier survive and the numbers between them come back as commas, so
"IV/चतरा /5/18/सलैया –(1)" was read as "[४/चतरा /5,//8,//सलैया -(7)". That is
worse than a blank, because 18 arriving as 8 is a plausible wrong value that
points at a different seat - the same failure ocr_seats.py records as "10 comes
back as 20, 11 as 2, 12 as 22".

Measured on a seeded sample of 22 pages across 10 documents, scored by whether
the identifier yields a complete seat identity through split_seat_id:

    tesseract   106/370   28.6%
    surya       350/383   91.4%

with no document worse and Chatra going from 4/133 to 133/133.

Surya emits HTML. The cache keeps it as HTML rather than flattening it, because
the table's cell boundaries are exactly what the whitespace layout of the old
text cache made everyone guess at.

Cached to data/jharkhand/ocr/<stem>.txt, form-feed separated so page numbers
survive, and **committed**, unlike the tesseract cache it replaces. That cache
was gitignored on the grounds that it was reproducible from the committed PDFs
in about forty minutes; this one takes ~4 hours and an Apple-Silicon Mac, so
ignoring it would mean only one machine in the world could rebuild Jharkhand.

Reproducing it, once:

    python3 -m venv ocrenv
    ./ocrenv/bin/pip install -r requirements-ocr.txt
    ./ocrenv/bin/python -m mlx_vlm convert --hf-path datalab-to/surya-ocr-2 \
        --mlx-path ~/surya-mlx-4bit -q --q-bits 4
    SURYA_MLX_PATH=~/surya-mlx-4bit make jharkhand-ocr

savitr is deliberately not in requirements.txt. It needs Apple Silicon for MLX,
and it pins pillow<11 where pdfplumber needs >=12.2, so the two cannot share an
interpreter - which is why the OCR gets its own requirements file and its own
venv. Nothing else in the repository imports it, and the parser reads the
committed cache rather than calling it, so only someone regenerating the cache
needs any of this.
"""

import argparse
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
JHARKHAND = ROOT / "data" / "jharkhand" / "2015"
CACHE = ROOT / "data" / "jharkhand" / "ocr"

# 200, not the 300 tesseract wanted: Surya's own preprocessing resizes to its
# input resolution, so the extra pixels cost render time and buy nothing.
DPI = 200

# Base Surya, converted to MLX once - see the module docstring for the command.
# NOT savitr's default terse model, which is distilled to emit voter rows from
# electoral rolls and would do exactly that to a reservation gazette.
#
# Overridable because the default is a path inside one person's home directory,
# and a recipe only one machine can follow is not a recipe.
MODEL = pathlib.Path(os.environ.get(
    "SURYA_MLX_PATH",
    pathlib.Path.home() / "Documents/GitHub/savitr/models/surya-mlx-4bit"))


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


_ENGINE = None


def engine():
    """The Surya model, loaded once. Importing savitr costs seconds and loading
    the weights costs more, so a per-page load would dominate a 593-page run."""
    global _ENGINE
    if _ENGINE is None:
        try:
            from savitr import MLXSuryaOCR
        except ImportError:
            sys.exit("savitr is not importable. This script runs under its own "
                     "interpreter - see the module docstring.")
        if not MODEL.exists():
            sys.exit(f"no Surya model at {MODEL}. Convert it once with:\n"
                     f"  python -m mlx_vlm convert --hf-path datalab-to/surya-ocr-2"
                     f" --mlx-path {MODEL} -q --q-bits 4")
        _ENGINE = MLXSuryaOCR(str(MODEL))
    return _ENGINE


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
                    # The DPI has to be written back. Pillow drops the PNG's
                    # resolution on save, Tesseract then estimates it from the
                    # pixel size, and estimates it wrong: the same Godda page
                    # yields 14 rows with the tag and none without it. Every
                    # earlier attempt at this page failed for that reason and
                    # looked like a limit of the scan.
                    dpi = image.info.get("dpi", (DPI, DPI))
                    image.rotate(-turn, expand=True).save(rendered[0], dpi=dpi)
            text, _ = engine().ocr_image(str(rendered[0]))
            pages.append(text)
        print(f"\r  {path.name[:44]:44s} {number}/{total}", end="",
              file=sys.stderr)
    print(file=sys.stderr)
    return "\f".join(pages)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="substring of the path to OCR")
    ap.add_argument("--force", action="store_true", help="ignore the cache")
    ap.add_argument("--all", action="store_true",
                    help="read the typeset documents too, not only the scans")
    args = ap.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    done = 0
    for path in sorted(JHARKHAND.rglob("*.pdf")):
        if args.only and args.only.lower() not in str(path).lower():
            continue
        cached = CACHE / f"{path.stem}.txt"
        if cached.exists() and not args.force:
            continue
        # "Already readable" turned out to be too generous. A typeset page's
        # text layer is Kruti Dev, which converts exactly but arrives with
        # everything the encoding costs: the block header comes back as
        # "iiiizz[[zz[[kkkk....MMMM" with its characters tripled and no mapping
        # recovers it, "I x<+ok" converts the district's roman numeral into
        # "प्", and on the one page compared the extraction found 24 rows where
        # the model found 25. Five separate defects on this branch came from
        # reading these documents as text. --all reads them as pictures instead.
        if has_text(path) and not args.all:
            continue
        text = ocr(path)
        cached.write_text(text, encoding="utf-8")
        done += 1
        print(f"  {path.name}: {len(text.split(chr(12)))} pages -> "
              f"{cached.relative_to(ROOT)}")
    print(f"\n{done} document(s) OCR'd into {CACHE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
