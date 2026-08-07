"""Generate the coverage table in readme.md, and check that its links work.

The readme is the index of record for this whole family of repos, and it has
drifted twice already: Haryana sat blank after being built, `data/karnatka/` was
a typo nobody caught, and ten states had raw documents on disk while their rows
said nothing. A hand-maintained index will drift again, so it is generated.

Three sources feed it:

  * **parsed datasets** in `data/<state>/`, identified by their columns rather
    than their filenames - `jharkhand data 2010_reservation_pop_for web.csv` is
    a pre-existing file that matches any sensible filename glob but is not one
    of ours;
  * **raw holdings** from `data/inventory.csv`, so a state with documents but no
    parser reads "raw, unparsed" instead of looking empty;
  * **sibling repos**, for the states that were split out.

Every link is verified: relative paths must exist on disk and http(s) links must
answer 200. `--check` exits non-zero on a dead link, so this can gate the index
the same way the validate scripts gate the data.
"""

import argparse
import collections
import csv
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
README = ROOT / "readme.md"

START, END = "<!-- coverage:start -->", "<!-- coverage:end -->"

# A parsed dataset is one carrying these columns. Filenames are not evidence.
REQUIRED = {"state", "year", "tier", "reservation", "caste_reservation"}

# States split into their own repositories.
SIBLINGS = {
    "Haryana": ("2016, 2022", "sarpanch, ward",
                "https://github.com/in-rolls/local_elections_haryana"),
    "Bihar": ("2006, 2011, 2016", "mukhiya, sarpanch, panch, ward",
              "https://github.com/in-rolls/local_elections_bihar"),
    "Kerala": ("2005, 2010, 2015, 2020", "ward",
               "https://github.com/in-rolls/local_elections_kerala"),
    "Uttar Pradesh": ("2005, 2010, 2015, 2021", "pradhan",
                      "https://github.com/in-rolls/local_elections_up"),
    "Uttarakhand": ("2008, 2014, 2019", "panchayat",
                    "https://github.com/in-rolls/local_elections_uttarakhand"),
}

# States whose data predates this schema. It is real coverage, just not in our
# column layout, so calling it "raw, unparsed" would understate it. Years are as
# recorded by whoever contributed them.
LEGACY = {
    "Rajasthan": ("2004-2019 urban, 2005-2021 panchayat", "rajasthan"),
    "Telangana": ("2018-2023", "telangana"),
    "West Bengal": ("2013 panchayat, 2008-2018 municipal", "wb"),
    "Karnataka": ("GP reservation history (.dta)", "karnataka"),
    "NCT of Delhi": ("2007, 2012, 2017 (urban)", "delhi"),
    "Maharashtra": ("Mumbai 2007, 2012, 2017 (urban only)", "maharashtra"),
}

# Directory name in data/ -> printed state name.
DIRECTORY_NAMES = {
    "ap": "Andhra Pradesh", "jk": "Jammu & Kashmir", "wb": "West Bengal",
    "up": "Uttar Pradesh", "madhya_pradesh": "Madhya Pradesh",
    "tamil_nadu": "Tamil Nadu", "delhi": "NCT of Delhi",
}

# States with no panchayati raj reservation to collect. Recording why is
# information, not an admission of a gap.
NO_PRI = {
    "Meghalaya": "Sixth Schedule - autonomous district councils, no PRI",
    "Mizoram": "Sixth Schedule - village councils, no PRI",
    "Nagaland": "Article 371A - village councils, no PRI",
}

ALL_STATES = [
    "Andaman & Nicobar Islands", "Andhra Pradesh", "Arunachal Pradesh", "Assam",
    "Bihar", "Chandigarh", "Chhattisgarh", "Dadra & Nagar Haveli and Daman & Diu",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jammu & Kashmir",
    "Jharkhand", "Karnataka", "Kerala", "Ladakh", "Lakshadweep",
    "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "NCT of Delhi", "Odisha", "Puducherry", "Punjab", "Rajasthan",
    "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh",
    "Uttarakhand", "West Bengal",
]


def pretty(directory):
    return DIRECTORY_NAMES.get(directory, directory.replace("_", " ").title())


