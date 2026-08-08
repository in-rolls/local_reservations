"""Haryana, from local_elections_haryana.

The closest of the siblings to the pooled schema: caste and gender are already
separate orthogonal columns, and district, block, gram_panchayat and ward_no are
all present under those names. What is missing is what the repository's layout
encodes rather than states - the year lives in a directory name and the tier in
a filename.

Two things worth naming:

`BC_A` is not a spelling of `BC`. Haryana reserves panchayat seats for Block A
of the Backward Classes list only, so the local label is finer than the pooled
one and both are kept. 12,515 rows carry it.

There is no `source_page`. The parser recorded which notification each row came
from but not the page within it, so provenance_level is `document`: a row can be
traced to a PDF and not to a page. That is recoverable by re-parsing and is on
the worklist rather than papered over.
"""

import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from normalize import label  # noqa: E402

REPO = "local_elections_haryana"
URL = "https://github.com/in-rolls/local_elections_haryana"
STATE = "Haryana"

# filename stem -> canonical office
TIERS = {"gp_reservation": ("gp_head", "sarpanch"),
         "ward_reservation": ("gp_ward", "ward")}

# What the sibling's committed files hold. A mismatch means the sibling moved
# under us, and silently pooling a different number of rows is exactly the
# failure this repository keeps meeting.
DECLARED = {
    ("2016", "gp_head"): 6079, ("2016", "gp_ward"): 61618,
    ("2022", "gp_head"): 6159, ("2022", "gp_ward"): 61362,
}


def slices(root):
    root = pathlib.Path(root)
    for year_dir in sorted(p for p in (root / "data").iterdir() if p.is_dir()):
        year = year_dir.name
        if not year.isdigit():
            continue
        for stem, (tier, tier_local) in sorted(TIERS.items()):
            path = year_dir / f"{stem}.csv"
            if not path.exists():
                continue
            with path.open(encoding="utf-8", errors="replace") as fh:
                rows = [convert(r, year, tier, tier_local, path, root)
                        for r in csv.DictReader(fh)]
            expected = DECLARED.get((year, tier))
            if expected is not None and len(rows) != expected:
                raise SystemExit(
                    f"{REPO}: {year}/{tier} holds {len(rows):,} rows, "
                    f"{expected:,} declared - the sibling changed")
            yield {
                "dataset_id": f"haryana/{tier}/{year}",
                "state": STATE, "rows": rows,
                # the parser kept the notification but not the page within it
                "provenance_level": "document",
                "unit_of_observation": "seat",
            }


def convert(row, year, tier, tier_local, path, root):
    local = row.get("caste_reservation", "")
    return {
        "state": STATE, "year": year, "tier": tier, "tier_local": tier_local,
        "district": row.get("district", ""), "block": row.get("block", ""),
        "gram_panchayat": row.get("gram_panchayat", ""),
        "ward_no": row.get("ward_no", ""),
        # Block A of the Backward Classes list, which is not the same set as
        # another state's BC - the fold is kept reversible
        "caste_reservation": "BC" if local == "BC_A" else local,
        "caste_reservation_local": local,
        "woman_reserved": row.get("woman_reserved", ""),
        # Rebuilt from the pooled category, not carried across. Haryana prints
        # "BC-A Other than Woman" against a caste_reservation of BC, so the
        # label as printed disagrees with the two fields it is meant to
        # summarise - 12,521 rows of it. The printed form survives in
        # reservation_raw and caste_reservation_local.
        "reservation": label("BC" if local == "BC_A" else local,
                             str(row.get("woman_reserved")) == "1"),
        "reservation_raw": row.get("reservation_raw", ""),
        "winner": row.get("winner", ""), "winner_basis": "published",
        "vacant": row.get("vacant", ""), "unopposed": row.get("unopposed", ""),
        "script": row.get("script", "latin"),
        "printings_agree": row.get("printings_agree", ""),
        "source_path": str((path.parent / "pdfs" /
                            row.get("source_pdf", "")).relative_to(root)),
        "source_page": "",
    }
