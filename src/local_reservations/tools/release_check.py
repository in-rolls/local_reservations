"""The last gate before a tag.

Everything upstream of this in `make release-check` has already run - the tests,
the master, the stats, the worklist, the coverage links, the manifest and its
verification. What is left is the question none of those ask: is this tree in a
state you would want to be able to cite forever?

It refuses on a dirty tree or a dirty sibling, because a manifest that
attributes rows to a commit they did not come from is worse than no manifest.
It prints the tag command rather than running it.
"""

import json
import subprocess
import sys

from local_reservations.paths import ROOT

# Everything in the repository that is written by a generator rather than by
# hand. `make coverage` rebuilds them all, so a stale one leaves the tree dirty
# and this script already refuses - but it refused with "uncommitted changes",
# which does not tell anyone that the readme was out of date. Naming them turns
# a puzzle into an instruction.
GENERATED = [
    "readme.md",
    "WORKLIST.md",
    "MANIFEST.json",
    "MANIFEST.md",
    "DICTIONARY.md",
]


def dirty_files():
    """Paths git reports as changed, relative to the repository root."""
    out = subprocess.run(
        ["git", "-C", str(ROOT), "status", "--porcelain"],
        capture_output=True,
        text=True,
    ).stdout
    return [line[3:].strip() for line in out.splitlines() if line.strip()]


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else ""
    manifest = json.loads((ROOT / "MANIFEST.json").read_text(encoding="utf-8"))

    problems = []
    if manifest.get("dirty"):
        changed = dirty_files()
        stale = [f for f in changed if f in GENERATED or f.startswith("data/")]
        problems.append("this repository has uncommitted changes")
        for path in changed[:8]:
            note = ""
            if path in GENERATED:
                note = (
                    "  <- generated; `make coverage` rebuilt it, so it was out of date"
                )
            problems.append(f"    {path}{note}")
        if len(changed) > 8:
            problems.append(f"    ... and {len(changed) - 8} more")
        if stale:
            problems.append(
                "  commit these: a release pins file hashes, so a "
                "generated file that is not committed is not the "
                "one the manifest describes"
            )
    for sibling in manifest.get("sibling_repos", []):
        if sibling.get("dirty"):
            problems.append(f"{sibling['repo']} has uncommitted changes")
        if not sibling.get("present"):
            problems.append(
                f"{sibling['repo']} is not checked out, so its "
                f"state is missing from this release"
            )

    print()
    if problems:
        print("Not ready to tag:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    rows = manifest["totals"].get("master_rows", 0)
    states = len(
        {
            s
            for f in manifest["files"]
            for s in f.get("states", [])
            if f.get("kind") == "master"
        }
    )
    print(
        f"Ready to tag: {rows:,} pooled seats across {states} states, "
        f"{len(manifest['files'])} files pinned."
    )
    if not version:
        print(
            "\nRe-run with a version to get the command:"
            "\n  make release-check VERSION=v0.1.0"
        )
        return 0
    print(
        f"\nRun this yourself - a tag cannot be taken back:\n"
        f"  uv run build-manifest --release {version} && \\\n"
        f"  git add MANIFEST.json MANIFEST.md && \\\n"
        f"  git commit -m 'Release {version}' && \\\n"
        f"  git tag -a {version} -m 'Release {version}' && \\\n"
        f"  git push origin main {version}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
