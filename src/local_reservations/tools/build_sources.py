"""Keep SOURCES.md's holdings table true to what is on disk.

    uv run python -m local_reservations.tools.build_sources
    uv run python -m local_reservations.tools.build_sources --check

SOURCES.md is a feasibility survey and most of it is judgement - whether a
state is worth building, what its documents turned out to be, what OCR would
cost. That stays hand-written. What does not stay hand-written is the count of
files and pages, because that is a fact about the directory and it drifted:
Karnataka's row read "1 scan, 7 pages" on the day the repository held 439
documents and 1,545 pages of them.

So the numbers come from data/inventory.csv and the sentence describing each
state stays here, in HELD, for the same reason build_state_readmes keeps
STATE_NOTES - it is knowledge about documents rather than a fact derivable from
them.
"""

import argparse
import collections
import csv
import sys

from local_reservations.paths import ROOT

SOURCES = ROOT / "SOURCES.md"
INVENTORY = ROOT / "data" / "inventory.csv"
START = "<!-- holdings:start -->"
END = "<!-- holdings:end -->"

# Directory name -> the name the survey uses. Several rows cover more than one
# directory, because the survey groups states nobody would build separately.
GROUPS = {
    "Bihar": ["bihar"],
    "Rajasthan": ["rajasthan"],
    "**Jharkhand**": ["jharkhand"],
    "**Jammu & Kashmir**": ["jk"],
    "**Andhra Pradesh**": ["ap"],
    "**Goa**": ["goa"],
    "West Bengal": ["wb"],
    "Madhya Pradesh": ["mp"],
    "Odisha": ["odisha"],
    "Tamil Nadu": ["tn"],
    "Chandigarh, Puducherry, Delhi": ["chandigarh", "puducherry", "delhi"],
    "**Karnataka**": ["karnataka"],
    "Assam, Himachal": ["assam", "himachal"],
}

# The half a directory listing cannot tell you.
HELD = {
    "Bihar": "PRI winners 2006-2016; also `local_elections_bihar`",
    "Rajasthan": "panchayat 2005-2021",
    "**Jharkhand**": "**2015 mukhiya (GP head) reservation by district; 2022 "
                     "Form-23 ZP members**",
    "**Jammu & Kashmir**": "**2010/2016/2018 block-wise, panch-ward "
                           "reservation with SC/ST/OC population**",
    "**Andhra Pradesh**": "**2020 district gazettes: GP, MPTC, ZPTC, MPP "
                          "reservation**",
    "**Goa**": "**2012/2017/2022 `panres_<taluka>` panchayat reservation + "
               "ward category**",
    "West Bengal": "2018 SEC delimitation-and-reservation gazettes, per "
                   "district - parsed, 825 zilla parishad seats",
    "Madhya Pradesh": "two large OmniPage-OCR'd volumes",
    "Odisha": "2017 reservation of sarpanch/ward member - **district totals, "
              "not seat-level**",
    "Tamil Nadu": "gazettes, but **municipal/corporation**, not village "
                  "panchayat",
    "Chandigarh, Puducherry, Delhi": "mostly urban local bodies",
    "**Karnataka**": "**2016 taluk & zilla panchayat winners with party**; "
                     "plus `Karnataka_GP_ReservationHistory.dta`. 244 of the "
                     "documents are deliberately unread - see "
                     "data/karnataka/readme.md",
    "Assam, Himachal": "one file each; Assam's is municipal",
}


def counts():
    """{directory: {format: files, "pages": pages}} from the inventory."""
    out = collections.defaultdict(lambda: collections.Counter())
    with INVENTORY.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out[row["state"]][row["format"]] += 1
            out[row["state"]]["pages"] += int(row["pages"] or 0)
    return out


def render():
    held = counts()
    lines = ["| state | text | scan | mixed | pages | what is held |",
             "|---|---|---|---|---|---|"]
    rows = []
    for label, directories in GROUPS.items():
        total = collections.Counter()
        for directory in directories:
            total.update(held.get(directory, {}))
        rows.append((total["pages"], label, total))
    for pages, label, total in sorted(rows, reverse=True):
        lines.append(f"| {label} | {total['digital-text']} | {total['scan']} | "
                     f"{total['mixed']} | {pages:,} | {HELD[label]} |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="fail when the file on disk differs from this")
    args = ap.parse_args()

    text = SOURCES.read_text(encoding="utf-8")
    if START not in text or END not in text:
        sys.exit(f"{SOURCES.name} has no {START} / {END} block")
    before = text[:text.index(START) + len(START)]
    after = text[text.index(END):]
    fresh = f"{before}\n{render()}\n{after}"

    if args.check:
        if fresh != text:
            sys.exit(f"{SOURCES.name} holdings table is stale - "
                     f"run make sources")
        print(f"  {SOURCES.name} holdings table is current")
        return 0
    SOURCES.write_text(fresh, encoding="utf-8")
    print(f"  wrote the holdings table -> {SOURCES.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
