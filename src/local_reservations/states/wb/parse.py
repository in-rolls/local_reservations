"""West Bengal zila parishad seats, 2018, from the delimitation gazettes.

The smallest state parsed here and the only one with a **draft and a final
printing of the same document for 19 of 20 districts**. Both are parsed and
compared, which is why this is worth doing at its size: two independent scans of
two independently typeset gazettes agreeing on the same seat is the strongest
evidence available that a scanned row was read right, and `printings_agree` is
already a column the master carries and `quality_flags` already reports.

The gazette prints five columns:

    (1) Name of Block
    (2) Number of members to be elected to the Zilla Parishad
    (3) Number, Name and area of the Constituency
    (4) Constituencies reserved for ST/SC/BC persons
    (5) Constituencies reserved for women

Columns (4) and (5) are separate, and that is the whole reason this parser reads
word positions rather than lines of text. Flattened to text, a scheduled-caste
women's seat reads "SC Women", a women's seat reads "Women", a scheduled-caste
seat reads "SC" and an open seat reads as nothing - which works until one stray
word lands between the columns and an open seat silently acquires a caste. The
column boundaries come from the gazette's own `(1) (2) (3) (4) (5)` markers.

**Column (2) is a check the document performs on itself.** It states how many
zila parishad members each block elects. Summed over a district that must equal
the number of constituencies parsed for it, and it is an entirely independent
statement - printed once per block, against constituencies enumerated one by
one. A parser that drops or invents a row fails it.
"""

import argparse
import collections
import csv
import pathlib
import re
import sys

from local_reservations.common.normalize import label  # noqa: E402
from local_reservations.paths import ROOT

CACHE = ROOT / "data" / "wb" / "ocr"
OUT = ROOT / "data" / "wb"
YEAR = "2018"

# "Haldibari / ZP-4", "Mathabhanga-II/ZP-5", "Cooch Behar-II / ZP-11"
SEAT = re.compile(r"^(?P<block>.+?)\s*/\s*ZP\s*-\s*(?P<number>\d+)\s*$", re.I)
MARKER = re.compile(r"^\(([1-5])\)$")
# "Dubrajpur 2", "Cooch Behar-II 3" - a block and the members it elects
MEMBERS = re.compile(r"^(?P<name>[^\d].*?)\s+(?P<count>\d{1,2})$")

# OCR renders these in mixed case often enough that matching is done folded.
CASTE_WORDS = {"sc": "SC", "st": "ST", "bc": "BC", "s.c": "SC", "s.t": "ST"}
WOMAN_WORDS = {"women", "woman", "wornen"}

COLUMNS = ["state", "year", "district", "block", "seat_no", "seat_id_printed",
           "tier", "tier_local", "reservation", "caste_reservation",
           "woman_reserved", "reservation_raw", "printings_agree", "script",
           "source_path", "source_page"]


