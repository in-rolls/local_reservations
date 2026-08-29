"""Check a checkout against MANIFEST.json.

Standard library only, and it imports nothing from scripts/common on purpose:
it has to run from a bare checkout, an unpacked release tarball, or a machine
where nothing else in this repository works. A verifier that needs the
repository to be in working order cannot tell you the repository is intact.

    uv run python -m local_reservations.tools.verify_manifest            # exit 0 if
    every file matches
    uv run python -m local_reservations.tools.verify_manifest --quiet    # only
    report failures
"""

import argparse
import hashlib
import json
import pathlib
import sys

# The one module that does not import local_reservations.paths, and the only
# place in the repository where duplicating that computation is correct. This
# script has to run from a bare checkout or an unpacked tarball, with nothing
# installed and no package importable - that is the promise the readme makes
# about it, and there is a test asserting it imports nothing but the standard
# library. Importing the package to find the repository root would quietly
# break exactly the case this exists for.
ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent

MANIFEST = ROOT / "MANIFEST.json"


def digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            sha.update(chunk)
    return sha.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if not MANIFEST.exists():
        print(f"no manifest at {MANIFEST}")
        return 2
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    missing, changed, ok = [], [], 0
    for entry in manifest.get("files", []):
        path = ROOT / entry["path"]
        if not path.exists():
            missing.append(entry["path"])
            continue
        if digest(path) != entry["sha256"]:
            changed.append(entry["path"])
            continue
        ok += 1

    release = manifest.get("release") or "(untagged)"
    print(
        f"manifest {release}, schema version "
        f"{manifest.get('schema_version')}, built from "
        f"{manifest.get('built_from_commit', '')[:12]}"
    )
    if manifest.get("dirty"):
        print("  WARNING: built from a tree with uncommitted changes")
    for sibling in manifest.get("sibling_repos", []):
        if sibling.get("dirty"):
            print(f"  WARNING: {sibling['repo']} was dirty when read")

    if not args.quiet or missing or changed:
        print(f"  {ok} file(s) match")
    for path in missing:
        print(f"  MISSING  {path}")
    for path in changed:
        print(f"  CHANGED  {path}")

    if missing or changed:
        print(f"\nFAILED: {len(missing)} missing, {len(changed)} changed")
        return 1
    print("\nOK: every file matches the manifest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
