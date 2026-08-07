"""Write parsed rows out, with provenance attached to every row.

Two formats, same content:

  <stem>.csv    flat, for anyone who wants to open it in a spreadsheet or R
  <stem>.jsonl  one JSON object per line, which survives added columns without
                breaking readers and keeps types

Every row carries where it came from - the source PDF's path relative to the
repo, and the page it was read from. The source PDFs are committed alongside,
so any row can be checked against the page it was parsed from without a network
round trip. That mattered repeatedly while building these: nearly every parser
bug in this repo produced plausible wrong values rather than an error, and the
only way to settle it was to open the page.
"""

import csv
import json
import pathlib
import re

PROVENANCE = ["source_path", "source_page", "source_pdf"]

# Phrases that are table headers, not places. A header row that survives into
# the data is invisible in a row count and only shows up as a duplicate key -
# Goa carried three rows for a panchayat called "Name of the Panchayat", and
# J&K 2018 a district called "Name of District".
HEADER_TEXT = {
    "name of the panchayat", "name of panchayat", "name of the taluka",
    "name of district", "name of the district", "district name",
    "name of block", "name of the block", "block name", "name of halqa",
    "name of the halqa", "panchayat name", "grampanchayat", "gram panchayat",
    "name of the grampanchayat", "number & name of panch constituencies",
    "name of the mandal", "mandal",
}


# Enumerating header phrases one at a time does not converge - the list grew
# through "Name of the Panchayat", "Name of District" and then "Name of Number"
# as each new source was parsed. These are all the same shape: a column caption
# describing what the column holds, never a place.
HEADER_SHAPE = re.compile(
    r"^\s*(?:sl\.?|sr\.?|s\.?\s*no\.?|no\.?|number|name|names)\b"
    r"|^\s*(?:the\s+)?name\s+of\b"
    r"|\bname\s+of\s+(?:the\s+)?(?:district|block|panchayat|halqa|taluka|"
    r"mandal|number|ward|constituenc\w*)\b",
    re.I)


def is_header_text(value):
    text = (value or "").strip()
    if not text:
        return False
    return text.lower() in HEADER_TEXT or bool(HEADER_SHAPE.match(text))


def stamp(row, path, page=None, root=None):
    """Attach provenance to a row. `path` is the source document."""
    path = pathlib.Path(path)
    root = pathlib.Path(root) if root else None
    try:
        relative = path.relative_to(root) if root else path
    except ValueError:
        relative = path
    row["source_path"] = str(relative)
    row["source_pdf"] = path.name
    if page is not None:
        row["source_page"] = page
    return row


def write(rows, stem, columns):
    """Write rows to <stem>.csv and <stem>.jsonl. Returns the two paths."""
    stem = pathlib.Path(stem)
    columns = list(columns) + [c for c in PROVENANCE if c not in columns]

    csv_path = stem.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore",
                                lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in columns})

    jsonl_path = stem.with_suffix(".jsonl")
    with jsonl_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps({c: row.get(c, "") for c in columns},
                                ensure_ascii=False) + "\n")

    return csv_path, jsonl_path
