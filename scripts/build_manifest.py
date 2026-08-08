"""Pin the corpus, so a citation means one thing.

Without this there is no way to say "the data as of March". A tag alone is not
enough either: it pins this repository's tree, but the master is built from
siblings that live elsewhere and move on their own schedule, so a row's origin
is only reproducible if the sibling's commit is written down beside it.

Writes MANIFEST.json (the record) and MANIFEST.md (the same thing readable).

**Two builds from the same tree must be byte-identical**, or verification fails
on somebody else's machine for no reason. That rules out a wall-clock timestamp,
so the manifest is dated by the git commit rather than by when it was generated.
It also rules out trusting a dirty sibling: rows attributed to a commit did not
come from that commit, so `dirty` is recorded and release-check refuses.
"""

import argparse
import collections
import csv
import hashlib
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "common"))
import adapters  # noqa: E402
import datasets  # noqa: E402
import master as M  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST_JSON = ROOT / "MANIFEST.json"
MANIFEST_MD = ROOT / "MANIFEST.md"

# Bumped whenever MASTER_COLUMNS changes, so a consumer can tell a schema change
# from a data change without diffing the header.
SCHEMA_VERSION = 1


def git(directory, *args):
    try:
        return subprocess.run(["git", "-C", str(directory), *args],
                              capture_output=True, text=True,
                              timeout=60).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return ""


# The manifest itself does not count. Writing it dirties the tree, so a build
# that checked plain `git status` reported clean on its first run and dirty on
# its second - the manifest recording a fact its own existence changed.
GENERATED = ("MANIFEST.json", "MANIFEST.md")


def repo_state(directory):
    changed = [line for line in git(directory, "status", "--porcelain").split("\n")
               if line.strip() and not any(line.strip().endswith(name)
                                           for name in GENERATED)]
    return {
        "commit": git(directory, "rev-parse", "HEAD"),
        "committed_utc": git(directory, "show", "-s", "--format=%cI", "HEAD"),
        "dirty": bool(changed),
    }


def digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            sha.update(chunk)
    return sha.hexdigest()


def read(path):
    with path.open(encoding="utf-8", errors="replace") as fh:
        return list(csv.DictReader(fh))


def describe(path, rows):
    """One file's entry. Row-level facts come from the rows, not the filename."""
    entry = {
        "path": str(path.relative_to(ROOT)),
        "sha256": digest(path),
        "bytes": path.stat().st_size,
        "rows": len(rows),
    }
    if not rows:
        return entry
    first = rows[0]
    if "dataset_id" in first:
        entry["dataset_ids"] = sorted({r["dataset_id"] for r in rows})
    for column, key in (("provenance_level", "provenance_level"),
                        ("listing_scope", "listing_scopes"),
                        ("tier", "tiers"), ("state", "states"),
                        ("year", "years")):
        if column in first:
            entry[key] = sorted({r[column] for r in rows if r[column]})
    if "seat_key_unique" in first:
        entry["rows_identifying_a_distinct_seat"] = sum(
            1 for r in rows if r["seat_key_unique"] == "1")
    return entry


