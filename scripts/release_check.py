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
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else ""
    manifest = json.loads((ROOT / "MANIFEST.json").read_text(encoding="utf-8"))

    problems = []
    if manifest.get("dirty"):
        problems.append("this repository has uncommitted changes")
    for sibling in manifest.get("sibling_repos", []):
        if sibling.get("dirty"):
            problems.append(f"{sibling['repo']} has uncommitted changes")
        if not sibling.get("present"):
            problems.append(f"{sibling['repo']} is not checked out, so its "
                            f"state is missing from this release")

    print()
    if problems:
        print("Not ready to tag:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    rows = manifest["totals"].get("master_rows", 0)
    states = len({s for f in manifest["files"]
                  for s in f.get("states", []) if f.get("kind") == "master"})
    print(f"Ready to tag: {rows:,} pooled seats across {states} states, "
          f"{len(manifest['files'])} files pinned.")
    if not version:
        print("\nRe-run with a version to get the command:"
              "\n  make release-check VERSION=v0.1.0")
        return 0
    print(f"\nRun this yourself - a tag cannot be taken back:\n"
          f"  python3 scripts/build_manifest.py --release {version} && \\\n"
          f"  git add MANIFEST.json MANIFEST.md && \\\n"
          f"  git commit -m 'Release {version}' && \\\n"
          f"  git tag -a {version} -m 'Release {version}' && \\\n"
          f"  git push origin main {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
