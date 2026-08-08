"""Find the parsed datasets. One implementation, deliberately.

Four modules independently globbed `data/*/*.csv` and decided what counted as a
parsed dataset by testing for the schema columns: build_coverage.parsed_datasets,
build_coverage.datasets, expectations.datasets and
build_state_readmes.dataset_files. Four copies of a rule is four chances for one
of them to disagree, and the pooled master is about to write files that match
that rule exactly - `data/master/master_haryana.csv` carries every schema column
by construction, so each of those globs would have reported it as a state called
"Master" and counted every row twice.

Directories that hold derived output rather than a state's parse are excluded
here, in one place.
"""

import collections
import csv
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"

sys.path.insert(0, str(ROOT / "scripts"))
import master  # noqa: E402

# A parsed dataset is one carrying these columns. Filenames are not evidence -
# Jharkhand's filenames name the wrong tier.
REQUIRED = {"state", "year", "tier", "reservation", "caste_reservation"}

# Derived output, not a state. These match REQUIRED by construction.
DERIVED = {"master", "stats"}


def state_directories(exclude=DERIVED):
    return sorted(p for p in DATA.iterdir()
                  if p.is_dir() and p.name not in exclude)


def paths(exclude=DERIVED):
    """Every CSV under data/<state>/ that carries the schema."""
    for directory in state_directories(exclude):
        for path in sorted(directory.glob("*.csv")):
            with path.open(encoding="utf-8", errors="replace") as fh:
                header = next(csv.reader(fh), [])
            if REQUIRED <= set(header):
                yield path


def read(path):
    with path.open(encoding="utf-8", errors="replace") as fh:
        return list(csv.DictReader(fh))


def parsed(exclude=DERIVED):
    """Yield (path, rows) for every parsed dataset that has rows.

    This repository's own parses only. Kept as it is because the per-state
    readmes and the coverage table are about what lives in data/<state>/.
    """
    for path in paths(exclude):
        rows = read(path)
        if rows:
            yield path, rows


def pooled():
    """Every row in the pooled master, this repository's and its siblings'.

    The checks and the worklist read this rather than parsed(), because
    otherwise they cannot see a single sibling row. Two thirds of the master
    comes from adapters, and a worklist that says "generated from the rows and
    cannot go stale" while being blind to most of the rows is worse than one
    that admits its scope: it reports a small number of problems and reads as
    though that is all there are.

    Yields (dataset_id, rows) rather than (path, rows) - a pooled slice has no
    single file behind it, and pretending otherwise is what would make
    provenance checks resolve against the wrong root.
    """
    import build_master              # noqa: PLC0415 - avoids a circular import
    grouped = collections.defaultdict(list)
    for slice_ in list(build_master.local_slices()) + \
            list(build_master.sibling_slices()):
        for row in slice_["rows"]:
            got = master.to_master(
                row, slice_["dataset_id"], slice_["source_repo"],
                slice_["source_commit"], slice_["provenance_level"],
                slice_.get("unit_of_observation", "seat"),
                row.get("seat_candidates", ""))
            if got is not None:
                grouped[slice_["dataset_id"]].append(got)
    for dataset_id, rows in sorted(grouped.items()):
        yield dataset_id, rows
