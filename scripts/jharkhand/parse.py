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
import canon  # noqa: E402
import emit  # noqa: E402
from normalize import _undouble, caste_of, is_vacant, label, woman_of  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
JHARKHAND = ROOT / "data" / "jharkhand" / "2015"

COLUMNS = ["state", "year", "district", "block", "block_no",
           "gram_panchayat", "gp_no", "ward_no", "seat_no", "seat_id_raw",
           "tier", "tier_local", "reservation", "caste_reservation",
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
# Stop at "ftyk" (zila): the header reads "iz[k.M & rksipk¡ph ftyk & /kuckn",
# and taking the lot made the block name "Topchanchi zila Dhanbad".
RE_BLOCK = re.compile(r"iz\[k\.M\s*&\s*(\S[^\n]{0,40}?)(?:\s*ftyk\b|$)")

# The last column is not a name. It is a compound seat identifier that runs the
# district, the block, the gram panchayat and the constituency number together:
#
#   XV cksdkjks@08 pkl@18 lruiqj@izk0fu0{ks0 la0&12
#   |  |          |       |      |                |
#   |  district   |       |      the label "izk0fu0{ks0 la0" = territorial
#   roman         block   gram   constituency number
#                         panchayat
#
# Reading it whole as "constituency" cost more than it looks: `block` came out
# 52-100% blank across the four tiers when the block is right there in the
# string, ward_member had no ward number at all for 6,174 rows, and 121 rows
# collided on a seat key that was nothing but a roman numeral.
#
# Four tiers print four layouts and the typesetters bracket the number five
# ways, so the parts are found by searching rather than by position, and
# anything that does not resolve is left blank rather than guessed.
SEAT_LABEL = re.compile(r"izk0\s*fu0\s*\{ks0\s*la0")
SEAT_TAIL = re.compile(r"(?:¼\s*(\d+)\s*½|\(\s*(\d+)\s*\)|&\s*(\d+))\s*$")
SEAT_ROMAN = re.compile(r"(?<![A-Za-z])([IVXLC]{1,6})(?![A-Za-z])")
SEAT_NUMBERED = re.compile(r"^(\d+)[\s/]+(.*\S)$")

# Fallback for the districts whose tables carry no ruling lines. pdfplumber
# finds no table there and the rows are simply lost - 9 of the 19 districts
# that *do* have readable mukhiya text were being dropped this way. The post
# token is a reliable anchor in the layout text:
#
#   tudjkt nsoh    eqf[k;k vukjf{kr    efgyk    I x<+ok@01@01&lq.Mh
RE_TEXT_ROW = re.compile(
    r"^(?P<name>.*?)\s*(?P<post>" + "|".join(re.escape(k) for k in TIERS) + r")"
    r"\s+(?P<caste>.+?)\s+(?P<woman>efgyk|vU;)\s+(?P<seat>\S.*)$")


def split_seat_id(text, tier):
    """Pull the district, block, gram panchayat and constituency number apart.

    The same shape means different things at different tiers - a zila parishad
    identifier names only the district, a panchayat samiti one ends with the
    block, and a ward one ends with the gram panchayat - so the tier decides
    what the trailing name is rather than the parser guessing. Where a string
    does not resolve to a known layout, nothing is returned: a wrong block name
    would be indistinguishable from a right one, and this corpus is legacy-font
    mojibake where nobody would notice.
    """
    s = re.sub(r"\s+", " ", (text or "").strip())
    if not s:
        return {}
    out = {}

    # the number is bracketed five ways across the districts: la0&12, ¼12½,
    # (12), &12, - (12)
    s = SEAT_LABEL.sub("", s)
    tail = SEAT_TAIL.search(s)
    if tail:
        out["seat_no"] = next(g for g in tail.groups() if g)
        s = s[:tail.start()]
    s = s.strip().strip("&-/@ ").strip()

    # the roman numeral is the district's index and floats: it opens the string
    # in most districts and trails it in East Singhbhum
    roman = SEAT_ROMAN.search(s)
    if roman:
        out["district_roman"] = roman.group(1)
        s = (s[:roman.start()] + " " + s[roman.end():])
    s = s.strip().strip("&-/@ ").strip()

    parts = [p.strip(" &-/") for p in s.split("@")]
    parts = [p for p in parts if p]

    def kind(p):
        if re.fullmatch(r"\d+", p):
            return "N"
        return "M" if SEAT_NUMBERED.match(p) else "T"

    shape = "".join(kind(p) for p in parts)
    out["shape"] = shape

    def numbered(p):
        found = SEAT_NUMBERED.match(p)
        return (found.group(1), found.group(2)) if found else ("", p)

    if shape == "TMM":            # district@NN block@NN gram panchayat
        out["block_no"], out["block"] = numbered(parts[1])
        out["gp_no"], out["gram_panchayat"] = numbered(parts[2])
    elif shape == "TNNT":         # district@NN@NN@gram panchayat
        out["block_no"], out["gp_no"] = parts[1], parts[2]
        out["gram_panchayat"] = parts[3]
    elif shape == "TNM":          # district@NN@NN gram panchayat
        out["block_no"] = parts[1]
        out["gp_no"], out["gram_panchayat"] = numbered(parts[2])
    elif shape == "TMT":          # district@NN block@gram panchayat
        out["block_no"], out["block"] = numbered(parts[1])
        out["gram_panchayat"] = parts[2]
    elif shape == "NNT":          # the district is missing, the rest is not
        out["block_no"], out["gp_no"] = parts[0], parts[1]
        out["gram_panchayat"] = parts[2]
    elif shape == "TNT":
        # The trailing name is the block at panchayat samiti level and the gram
        # panchayat below it. Same shape, different meaning - which is why this
        # function needs the tier.
        out["block_no"] = parts[1]
        out["block" if tier == "panchayat_samiti" else "gram_panchayat"] = parts[2]
    elif shape == "NT":
        out["block_no"] = parts[0]
        out["block" if tier == "panchayat_samiti" else "gram_panchayat"] = parts[1]
    elif shape == "T":
        # A bare name is the gram panchayat at mukhiya level, where the
        # identifier is only ever the name, and the district at zila parishad
        # level, whose constituencies are numbered across the whole district.
        if tier == "mukhiya":
            out["gram_panchayat"] = parts[0]
    return out


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


def seat_row(district, page_block, tier, caste, woman, raw, winner, raw_label):
    """One row, with the compound seat identifier taken apart.

    The block parsed out of the identifier wins over the one read from the page
    header: the header is a page-level guess that does not change when the table
    crosses a block boundary mid-page, while the identifier is stated on the row
    itself.
    """
    seat = split_seat_id(raw, tier)
    number = seat.get("seat_no", "")
    return {
        # Which of the two the block came from, so fill_block_names() can build
        # its lookup from the rows that state it and ignore the rest. Not a
        # declared column, so emit drops it.
        "block_from": "identifier" if seat.get("block") else
                      ("page" if page_block else ""),
        "state": "Jharkhand", "year": "2015", "district": district,
        "block": seat.get("block") or page_block,
        "block_no": seat.get("block_no", ""),
        "gram_panchayat": seat.get("gram_panchayat", ""),
        "gp_no": seat.get("gp_no", ""),
        # the trailing number is the ward at ward-member level and the seat
        # within the district or block above it
        "ward_no": number if tier == "ward_member" else "",
        "seat_no": "" if tier == "ward_member" else number,
        "seat_id_raw": clean(raw),
        "tier": canon.tier_of(tier, "Jharkhand"), "tier_local": tier,
        "reservation": label(caste, woman),
        "caste_reservation": caste, "woman_reserved": woman,
        "winner": winner, "vacant": int(is_vacant(winner)),
        "reservation_raw": raw_label, "script": "krutidev",
    }


def fill_block_names(rows):
    """Give a block its name where the row states only its number.

    Half the districts print the block as a number and nothing else
    ("yksgjnxk@5@10@ck?kk"), while the panchayat samiti sheets for the same
    district print both. So the name is recovered by joining on a key that both
    sides state, not by inferring anything.

    The lookup is built only from blocks that came from the seat identifier.
    The page header is not usable for it: it is read once per page and does not
    change when a table crosses a block boundary mid-page, which is how Dhanbad
    ended up with three different names against block 04.
    """
    lookup = collections.defaultdict(collections.Counter)
    for row in rows:
        if row.get("block_from") == "identifier" and row["block_no"]:
            lookup[(row["district"], row["block_no"])][row["block"]] += 1

    resolved = {key: names.most_common(1)[0][0]
                for key, names in lookup.items() if len(names) == 1}
    filled = 0
    for row in rows:
        if row.get("block_from") == "identifier" or not row["block_no"]:
            continue
        name = resolved.get((row["district"], row["block_no"]))
        if name:
            row["block"], filled = name, filled + 1
    return filled, len(lookup) - len(resolved)


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
                    rows.append(emit.stamp(seat_row(
                        district, block, tier, caste, woman, cells[4],
                        cells[0], f"{cells[2]} | {cells[3]}"),
                        path, page.page_number, ROOT))

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
        winner = clean(found.group("name"))
        out.append(emit.stamp(seat_row(
            district, block, tier, caste, woman, found.group("seat"), winner,
            f"{found.group('caste')} | {found.group('woman')}"),
            path, page.page_number, ROOT))
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

    # after every district is read, because a block named only by number in one
    # district's sheets is named in full in another's
    filled, ambiguous = fill_block_names(rows)
    print(f"block names joined on (district, block_no): {filled:,} rows filled, "
          f"{ambiguous} keys left ambiguous", file=sys.stderr)

    by_tier = collections.defaultdict(list)
    for row in rows:
        by_tier[row["tier_local"]].append(row)

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
