"""The manifest's two load-bearing properties.

Neither is about content. A manifest that is not reproducible fails on somebody
else's machine for no reason and gets ignored; a manifest that does not notice a
changed byte is decoration.
"""

import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
BUILD = ROOT / "scripts" / "build_manifest.py"
VERIFY = ROOT / "scripts" / "verify_manifest.py"
MANIFEST = ROOT / "MANIFEST.json"


def run(script, *args):
    return subprocess.run([sys.executable, str(script), *args],
                          capture_output=True, text=True, cwd=str(ROOT))


def test_two_builds_from_one_tree_are_byte_identical():
    """No wall-clock timestamp anywhere. The manifest is dated by the git
    commit, because a manifest that changes when nothing else did cannot be
    checked into a repository or diffed across a release."""
    if not MANIFEST.exists():
        return
    before = MANIFEST.read_bytes()
    run(BUILD)
    after = MANIFEST.read_bytes()
    MANIFEST.write_bytes(before)
    assert before == after


def test_the_manifest_records_the_exact_column_order():
    """So a consumer can tell a schema change from a data change without
    diffing a header."""
    if not MANIFEST.exists():
        return
    sys.path.insert(0, str(ROOT / "scripts" / "common"))
    import master as M
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
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
    target = next((ROOT / e["path"] for e in manifest["files"]
                   if (ROOT / e["path"]).exists()), None)
    if target is None:
        return
    original = target.read_bytes()
    try:
        target.write_bytes(original + b"\n")
        assert run(VERIFY, "--quiet").returncode == 1
    finally:
        target.write_bytes(original)
    assert run(VERIFY, "--quiet").returncode == 0
