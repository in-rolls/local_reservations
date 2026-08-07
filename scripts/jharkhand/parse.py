"""Parse Jharkhand panchayat reservation, 2015.

One folder per district. The filenames suggest a tier ("GARHWA MUKHIYA.pdf")
but they lie: several are named "RANCHI ZP PSS MUKHIYA GPS" and hold the Zila
Parishad, Panchayat Samiti, Mukhiya and ward-member lists one after another.
Trusting the filename gave 12,509 "mukhiya" seats against Jharkhand's ~4,345
gram panchayats.

So every PDF is read once and each row is assigned a tier from its *post*
column, and each tier is written to its own file:

    eqf[k;k              mukhiya            gram panchayat head   <- GP level
    xzke iapk;r lnL;     ward_member        gram panchayat ward
    iapk;r lfefr lnL;    panchayat_samiti   block
    ftyk ifj"kn lnL;     zila_parishad      district

Two things make this state different from Goa:

* **Caste and gender are separate columns** - column 3 is "vuqlwfpr tutkfr",
  column 4 is "efgyk" or "vU;" - so the shared normalizer's caste_of() and
  woman_of() are called directly rather than normalize_reservation().
* **There is no English printing.** Everything is legacy Kruti Dev, so person
  and place names come out as mojibake. The reservation decodes fine, being a
  closed vocabulary, and each seat is still uniquely keyed by (district, block
  number, seat number) from the last column.

Writes data/jharkhand/<tier>_reservation_2015.{csv,jsonl}.
"""

import argparse
import collections
import pathlib
import re
import sys

import pdfplumber

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "common"))
import emit  # noqa: E402
from normalize import _undouble, caste_of, is_vacant, label, woman_of  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
JHARKHAND = ROOT / "data" / "jharkhand" / "2015"

COLUMNS = ["state", "year", "district", "block", "block_no", "seat_no",
           "constituency", "tier", "reservation", "caste_reservation",
           "woman_reserved", "winner", "vacant", "reservation_raw", "script"]

# Kruti Dev for each post. "neoqf[k;k" is a *deputy* mukhiya, so the match is
# exact rather than a substring.
TIERS = {
    "eqf[k;k": "mukhiya",
    "xzke iapk;r lnL;": "ward_member",
    "iapk;r lfefr lnL;": "panchayat_samiti",
    'ftyk ifj"kn lnL;': "zila_parishad",
}
TIER_BY_KEY = {_undouble(k): v for k, v in TIERS.items()}

# "iz[k.M & [kjkSaa/kh" = prakhand (block) - <name>. Read from the page's layout
# text, because the table renders this header with characters multiplied
# ("iiiizz[[zz[[kkkk....MMMM").
RE_BLOCK = re.compile(r"iz\[k\.M\s*&\s*(\S[^\n]{0,40})")

# last column: "I x<+ok@01@01&lq.Mh" - <district>@<block no>@<seat no>&<name>
RE_SEAT_ID = re.compile(r"@\s*(\d+)\s*@\s*(\d+)\s*&\s*(.*)$")

# Fallback for the districts whose tables carry no ruling lines. pdfplumber
# finds no table there and the rows are simply lost - 9 of the 19 districts
# that *do* have readable mukhiya text were being dropped this way. The post
# token is a reliable anchor in the layout text:
#
#   tudjkt nsoh    eqf[k;k vukjf{kr    efgyk    I x<+ok@01@01&lq.Mh
RE_TEXT_ROW = re.compile(
    r"^(?P<name>.*?)\s*(?P<post>" + "|".join(re.escape(k) for k in TIERS) + r")"
    r"\s+(?P<caste>.+?)\s+(?P<woman>efgyk|vU;)\s+(?P<seat>\S.*)$")


def clean(cell):
    return re.sub(r"\s+", " ", (cell or "").replace("\n", " ")).strip()


def tier_of(cell):
    return TIER_BY_KEY.get(_undouble(clean(cell)))


def district_of(folder):
    """"1. GARHWA MUKHIYA PSS" -> "Garhwa". The folder names are the only
    readable place-names in this corpus."""
    name = re.sub(r"^\s*\d+\s*[.)]?\s*", "", folder.name)
    name = re.sub(r"\b(MUKHIYA|PSS|GPS|ZP)\b", "", name, flags=re.I)
    name = re.sub(r"[()&]", " ", name)
    return " ".join(name.split()).title()


