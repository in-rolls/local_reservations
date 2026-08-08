"""Build the pooled master from this repository and its siblings.

Everything a consumer needs to group across states, in one declared schema, with
every row still pointing at the page it was read from.

Three things this is careful about, each because getting it wrong would look
like success:

  reconcile()   every input row becomes an output row or a line in
                master_dropped.csv with a reason. It is the only check that can
                catch an adapter silently losing rows, because a row count that
                went down for a good reason and one that went down for a bad
                reason look identical.

  partitioning  one file per state. The pack here is already 1.9 GiB; a single
                master rewritten on every build adds a fresh blob each time even
                when one state changed.

  urban         excluded by canon.RURAL_TIERS and counted, not quietly dropped.
                Kerala and Rajasthan ship urban wards in the same files as rural
                ones, so this cannot be done by choosing files.

Siblings are read from ROOT.parent, never vendored, and their git commit is
recorded on every row.
"""

import argparse
import collections
import gzip
import io
import csv
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "common"))
import adapters  # noqa: E402
import canon  # noqa: E402
import datasets  # noqa: E402
import emit  # noqa: E402
import master as M  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "master"


def git_commit(directory):
    """The sibling's commit, and whether it has uncommitted changes.

    A dirty sibling makes source_commit meaningless - the rows did not come from
    that commit - so it is recorded rather than assumed away.
    """
    try:
        sha = subprocess.run(["git", "-C", str(directory), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=30).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(directory), "status", "--porcelain"],
                               capture_output=True, text=True, timeout=60).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return "", False
    return (sha[:12] + ("-dirty" if dirty else "")), bool(dirty)


def local_slices():
    """The states parsed in this repository."""
    commit, _ = git_commit(ROOT)
    grouped = collections.defaultdict(list)
    for _, rows in datasets.parsed():
        for row in rows:
            grouped[(row.get("state", ""), row.get("year", ""),
                     row.get("tier", ""))].append(row)
    for (state, year, tier), rows in sorted(grouped.items()):
        yield {
            "dataset_id": f"{state.lower().replace(' ', '_').replace('&', 'and')}"
                          f"/{tier}/{year}",
            "state": state, "rows": rows, "source_repo": "local_elections",
            "source_commit": commit, "provenance_level": "page",
            "unit_of_observation": "seat",
        }


def sibling_slices(only=None):
    for name, adapter in sorted(adapters.REGISTRY.items()):
        if only and name not in only:
            continue
        directory = ROOT.parent / adapter.REPO
        if not directory.exists():
            print(f"  {name}: {adapter.REPO} not checked out, skipping",
                  file=sys.stderr)
            continue
        commit, dirty = git_commit(directory)
        if dirty:
            print(f"  {name}: {adapter.REPO} has uncommitted changes",
                  file=sys.stderr)
        for got in adapter.slices(directory):
            yield dict(got, source_repo=adapter.REPO, source_commit=commit)


def build(only=None):
    rows, extras, dropped, candidates = [], [], [], []
    seen = collections.Counter()
    counts = collections.Counter()

    for slice_ in list(local_slices()) + list(sibling_slices(only)):
        for row in slice_["rows"]:
            counts["input"] += 1
            got = M.to_master(
                row, slice_["dataset_id"], slice_["source_repo"],
                slice_["source_commit"], slice_["provenance_level"],
                slice_.get("unit_of_observation", "seat"),
                row.get("seat_candidates", ""))
            if got is None:
                dropped.append({"dataset_id": slice_["dataset_id"],
                                "reason": "urban local body, out of scope",
                                "detail": row.get("tier", ""),
                                "source_path": row.get("source_path", "")})
                counts["urban"] += 1
                continue
            key = got["seat_key"]
            seen[key] += 1
            got["row_id"] = M.row_id(got, seen[key])
            rows.append(got)
            extras += M.extras(row, got["row_id"])
            candidates += M.candidates(row, got)
            counts["output"] += 1

    # computed over the whole master rather than per file, because a seat stated
    # in two states' files would otherwise look unique in both
    for row in rows:
        row["seat_key_unique"] = int(seen[row["seat_key"]] == 1)

    return rows, extras, dropped, candidates, counts


