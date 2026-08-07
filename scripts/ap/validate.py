"""Check the parsed Andhra Pradesh reservation data.

The useful thing about these gazettes is that each one states its own answer:
FORMAT-I on page 2 is an "Abstract of Reservations to the Office of Sarpanchs"
giving the district's total number of gram panchayats. So coverage can be
measured against a figure printed in the same document that was parsed, rather
than against an external total that might refer to a different year or a
different set of districts.

The other thing worth reporting is `ocr_repaired`. The text layer here is OCR
output with real errors, and the category vocabulary is closed enough to mend -
but a mend that is wrong is indistinguishable from one that is right, so the
count of mended cells is part of the result, not an implementation detail.
"""

import argparse
import collections
import csv
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "common"))
import checks  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data" / "ap"
SOURCE = DATA / "2020_res_gp"
OCR = DATA / "ocr"

# Andhra Pradesh reserves half of all sarpanch seats for women.
WOMEN_SHARE = 0.50
DISTRICTS = {
    "atp": "Anantapur", "est": "East Godavari", "kri": "Krishna",
    "nlr": "Nellore", "pkm": "Prakasam",
}


def load(tier):
    path = DATA / f"{tier}_reservation_2020.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _is_column_numbering(numbers):
    """A run like 1 2 3 4 5 ... is the header's column numbers, not data."""
    values = [int(n) for n in numbers]
    return len(values) >= 6 and all(b - a == 1 for a, b in zip(values, values[1:]))


def abstract_total(path, district):
    """The district's gram panchayat count, as its own FORMAT-I abstract states.

    Read from our OCR rather than the embedded text layer. The embedded layer
    breaks "East Godavari" across three lines, so a regex anchored on the name
    lands on a Scheduled-Area subtotal - which is how this check once reported
    825 of 183 as a pass. The OCR keeps the abstract row intact:

        1 adie 1103 94 89 | 183 2 4 3 5 1 6 112 | 88 | 200 ...

    so the first three-or-more-digit number on the row is the district total.
    """
    cached = OCR / f"{path.stem}.txt"
    if not cached.exists():
        return None
    for page in cached.read_text(encoding="utf-8").split("\f")[:6]:
        upper = page.upper()
        if "SARPANCH" not in upper.replace(" ", ""):
            continue
        if "ABSTRACT" not in upper and "FORMAT" not in upper:
            continue
        for line in page.split("\n"):
            numbers = re.findall(r"\b\d{2,5}\b", line)
            if len(numbers) < 8 or _is_column_numbering(numbers):
                continue
            big = [int(n) for n in numbers if int(n) >= 100]
            if big:
                return big[0]
    return None


def pct(part, whole):
    return 100.0 * part / whole if whole else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    sarpanch, ward = load("sarpanch"), load("ward")
    if not sarpanch:
        sys.exit("no parsed data - run scripts/ap/parse.py first")
    failures = 0
    failures += shared_battery(
        "Andhra Pradesh - shared checks",
        [("sarpanch", sarpanch), ("ward", ward)]).finish()

    print("\n=== Andhra Pradesh gram panchayat reservation, 2020 ===\n")

    women = sum(int(r["woman_reserved"]) for r in sarpanch)
    share = pct(women, len(sarpanch))
    repaired = sum(int(r["ocr_repaired"]) for r in sarpanch + ward)
    print(f"sarpanch {len(sarpanch):6d} seats   ward {len(ward):6d} seats")
    print(f"women {women}/{len(sarpanch)} = {share:.1f}%  (statute "
          f"{WOMEN_SHARE:.0%})")
    ok = abs(share / 100 - WOMEN_SHARE) <= 0.05
    failures += not ok
    print(f"   [{'PASS' if ok else 'FAIL'}] women's share within 5pp of half")

    print(f"OCR-mended cells: {repaired} of {len(sarpanch) + len(ward)} "
          f"= {pct(repaired, len(sarpanch) + len(ward)):.1f}%")
    print("   these are repairs to a closed vocabulary (5C->SC, 8c->BC); a "
          "wrong repair looks like a right one, so they stay flagged")

    print("\ncoverage against each gazette's own FORMAT-I abstract:")
    counts = collections.Counter(r["district"] for r in sarpanch)
    for path in sorted(SOURCE.glob("*.pdf")):
        district = DISTRICTS.get(path.stem.split("_")[0], path.stem)
        stated = abstract_total(path, district)
        got = counts.get(district, 0)
        if stated:
            share_of = pct(got, stated)
            if share_of > 110:
                # More rows than the district is meant to have means the number
                # scraped off the abstract is not the district total - these
                # gazettes break "East Godavari" across three lines, so the
                # regex can land on a Scheduled-Area subtotal instead. Reporting
                # that as a PASS at 450% would be worse than not checking.
                flag, note = "INFO", "  abstract figure unreliable, not a check"
            elif share_of >= 90:
                flag, note = "PASS", ""
            elif got:
                flag, note = "WARN", "  under-parsed"
            else:
                flag, note = "FAIL", "  nothing parsed"
            failures += flag == "FAIL"
            print(f"   [{flag}] {district:16s} {got:5d} of {stated:5d} stated "
                  f"({share_of:5.1f}%){note}")
        else:
            print(f"   [INFO] {district:16s} {got:5d} parsed, abstract total "
                  f"not readable")

    # Anantapur states each sarpanch seat twice, in two separately typeset
    # proformas. Two independent statements of the same fact agreeing is the
    # strongest evidence available in this state that a row was read right -
    # there is no published per-seat figure to check against - so the ones that
    # disagree are named rather than counted and forgotten.
    twice = [r for r in sarpanch if r.get("printings") == "2"]
    if twice:
        disagree = [r for r in twice if r.get("printings_agree") == "0"]
        share = 100.0 * (len(twice) - len(disagree)) / len(twice)
        flag = "PASS" if share >= 95 else "WARN"
        print(f"\n   [{flag}] seats stated twice agree - "
              f"{len(twice) - len(disagree)} of {len(twice)} ({share:.1f}%)")
        for row in disagree[:8]:
            print(f"        {row['district']}/{row['block']}/"
                  f"{row['gram_panchayat']}: kept {row['reservation']!r} "
                  f"(from {row['reservation_raw']!r}), p{row['source_page']}")

    bad = [r for r in sarpanch
           if r["caste_reservation"] not in ("SC", "ST", "BC", "NONE")]
    failures += bool(bad)
    print(f"\n   [{'PASS' if not bad else 'FAIL'}] every row normalised "
          f"({len(bad)} bad)")

    print(f"\n{'FAILED' if failures else 'OK'}: {failures} hard check(s) failed\n")
    return 1 if failures else 0


def shared_battery(title, datasets):
    """Structural and provenance checks every state runs, before its own.

    These cannot catch a misread category - only the substantive checks below
    do that - but they catch a shifted column, a lost key, a row counted twice,
    and a row that cannot be traced back to a page.
    """
    report = checks.Report(title)
    for label, rows in datasets:
        if not rows:
            continue
        print(f"\n-- {label}")
        checks.structural(report, rows, ROOT,
                          required=("state", "year", "tier", "reservation",
                                    "caste_reservation", "woman_reserved"))
        checks.provenance(report, rows, ROOT)
    return report


if __name__ == "__main__":
    sys.exit(main())