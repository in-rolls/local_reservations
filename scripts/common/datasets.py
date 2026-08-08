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

import csv
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"

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
    """Yield (path, rows) for every parsed dataset that has rows."""
    for path in paths(exclude):
        rows = read(path)
        if rows:
            yield path, rows