def build():
    here = repo_state(ROOT)
    files, totals = [], collections.Counter()

    master_dir = ROOT / "data" / "master"
    for path in sorted(master_dir.glob("master_*.csv")):
        rows = read(path)
        files.append(dict(describe(path, rows), kind="master"))
        if path.name not in ("master_extras.csv", "master_dropped.csv",
                             "master_key_collisions.csv"):
            totals["master_rows"] += len(rows)
            totals["master_states"] += 1

    # every parsed per-state file too, so a tag pins the whole corpus and not
    # only the pooled view of it
    for path, rows in datasets.parsed():
        files.append(dict(describe(path, rows), kind="parsed"))
        totals["parsed_rows"] += len(rows)

    siblings = []
    for name, adapter in sorted(adapters.REGISTRY.items()):
        directory = ROOT.parent / adapter.REPO
        entry = {"state": name, "repo": adapter.REPO, "url": adapter.URL,
                 "present": directory.exists()}
        if directory.exists():
            entry.update(repo_state(directory))
        siblings.append(entry)

    return {
        "schema_version": SCHEMA_VERSION,
        "release": "",
        # The commit this was BUILT FROM, which is necessarily the parent of
        # the commit that contains it - a file cannot record the hash of the
        # commit it is part of. Named so nobody reads it as "the release
        # commit". The SHA-256s below are what actually pins the data; this is
        # for tracing which tree produced them.
        "built_from_commit": here["commit"],
        # the commit's date, not the wall clock: two builds from one tree must
        # be byte-identical or verification fails for no reason
        "committed_utc": here["committed_utc"],
        "dirty": here["dirty"],
        "master_columns": M.MASTER_COLUMNS,
        "totals": dict(totals),
        "sibling_repos": siblings,
        "files": files,
    }


def render(manifest):
    out = ["# Manifest", "",
           "*Generated by `make manifest`. Verify a checkout with "
           "`python3 scripts/verify_manifest.py`.*", "",
           f"- schema version **{manifest['schema_version']}**",
           f"- built from commit `{manifest['built_from_commit'][:12]}`"
           + (" **(dirty)**" if manifest["dirty"] else "")
           + " — necessarily the parent of the commit holding this file",
           f"- {manifest['totals'].get('master_rows', 0):,} pooled seats, "
           f"{manifest['totals'].get('parsed_rows', 0):,} parsed rows", "",
           "## Siblings", "",
           "The master is built from repositories that move on their own "
           "schedule, so a row's origin is only reproducible with the commit it "
           "was read at.", "",
           "| State | Repository | Commit | Present |", "|---|---|---|---|"]
    for s in manifest["sibling_repos"]:
        commit = s.get("commit", "")[:12] + (" (dirty)" if s.get("dirty") else "")
        out.append(f"| {s['state']} | [{s['repo']}]({s['url']}) | "
                   f"`{commit or '—'}` | {'yes' if s['present'] else 'no'} |")
    out += ["", "## Files", "",
            "| File | Rows | Bytes | SHA-256 |", "|---|---|---|---|"]
    for f in manifest["files"]:
        out.append(f"| `{f['path']}` | {f['rows']:,} | {f['bytes']:,} | "
                   f"`{f['sha256'][:16]}…` |")
    out += ["", "## Schema", "",
            f"`master_columns` records the exact ordered column list, so a "
            f"consumer can detect a schema change without diffing a header:",
            "", "```", ", ".join(manifest["master_columns"]), "```", ""]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", default="", help="tag this manifest describes")
    ap.add_argument("--check", action="store_true",
                    help="fail if the manifest on disk is out of date")
    args = ap.parse_args()

    manifest = build()
    if args.release:
        manifest["release"] = args.release
    text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"

    if args.check:
        current = MANIFEST_JSON.read_text(encoding="utf-8") if MANIFEST_JSON.exists() else ""
        if current != text:
            print("MANIFEST.json is out of date - run `make manifest`")
            return 1
        print(f"  manifest current: {len(manifest['files'])} files")
        return 0

    MANIFEST_JSON.write_text(text, encoding="utf-8")
    MANIFEST_MD.write_text(render(manifest), encoding="utf-8")
    print(f"\n{len(manifest['files'])} files -> MANIFEST.json")
    print(f"  {manifest['totals'].get('master_rows', 0):,} pooled seats, "
          f"{manifest['totals'].get('parsed_rows', 0):,} parsed rows")
    dirty = [s["repo"] for s in manifest["sibling_repos"] if s.get("dirty")]
    if manifest["dirty"] or dirty:
        print(f"  uncommitted changes in: "
              f"{['local_elections'] * manifest['dirty'] + dirty}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