def parse_pdf(path, district):
    rows = []
    block = ""
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            found = RE_BLOCK.search(page.extract_text() or "")
            if found:
                block = clean(found.group(1))
            before = len(rows)
            for table in page.find_tables():
                for raw in table.extract():
                    cells = [clean(c) for c in raw]
                    if len(cells) < 5:
                        continue
                    tier = tier_of(cells[1])
                    if not tier:
                        continue          # header, spacer, or an unknown post
                    caste, woman = caste_of(cells[2]), woman_of(cells[3])
                    if caste is None or woman is None:
                        continue
                    seat = RE_SEAT_ID.search(cells[4])
                    block_no, seat_no, name = ("", "", cells[4])
                    if seat:
                        block_no, seat_no, name = (seat.group(1), seat.group(2),
                                                   clean(seat.group(3)))
                    rows.append(emit.stamp({
                        "state": "Jharkhand", "year": "2015",
                        "district": district, "block": block,
                        "block_no": block_no, "seat_no": seat_no,
                        "constituency": name, "tier": tier,
                        "reservation": label(caste, woman),
                        "caste_reservation": caste, "woman_reserved": woman,
                        "winner": cells[0], "vacant": int(is_vacant(cells[0])),
                        "reservation_raw": f"{cells[2]} | {cells[3]}",
                        "script": "krutidev",
                    }, path, page.page_number, ROOT))

            if len(rows) == before:
                rows += _from_text(page, path, district, block)
    return rows


def _from_text(page, path, district, block):
    """Read a page that has no ruled table, using the post token as the anchor."""
    out = []
    for line in (page.extract_text(layout=True) or "").split("\n"):
        found = RE_TEXT_ROW.match(clean(line))
        if not found:
            continue
        tier = tier_of(found.group("post"))
        caste = caste_of(found.group("caste"))
        woman = woman_of(found.group("woman"))
        if not tier or caste is None or woman is None:
            continue
        seat = RE_SEAT_ID.search(found.group("seat"))
        block_no, seat_no, name = ("", "", found.group("seat"))
        if seat:
            block_no, seat_no, name = (seat.group(1), seat.group(2),
                                       clean(seat.group(3)))
        winner = clean(found.group("name"))
        out.append(emit.stamp({
            "state": "Jharkhand", "year": "2015", "district": district,
            "block": block, "block_no": block_no, "seat_no": seat_no,
            "constituency": name, "tier": tier,
            "reservation": label(caste, woman), "caste_reservation": caste,
            "woman_reserved": woman, "winner": winner,
            "vacant": int(is_vacant(winner)),
            "reservation_raw": f"{found.group('caste')} | {found.group('woman')}",
            "script": "krutidev",
        }, path, page.page_number, ROOT))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="only the first N district folders")
    args = ap.parse_args()

    folders = sorted(p for p in JHARKHAND.iterdir() if p.is_dir())[: args.limit]
    rows, failed = [], []
    for folder in folders:
        district = district_of(folder)
        # PDFs are nested a further level in several districts
        # (HAZARIBAG/HAZARIBAG MUKHIYA/*.pdf), so this must recurse -
        # a top-level glob saw 36 of the 117 files and silently lost
        # two thirds of the state.
        for path in sorted(folder.rglob("*.pdf")):
            try:
                rows += parse_pdf(path, district)
            except Exception as exc:  # noqa: BLE001 - report, keep going
                failed.append((path.name, type(exc).__name__))
            print(f"\r  {district:18s} rows={len(rows)}", end="", file=sys.stderr)
    print(file=sys.stderr)

    by_tier = collections.defaultdict(list)
    for row in rows:
        by_tier[row["tier"]].append(row)

    for tier in sorted(by_tier):
        subset = by_tier[tier]
        stem = ROOT / "data" / "jharkhand" / f"{tier}_reservation_2015"
        csv_path, _ = emit.write(subset, stem, COLUMNS)
        districts = {r["district"] for r in subset}
        blocks = {(r["district"], r["block"]) for r in subset}
        women = sum(r["woman_reserved"] for r in subset)
        print(f"{tier:18s} {len(subset):6d} seats  {len(blocks):4d} blocks  "
              f"{len(districts):2d}/{len(folders)} districts  "
              f"women {women / max(len(subset), 1) * 100:4.1f}%  -> {csv_path.name}")

    print("\nmukhiya reservation split:")
    for k, v in collections.Counter(r["reservation"]
                                    for r in by_tier["mukhiya"]).most_common():
        print(f"   {v:6d}  {v / max(len(by_tier['mukhiya']), 1) * 100:5.1f}%  {k}")
    if failed:
        print(f"\nunreadable: {len(failed)} -> {failed[:5]}")


if __name__ == "__main__":
    main()
