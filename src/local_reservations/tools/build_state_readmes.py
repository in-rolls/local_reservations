"""Write a readme into every state directory under data/.

The top-level readme answers "what does this repository hold". It cannot answer
"what is in this directory, where did it come from, and what should I not do
with it" without becoming unreadable, and that is the question someone has who
has landed in data/jk/ from a search result or a file listing.

Everything here is derived from the files themselves - row counts, women's
shares, districts, the source documents each row cites, the caveats. Nothing is
typed in that could drift out of step with the data, which is the same reason
the top-level tables are generated. The one hand-written part is the paragraph
saying what makes each state's sources awkward, in STATE_NOTES, because that is
knowledge about documents rather than a fact derivable from the parsed rows.

Run with `make state-readmes`, or `--check` to fail when a file on disk differs
from what would be generated now.
"""

import argparse
import collections
import csv
import sys

from local_reservations.common import datasets
from local_reservations.paths import ROOT
from local_reservations.tools import build_coverage as coverage

STATS = DATA_STATS = None

DATA = ROOT / "data"

# What is awkward about each state's sources. Knowledge about the documents,
# not a fact derivable from the rows, so it is written rather than computed -
# and kept to what a reader needs before using the numbers.
STATE_NOTES = {
    "ap": """The gazettes have no ruled tables and no reliable text layer, so
every district is re-OCR'd from a 300 DPI render and read positionally. The
districts do not agree on the column order, and neither does Krishna with
itself: its pages 12 and 13 put the ward count on opposite sides of the
sarpanch's own cell. Nothing in a line marks where the mandal ends and the
panchayat begins, so that boundary is recovered from the order of the records.

Two consequences worth knowing before using this. `ocr_repaired` counts the
mends a row's category cell needed - a wrong mend looks exactly like a right
one, so those rows stay findable rather than being quietly trusted. And
Anantapur states each sarpanch seat twice, in two separately typeset proformas;
the file holds their deduplicated union, `printings` records how many
statements stood behind each row, and `printings_agree` records whether they
said the same thing.""",
    "goa": """Goa publishes ward-level reservation for village panchayats. The
2012 cycle names the winner; 2017 and 2022 are nomination-stage listings and
name nobody, which is a property of the document rather than a gap in the
parse. Ward numbers arrive in five different shapes, including one with a soft
hyphen inside it (`Ward­IV`), so they are normalised rather than read
literally.""",
    "karnataka": """Two very different sources sit under this state. The
1993-2007 gram panchayat rows come from a Stata file, a reservation history
that names no winner in any cycle because it is a roster rather than a result.
The 2016 taluk and zilla panchayat rows come from 195 notifications harvested
from the web archive's copy of `karsec.gov.in`; every one of them is a copier
scan with no text layer, read with Surya, and they carry the party the winner
represented, which almost nothing else in this corpus does.

**Two further groups of documents were harvested, are committed here, and are
deliberately not parsed.** Saying so is the point of this paragraph: they are
not a gap and nobody needs to look at them again.

`tzp_2016_reservation` is 211 files of seat-level reservation for the same 2016
seats the notifications cover - and the notifications' own third column already
states the reservation, so reading these would produce a second opinion on a
field we have rather than a new field.

`gp_2015` is 33 files in which nobody is named. Form-1 counts nomination papers
received, Form-2 those valid after scrutiny, Form-3 the candidates left in the
fray, Form-5 turnout, and the file called `Result.pdf` is Form-4 - the final
count including unopposed wins, but as district x taluk x 26 numeric columns.
The one thing in it worth knowing about is that those per-taluk counts of seats
and members elected by category are the shape of an external denominator, and
they come from the commission that ran the election rather than from the LGD
register. That is a different job from parsing seats.

Both groups keep their manifests, so any file can be traced to the URL and
capture it came from, and re-read by anyone who disagrees with this.""",
    "jharkhand": """Place names are printed in Kruti Dev, a legacy font
encoding rather than Unicode, and are shipped as they were printed - `script`
says so on every row. They are not transliterated, so joining these to another
source on name will not work without transliterating first.

The filenames do not reliably say which tier a file holds, so tier is decided
from the contents. A third of the PDFs have no ruling lines at all.""",
    "jk": """The holdings are an ad-hoc subset of districts rather than a
corpus, and there is no reliable published total to measure them against, so
no completeness figure is quoted - an invented denominator would be worse than
admitting there is not one.

The 2018 documents list **only the reserved seats**. Their 82% women's share is
a fact about which pages were published, not about J&K, and `listing_scope`
marks every such row. Do not compute shares across it.""",
}

