"""Re-OCR the Andhra Pradesh gazettes, because their embedded text layer is bad.

These PDFs already carry a text layer, but it is itself OCR output and it is
wrong in ways that matter: `5C` for SC, `8c` for BC, `t4` for 14, `72` for 12.
Parsing it means repairing those by hand and hoping the repairs are right.

Re-rendering the page and running Tesseract at `--psm 4` (one column of text of
variable sizes, which is what a wide ruled table is) fixes them at the source:

    embedded   44 Alamuru ALAMURU sc(w) t4 Bc (w) UR (W) SC sc (w) BC ...
    re-OCR     44 Alamuru ALAMURU SC(W) 14 BC(W)  UR(W)  SC sc(w)  BC ...

`--psm 6` is much worse here - it reads the table rules as pipe characters and
garbles the row - so the mode matters more than the engine.

This also unlocks Anantapur, whose PDF has no text layer at all.

Output is cached as data/ap/ocr/<stem>.txt with a form feed between pages, so it
drops straight into the same page-splitting the parser already does, and a
re-parse costs nothing.
"""

import argparse
import pathlib
import shutil
import subprocess
import sys
import tempfile

from local_reservations.paths import ROOT

SOURCE = ROOT / "data" / "ap" / "2020_res_gp"
CACHE = ROOT / "data" / "ap" / "ocr"

DPI = 300
PSM = "4"


def page_count(path):
    out = subprocess.run(["pdfinfo", str(path)], capture_output=True,
                         text=True).stdout
    for line in out.splitlines():
        if line.startswith("Pages:"):
            return int(line.split()[1])
    return 0


def ocr_pdf(path, dpi=DPI, psm=PSM):
    """Render each page and OCR it; returns the text, form-feed separated."""
    pages = page_count(path)
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        for page in range(1, pages + 1):
            stem = pathlib.Path(tmp) / f"p{page}"
            subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page),
                            "-r", str(dpi), "-png", str(path), str(stem)],
                           capture_output=True)
            images = sorted(pathlib.Path(tmp).glob(f"p{page}-*.png"))
            if not images:
                out.append("")
                continue
            text = subprocess.run(
                ["tesseract", str(images[0]), "-", "--psm", psm],
                capture_output=True, text=True).stdout
            out.append(text)
            for image in images:
                image.unlink()
            print(f"\r  {path.name} {page}/{pages}", end="", file=sys.stderr)
    print(file=sys.stderr)
    return "\f".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-OCR cached files")
    ap.add_argument("--only", help="substring of a filename to limit to")
    args = ap.parse_args()

    if not shutil.which("tesseract"):
        sys.exit("tesseract not found - brew install tesseract")

    CACHE.mkdir(parents=True, exist_ok=True)
    for path in sorted(SOURCE.glob("*.pdf")):
        if args.only and args.only not in path.name:
            continue
        target = CACHE / f"{path.stem}.txt"
        if target.exists() and not args.refresh:
            print(f"  {path.name:18s} cached ({target.stat().st_size // 1024} KB)")
            continue
        text = ocr_pdf(path)
        target.write_text(text, encoding="utf-8")
        print(f"  {path.name:18s} -> {target.name} "
              f"({len(text.split(chr(12)))} pages, {len(text) // 1024} KB)")


if __name__ == "__main__":
    main()