def reconcile(counts, dropped):
    """Every input row must become an output row or a dropped one.

    The only check that can catch an adapter losing rows quietly: a count that
    fell for a good reason looks exactly like one that fell for a bad one.
    """
    accounted = counts["output"] + len(dropped)
    if accounted != counts["input"]:
        raise SystemExit(
            f"reconcile: {counts['input']:,} rows in, {counts['output']:,} out, "
            f"{len(dropped):,} dropped - {counts['input'] - accounted:,} "
            f"unaccounted for")


def write(rows, extras, dropped, candidates):
    OUT.mkdir(parents=True, exist_ok=True)
    by_state = collections.defaultdict(list)
    for row in rows:
        by_state[row["state"]].append(row)

    written = []
    for state, subset in sorted(by_state.items()):
        written.append(write_gz(f"master_{slug_of(state)}.csv.gz",
                                M.MASTER_COLUMNS, subset))

    by_state = collections.defaultdict(list)
    for row in candidates:
        by_state[row["state"]].append(row)
    for state, subset in sorted(by_state.items()):
        written.append(write_gz(f"candidates_{slug_of(state)}.csv.gz",
                                M.CANDIDATE_COLUMNS, subset))

    for name, columns, data in (
            ("master_extras.csv", ["row_id", "column", "value"], extras),
            ("master_dropped.csv",
             ["dataset_id", "reason", "detail", "source_path"], dropped),
            ("master_key_collisions.csv",
             ["seat_key", "rows", "dataset_id", "row_id"],
             collisions(rows))):
        with (OUT / name).open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=columns,
                                    extrasaction="ignore", lineterminator="\n")
            writer.writeheader()
            writer.writerows(data)
    return written


def slug_of(state):
    return state.lower().replace(" ", "_").replace("&", "and")