# What each state's own substantive checks appeal to. These are the checks that
# actually catch silent corruption, since every parser bug in this repo produced
# plausible values rather than an error.
STATE_CHECKS = {
    "ap": [
        "each gazette's own FORMAT-I abstract, district by district",
        "agreement between the two proformas that state a seat twice",
        "the share of category cells that needed OCR repair",
    ],
    "goa": [
        "the published count of panchayats that went to poll in 2012",
        "the ward set, compared across the three cycles",
        "per-taluka coverage against 2012, which is complete",
    ],
    "jharkhand": [
        "the published seat totals for each tier",
        "how much of the gap is the source's and how much the "
        "parser's, decided by opening the file",
    ],
    "jk": [
        "SC-reserved wards against SC population, the strongest check available here",
        "the women's share against the one-third floor",
    ],
}

MAKE_TARGET = {"ap": "ap", "goa": "goa", "jharkhand": "jharkhand", "jk": "jk"}


def stats_rows(name):
    path = DATA / "stats" / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


STATUS_MARK = {"pass": "&check;", "warn": "!", "fail": "&cross;", "skip": "&ndash;"}


def render_checks(state):
    """The check grid for one state, from data/stats/slice_checks.csv.

    A skip renders as a dash and never as a tick. That is the whole point: the
    two largest slices in this repository went unchecked for row loss because a
    skip read like a pass.
    """
    rows = [r for r in stats_rows("slice_checks.csv") if r["state"] == state]
    if not rows:
        return []
    slices = sorted({(r["year"], r["tier"]) for r in rows})
    checks = sorted({r["check_id"] for r in rows})
    appeals = {r["check_id"]: r["appeals_to"] for r in rows}
    grid = {(r["year"], r["tier"], r["check_id"]): r for r in rows}

    out = [
        "| Check | Appeals to | " + " | ".join(f"{y} `{t}`" for y, t in slices) + " |",
        "|---|---|" + "---|" * len(slices),
    ]
    for check in checks:
        cells = []
        for year, tier in slices:
            got = grid.get((year, tier, check))
            if not got:
                cells.append("")
                continue
            mark = STATUS_MARK.get(got["status"], got["status"])
            shown = got["observed"][:22]
            cells.append(f"{mark} {shown}".strip())
        out.append(f"| `{check}` | {appeals[check]} | " + " | ".join(cells) + " |")
    out.append("")
    out.append(
        "&check; pass &nbsp; ! warn &nbsp; &cross; fail &nbsp; "
        "&ndash; skipped, meaning no rule is declared for that slice — "
        "which is not the same as passing."
    )
    return out