def parsed_datasets():
    """Every CSV in data/ that carries our schema, keyed by state name."""
    found = collections.defaultdict(lambda: {"years": set(), "tiers": set(),
                                             "rows": 0, "dir": None})
    for path in sorted(DATA.glob("*/*.csv")):
        try:
            with path.open(encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                if not reader.fieldnames or not REQUIRED <= set(reader.fieldnames):
                    continue
                rows = list(reader)
        except (OSError, UnicodeDecodeError):
            continue
        if not rows:
            continue
        state = rows[0]["state"] or pretty(path.parent.name)
        entry = found[state]
        entry["dir"] = path.parent.name
        entry["rows"] += len(rows)
        entry["years"] |= {r["year"] for r in rows if r["year"]}
        entry["tiers"] |= {r["tier"] for r in rows if r["tier"]}
    return found


def raw_holdings():
    """States with source documents but no parsed output yet."""
    path = DATA / "inventory.csv"
    if not path.exists():
        return {}
    holdings = collections.defaultdict(lambda: collections.Counter())
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            holdings[row["state"]][row["format"]] += 1
    return holdings


def sibling_rows(url):
    """Count rows in a sibling repo if it is checked out next to this one."""
    name = url.rsplit("/", 1)[-1]
    directory = ROOT.parent / name
    if not directory.exists():
        return "-"
    total = 0
    for path in directory.rglob("*.csv"):
        try:
            with path.open(encoding="utf-8", errors="replace") as fh:
                total += max(sum(1 for _ in fh) - 1, 0)
        except OSError:
            continue
    return f"{total:,}" if total else "-"


def build_rows():
    parsed = parsed_datasets()
    raw = raw_holdings()
    by_directory = {v["dir"]: k for k, v in parsed.items() if v["dir"]}

    table = []
    for state in ALL_STATES:
        if state in parsed:
            entry = parsed[state]
            table.append((state, ", ".join(sorted(entry["tiers"])),
                          ", ".join(sorted(entry["years"])),
                          f"{entry['rows']:,}", "parsed",
                          f"[data/{entry['dir']}/](data/{entry['dir']}/)"))
            continue
        if state in SIBLINGS:
            years, tiers, url = SIBLINGS[state]
            table.append((state, tiers, years, sibling_rows(url), "parsed",
                          f"[{url.rsplit('/', 1)[-1]}]({url})"))
            continue
        if state in LEGACY:
            years, directory = LEGACY[state]
            table.append((state, "-", years, "-", "prior work, other schema",
                          f"[data/{directory}/](data/{directory}/)"))
            continue
        if state in NO_PRI:
            table.append((state, "-", "-", "-", "no PRI", NO_PRI[state]))
            continue

        directory = next((d for d in raw
                          if pretty(d) == state and d not in by_directory), None)
        if directory:
            counts = raw[directory]
            text = ", ".join(f"{n} {k}" for k, n in counts.most_common()
                             if k in ("digital-text", "scan", "mixed", "tabular"))
            table.append((state, "-", "-", "-", "raw, unparsed",
                          f"[data/{directory}/](data/{directory}/) - {text}"))
        else:
            table.append((state, "-", "-", "-", "not held", "-"))
    return table


def render(table):
    head = ("| State | Tier | Years | Rows | Status | Where |\n"
            "|---|---|---|---|---|---|\n")
    body = "".join("| " + " | ".join(cells) + " |\n" for cells in table)
    return head + body


def links_in(text):
    return re.findall(r"\[[^\]]*\]\(([^)]+)\)", text)


def check_links(text):
    """Relative paths must exist; http(s) links must answer 200."""
    dead = []
    for target in sorted(set(links_in(text))):
        if target.startswith(("http://", "https://")):
            try:
                request = urllib.request.Request(
                    target, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(request, timeout=30) as response:
                    if response.status != 200:
                        dead.append((target, response.status))
            except Exception as exc:  # noqa: BLE001 - any failure is a dead link
                dead.append((target, type(exc).__name__))
        else:
            if not (ROOT / target).exists():
                dead.append((target, "missing on disk"))
    return dead


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify links and exit non-zero if any is dead")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the table without writing readme.md")
    args = ap.parse_args()

    table = build_rows()
    rendered = render(table)

    if args.dry_run:
        print(rendered)
    else:
        text = README.read_text(encoding="utf-8")
        block = f"{START}\n\n{rendered}\n{END}"
        if START in text and END in text:
            text = re.sub(re.escape(START) + r".*?" + re.escape(END), block,
                          text, flags=re.S)
        else:
            text = text.rstrip() + "\n\n" + block + "\n"
        README.write_text(text, encoding="utf-8")
        print(f"wrote {README} ({len(table)} states)")

    status = collections.Counter(row[4] for row in table)
    print("  " + "  ".join(f"{k}={v}" for k, v in status.most_common()))

    if args.check:
        dead = check_links(README.read_text(encoding="utf-8"))
        if dead:
            print(f"\n{len(dead)} dead link(s):")
            for target, why in dead:
                print(f"   {target}  -> {why}")
            return 1
        print("  all links resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
