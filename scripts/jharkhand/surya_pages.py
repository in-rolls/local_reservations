"""OCR every PNG in a directory, writing <name>.txt beside each.

Exists because surya-ocr pins pillow<11 and pdfplumber needs >=12.2, so the
model and the PDF reader cannot share an interpreter. ocr_seats.py has to have
both - pdfplumber to find the pages whose seat column is drawn, the model to
read them - so it runs under the repository's interpreter and calls this one
under savitr's, once, for a whole directory.

Once, and not per page: loading the weights costs more than reading a page, so a
call per page would spend most of the run in startup.
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "common"))
import ocr_engine  # noqa: E402  - the model path, stated in one place


def main():
    if len(sys.argv) != 2:
        return print(__doc__.strip()) or 2
    directory = pathlib.Path(sys.argv[1])
    pages = sorted(directory.glob("*.png"))
    if not pages:
        print(f"no PNGs in {directory}", file=sys.stderr)
        return 1
    engine = ocr_engine.engine()
    for index, page in enumerate(pages, 1):
        out = page.with_suffix(".txt")
        if out.exists():
            continue
        text, _ = engine.ocr_image(str(page))
        out.write_text(text, encoding="utf-8")
        print(f"\r  {index}/{len(pages)}", end="", file=sys.stderr)
    print(file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