def render_stats(state):
    rows = [r for r in stats_rows("slice_stats.csv") if r["state"] == state]
    if not rows:
        return []
    out = [
        "| Year | Tier | Rows | Districts | Blocks | Panchayats | "
        "Women | SC | ST | BC | Sources |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda x: (x["year"], x["tier"])):

        def pct(key):
            return f"{float(r[key]) * 100:.0f}%" if r[key] else "—"

        out.append(
            f"| {r['year']} | `{r['tier']}` | {int(r['rows']):,} | "
            f"{r['districts']} | {r['blocks']} | {int(r['panchayats']):,} | "
            f"{pct('women_share')} | {pct('sc_share')} | {pct('st_share')} | "
            f"{pct('bc_share')} | {r['source_documents']} docs, "
            f"{int(r['source_pages']):,} pages |"
        )
    return out


def slices_by_directory():
    grouped = collections.defaultdict(list)
    for entry in coverage.slices():
        grouped[entry["dir"]].append(entry)
    return grouped


def dataset_files(directory):
    """Parsed outputs in this directory, with what each holds."""
    out = []
    for path, rows in datasets.parsed():
        if path.parent.name != directory:
            continue
        out.append(
            {
                "name": path.name,
                "stem": path.stem,
                "rows": len(rows),
                "columns": len(rows[0]),
                "sources": len({r.get("source_path", "") for r in rows}),
            }
        )
    return out


def source_documents(directory):
    """Every document the rows cite, and whether it is actually here."""
    cited, missing = set(), set()
    for path in sorted((DATA / directory).glob("*.csv")):
        with path.open(encoding="utf-8", errors="replace") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames or "source_path" not in reader.fieldnames:
                continue
            for row in reader:
                target = (row.get("source_path") or "").strip()
                if not target:
                    continue
                cited.add(target)
                if not (ROOT / target).exists():
                    missing.add(target)
    return sorted(cited), sorted(missing)


def source_files(directory):
    """Files actually held, not counting the readme this script writes - which
    would otherwise make every directory report one file more than it has.
    """
    return sorted(
        p
        for p in (DATA / directory).rglob("*")
        if p.is_file() and p.name != "readme.md" and not p.name.startswith(".")
    )


def raw_inventory(directory):
    path = DATA / "inventory.csv"
    if not path.exists():
        return collections.Counter(), 0
    kinds, pages = collections.Counter(), 0
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["state"] != directory:
                continue
            kinds[row["format"]] += 1
            if (row.get("pages") or "").isdigit():
                pages += int(row["pages"])
    return kinds, pages


def render_parsed(directory, state, entries):
    files = dataset_files(directory)
    cited, missing = source_documents(directory)
    kinds, pages = raw_inventory(directory)
    total = sum(e["rows"] for e in entries)

    out = [f"# {state} — local body reservation", ""]
    out.append(
        "*Generated by `make state-readmes`. Edits here are overwritten "
        "— change the data or the generator instead.*"
    )
    out.append("")
    out.append(
        f"{total:,} rows across {len(entries)} "
        f"{'slice' if len(entries) == 1 else 'slices'}, parsed from "
        f"{len(cited)} source "
        f"{'document' if len(cited) == 1 else 'documents'} committed "
        f"alongside."
    )
    out.append("")

    out.append("## What is here")
    out.append("")
    out.append("| Year | Tier | Rows | Women | Districts | vs published | Notes |")
    out.append("|---|---|---|---|---|---|---|")
    for e in entries:
        out.append(
            f"| {e['year']} | `{e['tier']}` | {e['rows']:,} | "
            f"{e['women']:.0f}% | {e['districts']} | {e['coverage']} | "
            f"{e['notes'] or '—'} |"
        )
    out.append("")
    out.append(
        "Read the notes before the numbers — several of them say that a "
        "share is a property of which pages were published rather than "
        "of the state."
    )
    out.append("")

    out.append("## Files")
    out.append("")
    out.append(
        "Every file is written twice: `.csv` for a spreadsheet, "
        "`.jsonl` for a reader that should not break when a column is "
        "added."
    )
    out.append("")
    out.append("| File | Rows | Columns | Source documents |")
    out.append("|---|---|---|---|")
    for f in files:
        out.append(
            f"| [`{f['name']}`]({f['name']}) | {f['rows']:,} | "
            f"{f['columns']} | {f['sources']} |"
        )
    out.append("")

    stats = render_stats(state)
    if stats:
        out.append("## Stats")
        out.append("")
        out += stats
        out.append("")
        out.append(
            "Generated by `make stats` into "
            "[../stats/slice_stats.csv](../stats/slice_stats.csv). "
            "Snapshot that file before changing a parser and diff it "
            "after: a change that only renames things must not move a "
            "single number."
        )
        out.append("")

    note = STATE_NOTES.get(directory)
    if note:
        out.append("## About these sources")
        out.append("")
        out.append(note.strip())
        out.append("")

    out.append("## Provenance")
    out.append("")
    out.append(
        "Every row carries `source_path` and `source_page` — the "
        "document it was read from and the page within it. The "
        "documents are committed here, so any row can be checked "
        "against the page it came from without a network round trip. "
        "That mattered repeatedly: nearly every parser bug in this "
        "repository produced plausible wrong values rather than an "
        "error, and opening the page was the only way to settle it."
    )
    out.append("")
    if missing:
        out.append(
            f"⚠️ {len(missing)} cited "
            f"{'document is' if len(missing) == 1 else 'documents are'} "
            f"not on disk: `{missing[0]}`"
            + ("" if len(missing) == 1 else " and others")
        )
    else:
        out.append(f"All {len(cited)} cited documents are present.")
    out.append("")
    if kinds:
        described = ", ".join(f"{n} {k}" for k, n in kinds.most_common())
        out.append(
            f"Inventory for this directory: {described}"
            + (f", {pages:,} pages total." if pages else ".")
        )
        out.append("")

    out.append("## Reproducing")
    out.append("")
    out.append("```")
    out.append(f"make {MAKE_TARGET.get(directory, directory)}")
    out.append("```")
    out.append("")
    out.append(
        f"Parses from the committed documents and rewrites the files "
        f"above, then runs `src/local_reservations/states/{directory}/validate.py`."
    )
    out.append("")

    grid = render_checks(state)
    checks = STATE_CHECKS.get(directory)
    out.append("## What is checked")
    out.append("")
    out.append(
        "Every state runs a shared battery first — the seat key is "
        "unique, the reservation label agrees with the two fields it "
        "summarises, every `source_path` exists and every "
        "`source_page` falls inside its document. Then this state's own "
        "checks, which are the ones that catch silent corruption "
        "because they appeal to something outside the data:"
    )
    out.append("")
    for check in checks or ["—"]:
        out.append(f"- {check}")
    out.append("")
    if grid:
        out.append("")
        out += grid
        out.append("")
        out.append(
            "Each check declares what it **appeals to**. Only an "
            "external appeal - a published total, a statutory share, a "
            "population - reliably catches silent corruption; an "
            "internal check confirms the file agrees with itself, which "
            "it does whether or not a category was misread."
        )
        out.append("")
    out.append(
        "Column meanings are in [../../DICTIONARY.md](../../DICTIONARY.md). "
        "Expectation violations across every state are triaged into "
        "[../expectations_report.csv](../expectations_report.csv)."
    )
    return "\n".join(out) + "\n"


def render_sibling(directory, state, years, tiers, url):
    """A state parsed in its own repository. What sits here is the source
    material it was parsed from, which is worth saying plainly - the directory
    otherwise looks like a state nobody has got to yet.
    """
    kinds, pages = raw_inventory(directory)
    files = source_files(directory)
    name = url.rsplit("/", 1)[-1]
    out = [f"# {state} — local body reservation", ""]
    out.append(
        "*Generated by `make state-readmes`. Edits here are overwritten "
        "— change the data or the generator instead.*"
    )
    out.append("")
    out.append(
        f"**The parsed data for {state} is in "
        f"[{name}]({url})** — {tiers}, {years}. It was split into its "
        f"own repository, so it is counted in the [top-level "
        f"readme](../../readme.md) but has no rows here."
    )
    out.append("")
    out.append(
        f"What is in this directory is source material: {len(files)} "
        f"{'file' if len(files) == 1 else 'files'}"
        + (
            f", {', '.join(f'{n} {k}' for k, n in kinds.most_common())}"
            + (f", {pages:,} pages" if pages else "")
            if kinds
            else ""
        )
        + "."
    )
    out.append("")
    out.append(
        "It is not in this repository's schema, so it does not appear "
        "in the per-slice table. Bringing a sibling to that grain means "
        "giving its parsed files the shared columns — `state`, `year`, "
        "`tier`, `caste_reservation`, `woman_reserved` — which is the "
        "schema harmonisation still to be done."
    )
    return "\n".join(out) + "\n"


def render_unparsed(directory, state, status, where):
    kinds, pages = raw_inventory(directory)
    files = source_files(directory)
    out = [f"# {state} — local body reservation", ""]
    out.append(
        "*Generated by `make state-readmes`. Edits here are overwritten "
        "— change the data or the generator instead.*"
    )
    out.append("")
    out.append(
        f"**Status: {status}.** Nothing in this directory is in the "
        f"repository's schema yet, so it does not appear in the "
        f"per-slice table in the [top-level readme](../../readme.md)."
    )
    out.append("")
    if status == "tables, other layout":
        out.append(
            "The documents or tables are here and nobody has parsed "
            "them into this repository's schema yet. This is open work, "
            "not coverage already achieved - a distinction the old label "
            '"prior work, other schema" blurred, which is how '
            "Rajasthan sat here for months while its parse existed in "
            "another repository."
        )
        out.append("")
        if where:
            out.append(f"Recorded years: {where}.")
            out.append("")
    out.append(f"{len(files)} {'file' if len(files) == 1 else 'files'} on disk.")
    if kinds:
        described = ", ".join(f"{n} {k}" for k, n in kinds.most_common())
        out.append("")
        out.append(
            f"Inventory: {described}" + (f", {pages:,} pages total." if pages else ".")
        )
    out.append("")
    out.append("## What it would take")
    out.append("")
    out.append(
        "See [../../SOURCES.md](../../SOURCES.md) for where this state "
        "publishes its reservation data and what parsing it involves. "
        "A parser lands in `src/local_reservations/states/<state>/parse.py`, writes through "  # noqa: E501
        "`local_reservations/common/emit.py` so every row carries its source "
        "document and page, and is paired with a `validate.py` that "
        "checks the result against something outside the data — a "
        "published total, a statutory share, a population."
    )
    return "\n".join(out) + "\n"


def build():
    """Return {path: text} for every state directory."""
    entries = slices_by_directory()
    legacy = {d: (state, years) for state, (years, d) in coverage.LEGACY.items()}
    siblings = {
        state: (
            spec["years"],
            spec["tiers"],
            f"https://github.com/in-rolls/{spec['repo']}",
        )
        for state, spec in coverage.SIBLINGS.items()
    }

    out = {}
    for directory in sorted(
        p.name for p in DATA.iterdir() if p.is_dir() and p.name not in datasets.DERIVED
    ):
        state = coverage.pretty(directory)
        target = DATA / directory / "readme.md"
        if directory in entries:
            out[target] = render_parsed(directory, state, entries[directory])
        elif directory in legacy:
            name, years = legacy[directory]
            out[target] = render_unparsed(
                directory, name, "tables, other layout", years
            )
        elif state in siblings:
            years, tiers, url = siblings[state]
            out[target] = render_sibling(directory, state, years, tiers, url)
        else:
            out[target] = render_unparsed(directory, state, "documents, no parser", "")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--check",
        action="store_true",
        help="fail if any file differs from what would be written",
    )
    args = ap.parse_args()

    written = build()
    stale = []
    for path, text in sorted(written.items()):
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == text:
            continue
        stale.append(path.relative_to(ROOT))
        if not args.check:
            path.write_text(text, encoding="utf-8")

    if args.check:
        if stale:
            print(f"{len(stale)} state readme(s) out of date:")
            for path in stale:
                print(f"   {path}")
            return 1
        print(f"  {len(written)} state readmes up to date")
        return 0

    print(f"wrote {len(stale)} of {len(written)} state readmes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