def words_of(path):
    """Every OCR'd word on a page, with its box, grouped into lines."""
    lines = collections.defaultdict(list)
    with path.open(encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
            text = (row.get("text") or "").strip()
            if not text or row.get("level") != "5":
                continue
            try:
                left, width = int(row["left"]), int(row["width"])
                key = (int(row["block_num"]), int(row["par_num"]),
                       int(row["line_num"]))
            except (KeyError, ValueError):
                continue
            lines[key].append({"text": text, "x": left + width / 2})
    return [sorted(v, key=lambda w: w["x"]) for _, v in sorted(lines.items())]


def column_edges(lines):
    """Where columns (4) and (5) begin, from the gazette's own markers.

    Returns None where the page does not print the header, which is every page
    after a district's first: the caller carries the previous page's edges,
    because the table is one table continued rather than a new one.
    """
    for line in lines:
        # The header rule is a line of nothing but the five markers. Merely
        # finding them somewhere on a line matched the order's own prose -
        # "specified in column (1) of the Schedule below ... entries in column
        # (2) ... column (4) and the constituency ... column (5)" - which spans
        # four OCR'd lines of page 1 and put the column boundaries in the middle
        # of a paragraph. Every seat then read as unreserved, and the row count
        # was right.
        marks = [MARKER.match(w["text"]) for w in line]
        if not all(marks) or len(marks) < 5:
            continue
        found = {m.group(1): w["x"] for m, w in zip(marks, line)}
        if {"2", "3", "4", "5"} <= set(found):
            return ((found["1"] + found["2"]) / 2 if "1" in found else 0,
                    (found["2"] + found["3"]) / 2,
                    (found["3"] + found["4"]) / 2,
                    (found["4"] + found["5"]) / 2)
    return None


def read_page(path, edges):
    """The seats on one page, and the block member counts it states.

    Read as two independent regions rather than as lines of text. A block's
    member count usually sits on a line of its own - "Dubrajpur 2" - with no
    constituency beside it, so anything that only looked at lines carrying a
    seat saw three blocks of twenty and checked the gazette's arithmetic
    against a fifth of what it states.
    """
    lines = words_of(path)
    edges = column_edges(lines) or edges
    seats, members = [], {}
    if edges is None:
        return seats, members, edges
    _, seat_edge, caste_edge, woman_edge = edges

    for line in lines:
        left = " ".join(w["text"] for w in line if w["x"] < seat_edge).strip()
        seat_text = " ".join(w["text"] for w in line
                             if seat_edge <= w["x"] < caste_edge).strip()
        middle = [w for w in line if caste_edge <= w["x"] < woman_edge]
        right = [w for w in line if w["x"] >= woman_edge]

        # columns (1) and (2): the block, and how many members it elects
        stated = MEMBERS.match(left)
        if stated:
            members[stated.group("name").strip()] = int(stated.group("count"))

        got = SEAT.match(seat_text)
        if not got:
            continue
        block = re.sub(r"\s+", " ", got.group("block")).strip()

        caste = ""
        for word in middle:
            folded = word["text"].strip(".,").lower()
            if folded in CASTE_WORDS:
                caste = CASTE_WORDS[folded]
        woman = any(w["text"].strip(".,").lower() in WOMAN_WORDS for w in right)
        # a caste word that landed in the women's column is still a caste word,
        # but only when its own column is empty
        if not caste:
            for word in right:
                folded = word["text"].strip(".,").lower()
                if folded in CASTE_WORDS:
                    caste = CASTE_WORDS[folded]
        seats.append({
            "block": block, "seat_no": got.group("number"),
            "seat_id_printed": f"{block}/ZP-{got.group('number')}",
            "caste": caste or "NONE", "woman": int(woman),
            "raw": " ".join(w["text"] for w in middle + right),
        })
    return seats, members, edges


def read_document(stem, printing):
    directory = CACHE / printing
    pages = sorted(directory.glob(f"{stem}-*.tsv"))
    seats, members, edges = [], {}, None
    for path in pages:
        page = int(path.stem.rsplit("-", 1)[1])
        got, block_members, edges = read_page(path, edges)
        for seat in got:
            seat["source_page"] = page
        seats += got
        members.update(block_members)
    return seats, members


def district_of(stem):
    """The gazette names its district last, after the last dash."""
    return stem.rsplit("-", 1)[-1].strip()


def rows_for(stem, printing, agree):
    seats, _ = read_document(stem, printing)
    out = []
    for seat in seats:
        out.append({
            "state": "West Bengal", "year": YEAR,
            "district": district_of(stem), "block": seat["block"],
            "seat_no": seat["seat_no"],
            "seat_id_printed": seat["seat_id_printed"],
            "tier": "zp_member", "tier_local": "zilla parishad member",
            "caste_reservation": seat["caste"],
            "woman_reserved": seat["woman"],
            "reservation": label(seat["caste"], seat["woman"] == 1),
            "reservation_raw": seat["raw"],
            "printings_agree": agree.get(
                (district_of(stem), seat["seat_no"]), ""),
            "script": "latin",
            "source_path": f"data/wb/{YEAR}/"
                           + ("draft/" if printing == "draft" else "")
                           + f"{stem}.pdf",
            "source_page": seat["source_page"],
        })
    return out


def agreement():
    """Which seats the draft and the final printing state identically."""
    by_printing = {}
    for printing in ("final", "draft"):
        directory = CACHE / printing
        if not directory.exists():
            continue
        stems = sorted({p.stem.rsplit("-", 1)[0] for p in directory.glob("*.tsv")})
        for stem in stems:
            seats, _ = read_document(stem, printing)
            for seat in seats:
                # keyed on the seat number within the district, not on the
                # printed identifier: the block name is OCR'd out of a scan and
                # differs by a character between printings often enough that
                # matching on it found 189 of 813 seats
                key = (district_of(stem), seat["seat_no"])
                by_printing.setdefault(key, {})[printing] = (
                    seat["caste"], seat["woman"])
    out = {}
    for key, got in by_printing.items():
        if len(got) == 2:
            out[key] = int(got["final"] == got["draft"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if not CACHE.exists():
        raise SystemExit(f"no OCR cache at {CACHE}; run scripts/wb/ocr.py")

    agree = agreement()
    rows, checked, failed = [], 0, []
    stems = sorted({p.stem.rsplit("-", 1)[0]
                    for p in (CACHE / "final").glob("*.tsv")})
    for stem in stems:
        got = rows_for(stem, "final", agree)
        rows += got
        # the gazette's own arithmetic: each block states how many members it
        # elects, and the constituencies are enumerated separately
        _, members = read_document(stem, "final")
        if members:
            checked += 1
            stated = sum(members.values())
            counted = len({r["seat_id_printed"] for r in got})
            if stated and abs(stated - counted) > 0:
                failed.append((district_of(stem), stated, counted))

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"zp_member_{YEAR}.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore",
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    if not args.quiet:
        agreed = sum(1 for r in rows if r["printings_agree"] == 1)
        both = sum(1 for r in rows if r["printings_agree"] != "")
        print(f"  {len(rows):,} zila parishad seats across {len(stems)} "
              f"districts")
        print(f"  {both:,} seats printed twice; {agreed:,} agree "
              f"({100.0 * agreed / both:.1f}%)" if both else
              "  no district printed twice")
        if failed:
            print(f"  {len(failed)} district(s) where the stated member count "
                  f"and the constituencies enumerated disagree:")
            for district, stated, counted in failed:
                print(f"     {district}: states {stated}, enumerates {counted}")


if __name__ == "__main__":
    main()
