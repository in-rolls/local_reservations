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
SLICE_START, SLICE_END = "<!-- slices:start -->", "<!-- slices:end -->"

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "common"))
import reference  # noqa: E402

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
    "himachal": "Himachal Pradesh",
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


def unmapped_directories():
    """Directories under data/ whose name does not resolve to a state.

    A directory that fails to map is not an error anywhere - it simply never
    matches, and the state is reported as "not held" while its documents sit on
    disk. That is what happened to Himachal: pretty("himachal") is "Himachal",
    the state is listed as "Himachal Pradesh", and una_2020.pdf was reported as
    nothing acquired. Checked rather than assumed, because the failure is
    silent by construction.
    """
    names = {p.name for p in DATA.iterdir() if p.is_dir()}
    names |= set(raw_holdings())
    return sorted(n for n in names if pretty(n) not in ALL_STATES)


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


def datasets():
    """Every CSV under data/ that carries our schema, with its rows."""
    for path in sorted(DATA.glob("*/*.csv")):
        try:
            with path.open(encoding="utf-8", errors="replace") as fh:
                reader = csv.DictReader(fh)
                if not reader.fieldnames or not REQUIRED <= set(reader.fieldnames):
                    continue
                rows = list(reader)
        except OSError:
            continue
        if rows:
            yield path, rows


def slices():
    """One entry per state x year x tier - the grain the data actually has.

    The state-level table collapses years into a cell, which reads as though
    Goa's three cycles are comparable. They are not: 2012 is complete and names
    the winner, while 2017 and 2022 are partial nomination lists. Splitting by
    slice puts the caveat next to the number.
    """
    grouped = collections.defaultdict(list)
    directory_of = {}
    for path, rows in datasets():
        for row in rows:
            key = (row.get("state", ""), row.get("year", ""), row.get("tier", ""))
            grouped[key].append(row)
            directory_of[key] = path.parent.name

    out = []
    for (state, year, tier), rows in sorted(grouped.items()):
        total = len(rows)
        women = sum(1 for r in rows if str(r.get("woman_reserved")) == "1")
        districts = {r.get("district") for r in rows if (r.get("district") or "").strip()}
        out.append({
            "state": state, "year": year, "tier": tier, "rows": total,
            "women": 100.0 * women / max(total, 1),
            "districts": len(districts),
            "coverage": _coverage(state, year, tier, rows),
            "notes": "; ".join(_notes(state, year, tier, rows, len(districts))),
            "dir": directory_of[(state, year, tier)],
        })
    return out


def _coverage(state, year, tier, rows):
    """Rows against a published total, comparing like with like."""
    spec = reference.published(state, year, tier)
    total = spec.get("total")
    if not total:
        return "—"
    counted = rows
    if spec.get("basis") == "elected":
        # an "elected" figure excludes seats nobody holds
        counted = [r for r in rows if str(r.get("vacant", "")) != "1"]

    # Compare like with like. Goa's 186 counts *panchayats*, and the rows are
    # wards - dividing one by the other reported 797% coverage, which is the
    # same unit error that once made Haryana 2016 look like a 102% over-count.
    unit = spec.get("unit", "seats")
    if unit == "panchayats":
        n = len({(r.get("block"), r.get("gram_panchayat")) for r in counted})
    else:
        n = len(counted)
    return f"{100.0 * n / total:.0f}% of {total:,} {unit}"


def _notes(state, year, tier, rows, districts):
    """Caveats derived from the rows, so they cannot go stale."""
    notes = []
    if not any((r.get("winner") or "").strip() for r in rows):
        notes.append("no winner published")
    if rows and rows[0].get("listing_scope") == "reserved_only":
        notes.append("**reserved seats only** — shares are a property of the "
                     "document, not of the state")
    if rows and rows[0].get("script") == "krutidev":
        notes.append("place names not transliterated")

    expected = reference.districts_expected(state, year)
    if expected and districts and districts < expected:
        notes.append(f"partial: {districts} of {expected} districts")

    flags = [r.get("ward_list_complete") for r in rows]
    known = [f for f in flags if f in ("0", "1")]
    if known and len(known) > 0.1 * len(rows):
        share = 100.0 * sum(1 for f in known if f == "1") / len(known)
        notes.append(f"ward list complete for {share:.0f}% of rows with a "
                     f"stated count")
    return notes


def render_slices(entries):
    head = ("| State | Year | Tier | Rows | Women | Districts | vs published | "
            "Notes | Where |\n|---|---|---|---|---|---|---|---|---|\n")
    body = ""
    for e in entries:
        body += (f"| {e['state']} | {e['year']} | `{e['tier']}` | "
                 f"{e['rows']:,} | {e['women']:.0f}% | {e['districts']} | "
                 f"{e['coverage']} | {e['notes'] or '—'} | "
                 f"[data/{e['dir']}/](data/{e['dir']}/) |\n")
    return head + body


def render(table):
    head = ("| State | Tier | Years | Rows | Status | Where |\n"
            "|---|---|---|---|---|---|\n")
    body = "".join("| " + " | ".join(cells) + " |\n" for cells in table)
    return head + body


def links_in(text):
    return re.findall(r"\[[^\]]*\]\(([^)]+)\)", text)


def check_links(text, base=None):
    """Relative paths must exist; http(s) links must answer 200.

    `base` is the directory the links are written relative to - the state
    readmes live a level down, so their `../../SOURCES.md` resolves against
    data/<state>/ and not against the repository root.
    """
    base = base or ROOT
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
            if not (base / target).resolve().exists():
                dead.append((target, "missing on disk"))
    return dead


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify links and exit non-zero if any is dead")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the table without writing readme.md")
    args = ap.parse_args()

    unmapped = unmapped_directories()
    if unmapped:
        print(f"  directories that map to no state: {unmapped}")

    table = build_rows()
    rendered = render(table)
    entries = slices()
    rendered_slices = render_slices(entries)

    if args.dry_run:
        print(rendered_slices)
        print(rendered)
    else:
        text = README.read_text(encoding="utf-8")
        for start, end, block_body in ((SLICE_START, SLICE_END, rendered_slices),
                                       (START, END, rendered)):
            block = f"{start}\n\n{block_body}\n{end}"
            if start in text and end in text:
                text = re.sub(re.escape(start) + r".*?" + re.escape(end), block,
                              text, flags=re.S)
            else:
                text = text.rstrip() + "\n\n" + block + "\n"
        README.write_text(text, encoding="utf-8")
        print(f"wrote {README} ({len(entries)} slices, {len(table)} states)")

    status = collections.Counter(row[4] for row in table)
    print("  " + "  ".join(f"{k}={v}" for k, v in status.most_common()))

    if args.check:
        dead = check_links(README.read_text(encoding="utf-8"))
        for path in sorted(DATA.glob("*/readme.md")):
            dead += [(f"{path.parent.name}/{t}", why) for t, why in
                     check_links(path.read_text(encoding="utf-8"), path.parent)]
        if dead:
            print(f"\n{len(dead)} dead link(s):")
            for target, why in dead:
                print(f"   {target}  -> {why}")
            return 1
        print("  all links resolve")
        if unmapped:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
