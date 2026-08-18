"""Rajasthan, from quota_raj.

Rajasthan's parse sits in quota_raj rather than a local_elections_* repository,
which is the only reason it spent months in this repository's coverage table
filed as "prior work, other schema" - a label that reads as *already handled*
where it meant *parsed, just not by a repository I was looking for*.

Four gram panchayat head cycles, 2005/2010/2015/2020, with caste and gender
already in separate columns. The only real work is reading parquet without
pandas, since this repository is standard library only: the four files are read
through pandas when it is importable and the slice is skipped with a reason when
it is not, rather than silently contributing nothing.

Rajasthan carries no provenance at all - no source document, no page - so
provenance_level is `dataset`. A row can be traced to the file it came from and
no further. That is a real limit on what these rows can be checked against, and
it is recorded rather than left as an empty column that reads like an oversight.
"""

import pathlib

REPO = "quota_raj"
URL = "https://github.com/in-rolls/quota_raj"
STATE = "Rajasthan"

FILES = {
    "2005": "data/raj/source_2005_std.parquet",
    "2010": "data/raj/source_2010_std.parquet",
    "2015": "data/raj/source_2015_std.parquet",
    "2020": "data/raj/source_2020_std.parquet",
}

DECLARED = {"2005": 9178, "2010": 9166, "2015": 9862, "2020": 11314}

# GEN is what Rajasthan prints for an unreserved seat, and OBC for what other
# states print as BC. Both are kept in caste_reservation_local.
CASTE = {"GEN": "NONE", "SC": "SC", "ST": "ST", "OBC": "BC"}


def slices(root):
    try:
        import pandas
    except ImportError:
        print(
            f"  {REPO}: pandas is not importable, so the parquet slices are skipped",
            flush=True,
        )
        return

    root = pathlib.Path(root)
    for year, relative in sorted(FILES.items()):
        path = root / relative
        if not path.exists():
            continue
        frame = pandas.read_parquet(path)
        expected = DECLARED.get(year)
        if expected is not None and len(frame) != expected:
            raise SystemExit(
                f"{REPO}: {year} holds {len(frame):,} rows, {expected:,} "
                f"declared - the sibling changed"
            )
        rows = [convert(record, year, relative) for record in frame.to_dict("records")]
        yield {
            "dataset_id": f"rajasthan/gp_head/{year}",
            "state": STATE,
            "rows": rows,
            # no source document or page is recorded anywhere in the sibling
            "provenance_level": "dataset",
            "unit_of_observation": "seat",
        }


def label(caste, woman):
    prefix = {"SC": "SC", "ST": "ST", "BC": "BC"}.get(caste, "")
    return f"{prefix} {'Woman' if woman else 'Other than Woman'}".strip()


def blank(value):
    return "" if value is None or str(value) in ("nan", "None") else str(value)


def convert(record, year, relative):
    local = blank(record.get("caste_category")).upper()
    caste = CASTE.get(local, "NONE")
    woman = 1 if str(record.get("female_reserved")) in ("1", "1.0", "True") else 0
    return {
        "state": STATE,
        "year": year,
        "tier": "gp_head",
        "tier_local": "sarpanch",
        "district": blank(record.get("district_raw")),
        # samiti is the panchayat samiti, which is Rajasthan's block
        "block": blank(record.get("samiti_raw")),
        "gram_panchayat": blank(record.get("gp_std") or record.get("gp_raw")),
        "ward_no": "",
        "caste_reservation": caste,
        "caste_reservation_local": local or "NONE",
        "woman_reserved": woman,
        "reservation": label(caste, woman),
        "reservation_raw": blank(record.get("reservation_raw")),
        "winner": blank(record.get("winner_name")),
        "winner_basis": "published" if blank(record.get("winner_name")) else "",
        "script": "latin",
        "source_path": relative,
        "source_page": "",
    }
