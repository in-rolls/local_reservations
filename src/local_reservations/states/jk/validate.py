"""Check the parsed J&K reservation data.

J&K has no reliable published seat total to check against, and its holdings are
an ad-hoc set rather than a complete corpus, so the checks here are about being
honest rather than about hitting a number:

* the women's share is only meaningful for a **full roster**. 2018's documents
  list only the reserved wards, so its 82% women is a property of the document.
  That check is skipped for `listing_scope == reserved_only` rather than
  reported as a failure or, worse, as a finding.
* 2016 carries two reservation columns, so the sarpanch count must be far
  smaller than the ward count. If they are close, column 13 was misread as
  column 12 and every ward is being recorded twice.
* 2016 also carries the SC/ST populations the allocation was based on, so
  SC-reserved wards should sit in places with more SC population than average.
  No other state in this repo lets the allocation rule be checked against its
  own inputs.
"""

import argparse
import collections
import csv
import pathlib
import sys

from local_reservations.common import checks
from local_reservations.paths import ROOT

JK = ROOT / "data" / "jk"

# The 73rd Amendment, and J&K's own Act, reserve "not less than one-third" of
# seats for women. That is a floor, not a target - unlike Haryana's 50%, which
# is an exact split. So this is a one-sided check. 2010 comes out at 48%, which
# is above the floor rather than a parse error: its raw values are all genuine
# women-reserved strings, down to character-spaced ones like "S T W O M E N".
WOMEN_FLOOR = 1 / 3
YEARS = ["2010", "2016", "2018"]


def load(tier, year):
    path = JK / f"{tier}_reservation_{year}.csv"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def pct(part, whole):
    return 100.0 * part / whole if whole else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    failures = 0
    failures += shared_battery(
        "Jammu & Kashmir - shared checks",
        [(f"{y} {t}", load(t, y) or [])
         for y in YEARS for t in ("sarpanch", "ward")]).finish()

    print("\n=== Jammu & Kashmir panchayat reservation ===\n")

    for year in YEARS:
        for tier in ("sarpanch", "ward"):
            rows = load(tier, year)
            if not rows:
                continue
            scope = rows[0].get("listing_scope", "all_seats")
            women = sum(int(r["woman_reserved"]) for r in rows)
            districts = {r["district"] for r in rows if r["district"]}
            files = {r["source_pdf"] for r in rows}
            share = pct(women, len(rows))

            print(f"{year} {tier:9s} {len(rows):6d} seats  "
                  f"{len(districts):2d} districts  {len(files):2d} files  "
                  f"women {share:4.1f}%   [{scope}]")

            if scope == "all_seats":
                # one-sided: at or above the floor, allowing 2pp for rounding
                ok = share / 100 >= WOMEN_FLOOR - 0.02
                failures += not ok
                print(f"      [{'PASS' if ok else 'FAIL'}] women's share at or "
                      f"above the one-third floor")
            else:
                print("      [SKIP] women's share - this listing carries only "
                      "reserved seats, so the share is a property of the "
                      "document, not of J&K")

        # 2016 prints both tiers; they must not be the same size
        sarpanch, ward = load("sarpanch", year), load("ward", year)
        if sarpanch and ward:
            ratio = len(ward) / max(len(sarpanch), 1)
            ok = ratio >= 2.5
            failures += not ok
            print(f"      [{'PASS' if ok else 'FAIL'}] wards per halqa = "
                  f"{ratio:.1f} (near 1 would mean the sarpanch column was "
                  f"read as the ward column)")

            # the allocation rule, checked against its own inputs
            withpop = [r for r in ward if r.get("pop_total", "").isdigit()
                       and r.get("pop_sc", "").isdigit()]
            if withpop:
                def sc_share(r):
                    return int(r["pop_sc"]) / max(int(r["pop_total"]), 1)
                reserved = [r for r in withpop if r["caste_reservation"] == "SC"]
                other = [r for r in withpop if r["caste_reservation"] != "SC"]
                if reserved and other:
                    a = sum(map(sc_share, reserved)) / len(reserved)
                    b = sum(map(sc_share, other)) / len(other)
                    ok = a > b
                    failures += not ok
                    print(f"      [{'PASS' if ok else 'FAIL'}] SC-reserved wards "
                          f"have higher SC population share ({a:.1%} vs {b:.1%} "
                          f"in {len(reserved)} vs {len(other)} wards)")
        print()

    files_on_disk = sum(1 for y in YEARS for _ in (JK / y).glob("*.pdf"))
    used = set()
    for year in YEARS:
        for tier in ("sarpanch", "ward"):
            used |= {r["source_pdf"] for r in (load(tier, year) or [])}
    print(f"documents used: {len(used)} of {files_on_disk} on disk")
    print("J&K's holdings are an ad-hoc subset, not a full corpus - see "
          "SOURCES.md; there is no published seat total to measure against.")

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