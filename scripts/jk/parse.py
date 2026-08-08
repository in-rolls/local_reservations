"""Parse Jammu & Kashmir panchayat reservation, 2010 / 2016 / 2018.

J&K calls the gram panchayat a *halqa* and its wards *panch constituencies*, so
the two tiers here are `sarpanch` (halqa level) and `ward` (panch level).

Each year is laid out differently, so columns are located from the header row
rather than by fixed index:

  2016  15 columns, and the richest source in this project: district, block,
        halqa, panch ward, SC/ST/OC populations and percentages, and **two**
        reservation columns - one for the panch ward, one for the sarpanch of
        the halqa. So 2016 yields both tiers, and carries the populations that
        the allocation was based on, which makes the rule auditable.
  2010   5 columns: S.No, halqa, panch number, panch name, reservation. Ward
        tier only.
  2018   9 columns: district and block numbers and names, halqa, panch, and one
        reservation column. Ward tier only.

The holdings are ad-hoc - mixed granularity, inconsistent filenames, 2016
covering part of Jammu division and 2018 part of Kashmir - so what matters here
is honest coverage accounting, not clever parsing. validate.py does that.

Writes data/jk/{ward,sarpanch}_reservation_<year>.{csv,jsonl}.
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
from normalize import label, normalize_reservation  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
JK = ROOT / "data" / "jk"

COLUMNS = ["state", "year", "district", "district_declared", "block", "halqa",
           "ward_no",
           "ward_name", "tier", "tier_local", "reservation", "caste_reservation",
           "woman_reserved", "listing_scope", "pop_sc", "pop_st", "pop_oc",
           "pop_total", "reservation_raw", "script"]

# What each year's documents actually list. 2010 and 2016 are full rosters -
# they carry "Un Reserved" and "Open" rows - but the 2018 files are titled
# "Reservation of SC/ST/women & ST for panch constituencies" and contain *only
# the reserved wards*. Treating that as a roster implies 82% of J&K wards are
# women-reserved, which is an artefact of the document, not a finding. Any
# denominator computed from 2018 is wrong unless this column is respected.
LISTING_SCOPE = {"2010": "all_seats", "2016": "all_seats",
                 "2018": "reserved_only"}

# header text that leaks into the data when a header row is not skipped
HEADER_NOISE = {"name of district", "district name", "name of block",
                "block name", "name of halqa", "district", "block"}

def clean(cell):
    return re.sub(r"\s+", " ", (cell or "").replace("\n", " ")).strip()


def district_from_title(text):
    """2016 and 2018 print "... in respect of District Doda" above the table."""
    found = re.search(r"District\s+([A-Za-z][A-Za-z .\-]{2,25})", text or "")
    return clean(found.group(1)) if found else ""


# Jammu & Kashmir's districts as they stood in 2010. A closed list, which is
# what makes the district readable at all: the 2010 documents spell the word
# before it at least four ways - DISTRICT, Distrist, ISTRICT with the D lost to
# the scan, and sometimes nothing but a comma - so the word is matched by edit
# distance and the name that follows against this roster. Free-text capture was
# tried first and returned "JAMMU Name" and "REASI ANNEXURE".
DISTRICT_ROSTER = [
    "Jammu", "Samba", "Kathua", "Udhampur", "Reasi", "Rajouri", "Poonch",
    "Doda", "Ramban", "Kishtwar", "Anantnag", "Kulgam", "Pulwama", "Shopian",
    "Srinagar", "Budgam", "Ganderbal", "Bandipora", "Baramulla", "Kupwara",
    "Leh", "Kargil",
]

# Eight of the 2010 blocks name no district anywhere in their document. These
# come from outside the corpus and are marked as such rather than presented as
# something the page said - see the district_declared column.
DISTRICT_OF_BLOCK = {
    "dachhan": "Kishtwar", "marwah": "Kishtwar", "padder": "Kishtwar",
    "warwan": "Kishtwar", "inderbal": "Kishtwar", "nagsani": "Kishtwar",
    "gool": "Ramban", "ramsoo": "Ramban",
}

_WORD = re.compile(r"\b([A-Za-z]{5,9})\b")


def _distance(a, b):
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1,
                               previous[j - 1] + (x != y)))
        previous = current
    return previous[-1]


def district_from_document(text):
    """The district a 2010 document names, or "" if it names none.

    Prefers the name that follows a district-ish word; falls back to any roster
    name on the page, which is safe because these are district-level documents
    and the roster names are distinctive.
    """
    flat = re.sub(r"\s+", " ", text or "")
    for found in _WORD.finditer(flat):
        if _distance(found.group(1).upper(), "DISTRICT") <= 2:
            after = flat[found.end():found.end() + 30]
            for name in DISTRICT_ROSTER:
                if re.match(r"\W{0,3}" + name, after, re.I):
                    return name
    for name in DISTRICT_ROSTER:
        if re.search(r"\b" + name + r"\b", flat, re.I):
            return name
    return ""


def block_from_filename(path):
    """2010 names each file for its block. Verified rather than assumed: on the
    2,236 rows where the page also states a block, the two agree every time."""
    return re.sub(r"[()]", "", path.stem).strip()


def carry(values, index, current):
    """Read a column that is only printed on the first row of each group.

    Header text must be rejected *here*, not when the row is emitted. The
    header row is read before the guard sees it, so its text lands in the
    carried-forward variable and every subsequent row inherits it - which is
    how 1,398 J&K 2018 rows ended up in a district called "Name of District"
    even with a guard on the emit.
    """
    if index is None or index >= len(values):
        return current
    value = values[index]
    if not value or emit.is_header_text(value):
        return current
    return value


def map_columns(table_rows):
    """Locate each field by reading the header, not by fixed index.

    2016 alone ships three layouts - 15, 16 and 18 columns - and they disagree
    on where everything sits. Doda leads with the district, Kathua leads with a
    serial number, Batote puts the block second. Hard-coding indices read the
    serial number as the district and produced 33 districts for a state that
    has 22.

    Headers wrap across two or three rows, so the first few rows are joined
    column-wise before matching.
    """
    # A spanning title row ("Pyt-wise/Block-wise Reservation of SC/ST/Women
    # Panches & Sarpanches...") occupies column 0 with every other cell empty.
    # Joining it into the header puts "reserv" and "sc" in column 0, so the
    # serial-number column gets mapped as the reservation column. Only rows
    # with several filled cells are real header rows.
    def is_number_row(row):
        """The row of column numbers ("2 3 4 5 ...") sits under the header and
        would otherwise be joined into it, leaving every header ending in a
        digit so that suffix matches like "...sc" never fire."""
        filled = [clean(c) for c in row if clean(c)]
        return bool(filled) and all(c.isdigit() for c in filled)

    # The numeric row is not just noise to skip - it marks where the header
    # ends. Without that boundary the first data row gets joined in as header
    # ("... of panch sc 90"), and then no suffix match fires.
    boundary = next((i for i, r in enumerate(table_rows[:8]) if is_number_row(r)),
                    None)
    limit = boundary if boundary is not None else 4
    candidates = [i for i in range(min(limit, len(table_rows)))
                  if sum(1 for c in table_rows[i] if clean(c)) >= 3]
    header_rows = [table_rows[i] for i in candidates]
    if not header_rows:
        return None
    header_depth = (boundary + 1) if boundary is not None else (
        (candidates[-1] + 1) if candidates else 0)
    width = max(len(r) for r in header_rows)
    joined = []
    for i in range(width):
        parts = [clean(r[i]) for r in header_rows if i < len(r)]
        joined.append(" ".join(p for p in parts if p).lower())

    if not any("reserv" in h for h in joined):
        return None

    def find(*needles, exclude=()):
        for i, head in enumerate(joined):
            if any(n in head for n in needles) and not any(x in head for x in exclude):
                return i
        return None

    reservations = [i for i, h in enumerate(joined) if "reserv" in h]
    ward_no = find("constituency n", "number &", "panch no", "no. & name")
    mapping = {
        "district": find("district", exclude=("no.", "no ")),
        "block": find("block name", "name of block", exclude=("no.", "no ")),
        "halqa": find("halqa", "panchayat name", "pyt. name", "pyt name",
                      "name of halqua", exclude=("no.", "no ")),
        "ward_no": ward_no,
        "ward_name": (ward_no + 1) if ward_no is not None else None,
        # first reservation column is the panch ward, second the sarpanch
        "ward_res": reservations[0] if reservations else None,
        "sarpanch_res": reservations[1] if len(reservations) > 1 else None,
        # The population block is a sub-header "SC | ST | OC | Total", but each
        # cell joins with its group title ("Category wise population ... SC"),
        # so an equality test never fires. Match the triple by suffix instead,
        # and take the first one - the second is the *percentage* block.
        "pop_sc": next(
            (i for i in range(len(joined) - 2)
             if joined[i].endswith("sc") and joined[i + 1].endswith("st")
             and joined[i + 2].endswith("oc")
             and "%" not in joined[i] and "percent" not in joined[i]),
            None),
    }
    mapping["header_depth"] = header_depth
    return mapping if mapping["ward_res"] is not None else None


def parse_mapped(path, year):
    """Read a document whose columns are located from its own header."""
    rows = []
    # 2010 names its files by block or tehsil and has no district column at all,
    # so the filename is the only place that information exists.
    district, block, halqa = "", path.stem.strip(), ""
    mapping = None
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            district = district_from_title(page.extract_text() or "") or district
            for table in page.find_tables():
                extracted = [[clean(c) for c in r] for r in table.extract()]
                # Only the first page repeats the header. Recomputing the
                # mapping per table therefore returned None from page two
                # onwards and silently dropped every page but the first.
                found_here = map_columns(extracted)
                mapping = found_here or mapping
                if not mapping:
                    continue
                # drop the rows that *are* the header, or "Name of District"
                # ends up recorded as a district and the header's explanatory
                # sentence as a reservation value
                body = extracted[found_here["header_depth"]:] if found_here else extracted
                for cells in body:
                    def cell(key):
                        i = mapping.get(key)
                        return cells[i] if i is not None and i < len(cells) else ""

                    # the district column often holds a serial number instead;
                    # only accept something with letters in it
                    found = cell("district")
                    if (found and re.search(r"[A-Za-z]{3}", found)
                            and not emit.is_header_text(found)):
                        district = found
                    for name, value in (("block", cell("block")),
                                        ("halqa", cell("halqa"))):
                        if value and not emit.is_header_text(value):
                            if name == "block":
                                block = value
                            else:
                                halqa = value

                    ward_no, ward_name = cell("ward_no"), cell("ward_name")
                    if not ward_no or not re.match(r"^[IVXLC]+$|^\d+$", ward_no):
                        continue
                    base = {
                        "state": "Jammu & Kashmir", "year": year,
                        "district": district, "block": block, "halqa": halqa,
                        "listing_scope": LISTING_SCOPE.get(year, "all_seats"),
                        "pop_sc": "", "pop_st": "", "pop_oc": "", "pop_total": "",
                    }
                    sc = mapping.get("pop_sc")
                    if sc is not None and sc + 3 < len(cells):
                        base.update(pop_sc=cells[sc], pop_st=cells[sc + 1],
                                    pop_oc=cells[sc + 2], pop_total=cells[sc + 3])

                    for key, tier in (("ward_res", "ward"),
                                      ("sarpanch_res", "sarpanch")):
                        raw = cell(key)
                        parsed = normalize_reservation(raw)
                        if not parsed:
                            continue
                        caste, woman, script = parsed
                        rows.append(emit.stamp(dict(
                            base,
                            ward_no=ward_no if tier == "ward" else "",
                            ward_name=ward_name if tier == "ward" else "",
                            tier=canon.tier_of(tier, "Jammu & Kashmir"),
                            tier_local=tier, reservation=label(caste, woman),
                            caste_reservation=caste, woman_reserved=woman,
                            reservation_raw=raw, script=script,
                        ), path, page.page_number, ROOT))
    return rows


def fill_place(rows, path):
    """Give a document's rows the block and district the document itself names.

    2010's files have no district column at all and a block column that is
    printed on only a third of the rows, so both were left blank: 6,888 rows
    with no district and 5,104 with no block, out of 7,340. Neither is missing
    from the documents - the block is the filename and the district is in the
    title - so neither needed to stay blank.

    A value already read from the page always wins; this only fills what is
    empty.
    """
    if not rows:
        return
    block = block_from_filename(path)
    district = ""
    try:
        with pdfplumber.open(str(path)) as pdf:
            district = district_from_document(pdf.pages[0].extract_text() or "")
    except Exception:  # noqa: BLE001 - a document that will not open names nothing
        district = ""
    declared = ""
    if not district:
        district = DISTRICT_OF_BLOCK.get(block.lower(), "")
        declared = "1" if district else ""

    for row in rows:
        if not (row.get("block") or "").strip():
            row["block"] = block
        # A district read off the page still has to be a district. 344 rows
        # carried "vide Order No." - the tail of an order reference that landed
        # in the column - and it survived because it was not blank. The roster
        # is closed, so anything outside it is boilerplate, not a place.
        current = (row.get("district") or "").strip()
        if current and not any(current.lower() == d.lower()
                               for d in DISTRICT_ROSTER):
            current = ""
        if not current:
            row["district"] = district
            row["district_declared"] = declared
        else:
            row["district"] = current


def parse_generic(path, year, layout):
    """2010 and 2018: one reservation column, ward tier only.

    `layout` gives the column index of each field; -1 means the field is not
    printed and has to come from the page title.
    """
    rows = []
    district = block = halqa = ""
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            district = district_from_title(text) or district
            for table in page.find_tables():
                for raw in table.extract():
                    cells = [clean(c) for c in raw]
                    if len(cells) <= layout["reservation"]:
                        continue
                    district = carry(cells, layout.get("district"), district)
                    block = carry(cells, layout.get("block"), block)
                    halqa = carry(cells, layout.get("halqa"), halqa)
                    ward_no = cells[layout["ward_no"]]
                    ward_name = (cells[layout["ward_name"]]
                                 if layout.get("ward_name") is not None else "")
                    parsed = normalize_reservation(cells[layout["reservation"]])
                    if not parsed or not ward_no:
                        continue
                    caste, woman, script = parsed
                    rows.append(emit.stamp({
                        "state": "Jammu & Kashmir", "year": year,
                        "district": district, "block": block, "halqa": halqa,
                        "ward_no": ward_no, "ward_name": ward_name,
                        "tier": "gp_ward", "tier_local": "ward",
                        "reservation": label(caste, woman),
                        "caste_reservation": caste, "woman_reserved": woman,
                        "listing_scope": LISTING_SCOPE.get(year, "all_seats"),
                        "pop_sc": "", "pop_st": "", "pop_oc": "", "pop_total": "",
                        "reservation_raw": cells[layout["reservation"]],
                        "script": script,
                    }, path, page.page_number, ROOT))
    return rows


LAYOUTS = {
    # S.No | Halqa | Panch no | Panch name | Reservation
    "2010": {"halqa": 1, "ward_no": 2, "ward_name": 3, "reservation": 4},
    # District no | District | Block no | Block | Halqa no | Halqa | Panch no |
    # Panch name | Reservation
    "2018": {"district": 1, "block": 3, "halqa": 5, "ward_no": 6,
             "ward_name": 7, "reservation": 8},
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", action="append", choices=["2010", "2016", "2018"])
    args = ap.parse_args()
    years = args.year or ["2010", "2016", "2018"]

    for year in years:
        directory = JK / year
        if not directory.exists():
            continue
        rows, empty, failed = [], [], []
        for path in sorted(directory.glob("*.pdf")):
            try:
                got = parse_mapped(path, year)
                if not got and year in LAYOUTS:
                    # fall back to fixed indices for the years whose tables
                    # carry no usable header
                    got = parse_generic(path, year, LAYOUTS[year])
            except Exception as exc:  # noqa: BLE001 - report and continue
                failed.append((path.name, type(exc).__name__))
                got = []
            if not got:
                empty.append(path.name)
            fill_place(got, path)
            rows += got
            print(f"\r  {year} {path.name[:40]:40s} rows={len(rows)}",
                  end="", file=sys.stderr)
        print(file=sys.stderr)

        by_tier = collections.defaultdict(list)
        for row in rows:
            by_tier[row["tier_local"]].append(row)
        for tier, subset in sorted(by_tier.items()):
            stem = JK / f"{tier}_reservation_{year}"
            csv_path, _ = emit.write(subset, stem, COLUMNS)
            women = sum(r["woman_reserved"] for r in subset)
            districts = {r["district"] for r in subset if r["district"]}
            print(f"{year} {tier:9s} {len(subset):6d} seats  "
                  f"{len(districts):2d} districts  "
                  f"women {women / max(len(subset), 1) * 100:4.1f}%  "
                  f"-> {csv_path.name}")
        if empty:
            print(f"     no rows from {len(empty)} of "
                  f"{len(list(directory.glob('*.pdf')))} files")
        if failed:
            print(f"     unreadable: {failed[:4]}")


if __name__ == "__main__":
    main()
