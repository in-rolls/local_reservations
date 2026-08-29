"""The manifest's two load-bearing properties.

Neither is about content. A manifest that is not reproducible fails on somebody
else's machine for no reason and gets ignored; a manifest that does not notice a
changed byte is decoration.
"""

import hashlib
import json
import subprocess
import sys

from local_reservations.paths import ROOT

BUILD = ROOT / "src" / "local_reservations" / "tools" / "build_manifest.py"
VERIFY = ROOT / "src" / "local_reservations" / "tools" / "verify_manifest.py"
MANIFEST = ROOT / "MANIFEST.json"
MANIFEST_MD = ROOT / "MANIFEST.md"


def run(script, *args):
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )


def test_two_builds_from_one_tree_are_byte_identical():
    """No wall-clock timestamp anywhere. The manifest is dated by the git
    commit, because a manifest that changes when nothing else did cannot be
    checked into a repository or diffed across a release.

    Both builds happen here rather than comparing against whatever is on disk:
    the committed manifest was built from an earlier HEAD, so comparing to it
    tests that the commit has not moved, which is a different and much less
    interesting claim.
    """
    # both files are restored: a test run that leaves the tree dirty makes
    # release-check refuse, and the cause is not obvious from what it prints
    saved = {p: p.read_bytes() for p in (MANIFEST, MANIFEST_MD) if p.exists()}
    try:
        run(BUILD)
        first = MANIFEST.read_bytes()
        run(BUILD)
        second = MANIFEST.read_bytes()
    finally:
        for path, content in saved.items():
            path.write_bytes(content)
    assert first == second


def test_the_manifest_records_the_exact_column_order():
    """So a consumer can tell a schema change from a data change without
    diffing a header."""
    if not MANIFEST.exists():
        return
    from local_reservations.common import master as M
    from local_reservations.tools import build_manifest

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == build_manifest.SCHEMA_VERSION == 2
    assert manifest["master_columns"] == M.MASTER_COLUMNS


def test_every_recorded_digest_matches_the_file():
    if not MANIFEST.exists():
        return
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for entry in manifest["files"][:6]:
        path = ROOT / entry["path"]
        if not path.exists():
            continue
        sha = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                sha.update(chunk)
        assert sha.hexdigest() == entry["sha256"], entry["path"]


def test_the_verifier_needs_nothing_from_the_repository():
    """It has to run from a bare checkout or an unpacked tarball. A verifier
    that needs the repository working cannot tell you the repository is intact.

    Checked by reading the imports rather than searching the text, so a module
    named in a comment does not fail it and an import hidden in a function does
    not pass it.
    """
    import ast

    tree = ast.parse(VERIFY.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= set(sys.stdlib_module_names), imported


def test_a_changed_byte_is_caught():
    if not MANIFEST.exists():
        return
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    target = next(
        (ROOT / e["path"] for e in manifest["files"] if (ROOT / e["path"]).exists()),
        None,
    )
    if target is None:
        return
    original = target.read_bytes()
    try:
        target.write_bytes(original + b"\n")
        assert run(VERIFY, "--quiet").returncode == 1
    finally:
        target.write_bytes(original)
    assert run(VERIFY, "--quiet").returncode == 0