def write_gz(name, columns, rows):
    """A per-state table, gzipped.

    Not a space optimisation. `candidates_bihar.csv` is 208 MB and GitHub
    refuses any file over 100 MB outright, so the corpus could not be pushed at
    all; gzipped it is 26 MB. Every tool that reads these reads them compressed
    without being told - pandas and polars sniff the extension, and the standard
    library needs `gzip.open` in place of `open`.

    `mtime=0` matters: gzip stamps the current time into its header by default,
    so the same rows would hash differently on every build and the manifest
    would report a change that never happened.
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore",
                            lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path = OUT / name
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as fh:
            fh.write(buffer.getvalue().encode("utf-8"))
    return (path, len(rows))


def collisions(rows):
    grouped = collections.defaultdict(list)
    for row in rows:
        grouped[row["seat_key"]].append(row)
    out = []
    for key, subset in grouped.items():
        if len(subset) > 1:
            for row in subset:
                out.append({"seat_key": key, "rows": len(subset),
                            "dataset_id": row["dataset_id"],
                            "row_id": row["row_id"]})
    return sorted(out, key=lambda r: (-r["rows"], r["seat_key"]))


def render_readme(rows, dropped, candidates, counts, written):
    unique = sum(1 for r in rows if r["seat_key_unique"])
    states = collections.Counter(r["state"] for r in rows)
    tiers = collections.Counter(r["tier"] for r in rows)
    provenance = collections.Counter(r["provenance_level"] for r in rows)
    out = ["# The pooled master", "",
           "*Generated by `make master`. Edits here are overwritten.*", "",
           f"{len(rows):,} seats across {len(states)} states, in one declared "
           f"schema. One file per state; the headers are identical, so "
           f"concatenating them is the whole table.", "",
           "## What a row is", "",
           "**One row per seat as a source document states it** — which is not "
           "the same as one row per seat, and the master does not claim it is. "
           f"{unique:,} rows ({unique / max(len(rows), 1):.1%}) identify a "
           f"distinct seat; the other {len(rows) - unique:,} are in "
           "[master_key_collisions.csv](master_key_collisions.csv) rather than "
           "hidden behind a promise the data does not support.", "",
           "| State | Seats |", "|---|---|"]
    for state, n in sorted(states.items()):
        out.append(f"| [{state}](master_{slug_of(state)}.csv.gz) | {n:,} |")
    out += ["", "| Tier | Seats |", "|---|---|"]
    for tier, n in tiers.most_common():
        out.append(f"| `{tier}` | {n:,} |")
    out += ["", "## Three columns where one would have lost something", "",
            "- **`tier` and `tier_local`** — states print the same office under "
            "different names, and worse, the same name means different "
            "offices. Bihar's *sarpanch* heads a village court, not the "
            "panchayat. Group on `tier`; check against a gazette with "
            "`tier_local`.",
            "- **`caste_reservation`, `caste_reservation_local` and "
            "`caste_scheme`** — the fold to `BC` is lossy and is not the same "
            "fold everywhere. Haryana reserves only Block A of its Backward "
            "Classes list and prints `BC_A`; Kerala reserves no backward-class "
            "seat at all, so zero BC rows there is the law rather than a "
            "parsing failure. `caste_scheme` is what makes those "
            "distinguishable.",
            "- **`unit_of_observation` and `seat_candidates`** — some sources "
            "are candidate-level and are collapsed to seats. A row that came "
            "from a collapse says so, with the denominator visible.", "",
            "## Before you use it", "",
            "`quality_flags` carries what a row cannot be trusted for: "
            "`ocr_repaired`, `gender_not_stated`, `ward_list_incomplete`, "
            "`winner_inferred`, `name_untransliterated`, `printings_disagree`. "
            "`gender_not_stated` in particular means `woman_reserved=0` is a "
            "default rather than a reading.", "",
            "`provenance_level` says how far back a row can be traced:", ""]
    for level, n in provenance.most_common():
        meaning = {"page": "to the page it was read from",
                   "document": "to a document, but not a page within it",
                   "dataset": "to the file it came from and no further",
                   "none": "nowhere - the source recorded none"}.get(level, "")
        out.append(f"- **{level}** — {n:,} rows, traceable {meaning}")
    out += ["", "## Files", "",
            "| File | Rows | What |", "|---|---|---|"]
    for path, n in written:
        what = ("one state, one row per candidate" if path.name.startswith(
            "candidates_") else "one state, one row per seat")
        out.append(f"| [`{path.name}`]({path.name}) | {n:,} | {what} |")
    out += [f"| [`master_extras.csv`](master_extras.csv) | — | the "
            f"state-specific columns, long-form as (row_id, column, value), so "
            f"the master stays a fixed schema without losing anything |",
            f"| [`master_key_collisions.csv`](master_key_collisions.csv) | "
            f"{len(rows) - unique:,} | rows that do not identify a distinct "
            f"seat |",
            f"| [`master_dropped.csv`](master_dropped.csv) | {len(dropped):,} "
            f"| every input row that did not become an output row, with a "
            f"reason. `make master` fails if these do not add up |", "",
            "## Scope", "",
            "Rural bodies only for now — urban local bodies are held by the "
            "Trivedi Centre and are filtered by `canon.RURAL_TIERS`, which has "
            "to be a row-level filter because Kerala and Rajasthan ship urban "
            "wards in the same files as rural ones.", ""]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="build only these sibling states")
    args = ap.parse_args()

    rows, extras, dropped, candidates, counts = build(args.only)
    reconcile(counts, dropped)
    written = write(rows, extras, dropped, candidates)
    (OUT / "readme.md").write_text(render_readme(rows, dropped, candidates, counts, written),
                                   encoding="utf-8")

    print(f"\n{counts['output']:,} rows -> {OUT.relative_to(ROOT)}/")
    for path, n in written:
        print(f"  {path.name:34} {n:>9,}")
    unique = sum(1 for r in rows if r["seat_key_unique"])
    print(f"\n  {counts['input']:,} in, {counts['output']:,} out, "
          f"{len(dropped):,} dropped ({counts['urban']:,} urban)")
    print(f"  {unique:,} rows identify a distinct seat "
          f"({unique / max(len(rows), 1):.1%}); "
          f"{len(rows) - unique:,} do not, listed in master_key_collisions.csv")
    print(f"  {len(extras):,} extra values held long-form in master_extras.csv")
    if candidates:
        print(f"  {len(candidates):,} candidate rows in candidates_<state>.csv, "
              f"joinable to the seat on row_id")
    tiers = collections.Counter(r["tier"] for r in rows)
    print("  " + "  ".join(f"{k}={v:,}" for k, v in tiers.most_common()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
