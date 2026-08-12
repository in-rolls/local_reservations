"""Surya, driven the same way for every state that needs it.

Imported by scripts/<state>/ocr.py. Only the paths and the "does this document
need OCR at all" test are per-state; the rendering, the rotation and the model
are not, and were on their way to being copied a second time.

**Runs under its own interpreter.** savitr pins pillow<11 where pdfplumber needs
>=12.2, so the OCR venv and the parsing one cannot be the same - see
requirements-ocr.txt. Nothing here imports anything else from common, so this
module loads in an interpreter that has only savitr.

Named `ocr_engine` and not `surya`: this directory goes on sys.path[0], and a
module called `surya` here would shadow the real surya package for savitr.
"""

import pathlib
import subprocess
import sys
import tempfile

# 200, not the 300 tesseract wanted: Surya's own preprocessing resizes to its
# input resolution, so the extra pixels cost render time and buy nothing.
DPI = 200

# Base Surya, converted to MLX once. NOT savitr's default terse model, which is
# distilled to emit voter rows from electoral rolls and would do exactly that
# to a reservation gazette.
DEFAULT_MODEL = pathlib.Path.home() / "Documents/GitHub/savitr/models/surya-mlx-4bit"

_ENGINE = None


def page_count(path):
    out = subprocess.run(["pdfinfo", str(path)], capture_output=True,
                         text=True).stdout
    for line in out.split("\n"):
        if line.startswith("Pages:"):
            return int(line.split()[1])
    return 0


def rotation(image):
    """How far the page is turned, from Tesseract's own orientation pass.

    Jharkhand's Godda blocks are printed sideways - the content is perfectly
    legible and OCR returned pure noise, because nothing had turned the page
    the right way up. Confidence is checked because the same call returns 1.03
    on a page that is merely a little skewed, and acting on that would rotate a
    good page into a bad one.
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


def engine(model=None):
    """The Surya model, loaded once. Importing savitr costs seconds and loading
    the weights costs more, so a per-page load would dominate a 600-page run."""
    global _ENGINE
    if _ENGINE is None:
        model = pathlib.Path(model or DEFAULT_MODEL)
        try:
            from savitr import MLXSuryaOCR
        except ImportError:
            sys.exit("savitr is not importable. This script runs under its own "
                     "interpreter - see requirements-ocr.txt.")
        if not model.exists():
            sys.exit(f"no Surya model at {model}. Convert it once with:\n"
                     f"  python -m mlx_vlm convert --hf-path "
                     f"datalab-to/surya-ocr-2 --mlx-path {model} -q --q-bits 4")
        _ENGINE = MLXSuryaOCR(str(model))
    return _ENGINE


def ocr(path, model=None, dpi=DPI, deskew=True, progress=True):
    """Every page of a PDF as Surya's HTML, form-feed separated.

    HTML rather than flattened text, because the table's cell boundaries are
    exactly what a whitespace layout makes the parser guess at.
    """
    pages = []
    total = page_count(path)
    for number in range(1, total + 1):
        with tempfile.TemporaryDirectory() as scratch:
            stem = pathlib.Path(scratch) / "p"
            subprocess.run(
                ["pdftoppm", "-f", str(number), "-l", str(number), "-r",
                 str(dpi), "-png", str(path), str(stem)],
                capture_output=True, timeout=300)
            rendered = sorted(pathlib.Path(scratch).glob("p-*.png"))
            if not rendered:
                pages.append("")
                continue
            turn = rotation(rendered[0]) if deskew else 0.0
            if turn:
                from PIL import Image
                with Image.open(rendered[0]) as image:
                    # The DPI has to be written back. Pillow drops the PNG's
                    # resolution on save, Tesseract then estimates it from the
                    # pixel size, and estimates it wrong: the same Godda page
                    # yields 14 rows with the tag and none without it. Every
                    # earlier attempt at that page failed for this reason and
                    # looked like a limit of the scan.
                    resolution = image.info.get("dpi", (dpi, dpi))
                    image.rotate(-turn, expand=True).save(rendered[0],
                                                          dpi=resolution)
            text, _ = engine(model).ocr_image(str(rendered[0]))
            pages.append(text)
        if progress:
            print(f"\r  {path.name[:44]:44s} {number}/{total}", end="",
                  file=sys.stderr, flush=True)
    if progress:
        print(file=sys.stderr)
    return "\f".join(pages)
