"""Where the repository is, worked out once.

Forty-two modules each computed this for themselves, as
``pathlib.Path(__file__).resolve().parent.parent`` or ``.parent.parent.parent``
depending on how deep they sat. That is duplication with teeth: the count is a
silent assertion about directory depth, so moving a file two levels changes
where it thinks ``data/`` is, and nothing fails loudly - it just resolves to a
directory that does not exist, or worse, one that does.

Found by walking up for the marker rather than by counting, so it survives the
next move as well as this one.
"""

import pathlib

_MARKERS = ("pyproject.toml", "data")


def _find_root(start):
    for directory in [start, *start.parents]:
        if all((directory / marker).exists() for marker in _MARKERS):
            return directory
    raise RuntimeError(
        f"no repository root above {start}: looked for {_MARKERS}")


ROOT = _find_root(pathlib.Path(__file__).resolve())
DATA = ROOT / "data"
