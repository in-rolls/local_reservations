"""Parse Andhra Pradesh gram panchayat reservation, 2020.

One gazette per district. Pages 10 onward hold "Details of Reservations for the
Office of Sarpanches & Ward Members", one line per gram panchayat:

    44 Alamuru ALAMURU sc(w) t4 Bc (w) UR (W) SC sc (w) BC UR (W) UR ...
    |  |       |       |     |  |
    |  mandal  GP      |     |  the wards, one category each
    |                  |     number of wards
    serial             the sarpanch's own reservation

Two things make this the hardest state in the repo:

**The text layer is OCR output, and it is wrong in places.** `5C` for SC, `8c`
for BC, `t4` for 14, `72` for 12, `UR {W)` with a brace. The category vocabulary
is closed - UR, SC, ST, BC, each optionally "(W)" - so the damage is repairable,
but a repair that is wrong looks exactly like one that is right. Every row
therefore carries `ocr_repaired`, counting how many of its cells had to be
mended, so the doubtful rows can be found again.

**There are no ruled tables**, so the line is read positionally. The mandal and
the gram panchayat are separated only by case: the mandal is Title Case and the
gram panchayat is UPPERCASE.

Writes data/ap/{sarpanch,ward}_reservation_2020.{csv,jsonl}.
"""

import argparse
import collections
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "common"))
import emit  # noqa: E402
from normalize import label, normalize_reservation  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
AP = ROOT / "data" / "ap" / "2020_res_gp"

COLUMNS = ["state", "year", "district", "block", "gram_panchayat", "ward_no",
           "tier", "reservation", "caste_reservation", "woman_reserved",
           "ward_count", "ocr_repaired", "reservation_raw", "script"]

# District codes in the filenames.
DISTRICTS = {
    "atp": "Anantapur", "est": "East Godavari", "kri": "Krishna",
    "nlr": "Nellore", "pkm": "Prakasam", "wst": "West Godavari",
    "kdp": "Kadapa", "ctr": "Chittoor", "gnt": "Guntur", "srk": "Srikakulam",
    "vsp": "Visakhapatnam", "vzm": "Vizianagaram", "krl": "Kurnool",
}

# A reservation token, tolerant of the OCR substitutions actually observed:
# S<->5, B<->8, and the bracket around "W" appearing as ( { [ or mismatched.
CATEGORY = re.compile(
    r"(?<![A-Za-z0-9])(?:[Uu][Rr]|[Ss5][CcTt]|[Bb8][Cc]|[Gg][Nn])"
    r"\s*(?:[({\[]\s*[WwVv]\s*[)}\]]?)?",
    re.X)

# a ward count, with the digit confusions this OCR makes: l/I->1, t->1, O->0
COUNT = re.compile(r"^[0-9tTlIiOo]{1,3}$")

CANONICAL = {"5": "S", "8": "B", "0": "O"}


def repair(token):
    """Return (clean token, was_repaired). Only the closed category vocabulary
    is repaired - never a name, where a wrong guess would be undetectable."""
    original = token
    fixed = re.sub(r"\s+", " ", token).strip()
    fixed = "".join(CANONICAL.get(c, c) for c in fixed)
    fixed = fixed.replace("{", "(").replace("[", "(").replace("}", ")").replace("]", ")")
    if "(" in fixed and ")" not in fixed:
        fixed += ")"
    return fixed, fixed.upper().replace(" ", "") != original.upper().replace(" ", "")


def digits(token):
    """A ward count as OCR left it: "t4" is 14, "72" is 12 in this font."""
    mapped = token.translate(str.maketrans("tTlIiOo", "1110000"))
    return mapped if mapped.isdigit() else ""


def parse_line(line):
    """Split one gram panchayat line, or return None if it is not one."""
    line = re.sub(r"\s+", " ", line).strip()
    # the serial itself is OCR-damaged in places ("4a" for 48)
    head = re.match(r"^(\d{1,4}[A-Za-z]?)\s+(.*)$", line)
    if not head:
        return None
    rest = head.group(2)

    matches = list(CATEGORY.finditer(rest))
    if not matches:
        return None
    first = matches[0]

    names = rest[:first.start()].strip()
    if not names:
        return None
    # mandal is Title Case, gram panchayat is UPPERCASE - the only separator
    words = names.split()
    upper_from = next((i for i, w in enumerate(words)
                       if w.isupper() and len(w) > 2), len(words))
    mandal = " ".join(words[:upper_from]).strip()
    panchayat = " ".join(words[upper_from:]).strip() or mandal

    tail = rest[first.end():].strip()
    count_token = tail.split(" ")[0] if tail else ""
    ward_count = digits(count_token) if COUNT.match(count_token or "") else ""

    wards = [m.group(0) for m in matches[1:]]
    return {
        "serial": head.group(1), "mandal": mandal, "panchayat": panchayat,
        "sarpanch_raw": first.group(0), "ward_count": ward_count,
        "ward_raws": wards,
    }


def _records(lines):
    """Reassemble gram panchayat records that the layout split across lines.

    A long ward list wraps, so a record often arrives as

        53 Alamuru MOOLASTANAM
        8C
        5C sc (w) UR

    Reading line by line finds the first fragment, fails to see any category on
    it, and drops the panchayat entirely - which is how East Godavari came out
    at 748 of its 1,103 gram panchayats. So a line that opens a record is held
    open and the continuation lines are appended until the next record starts.
    """
    opener = re.compile(r"^\s*\d{1,4}[A-Za-z]?\s+[A-Za-z]")
    buffer = ""
    for raw in lines:
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        if opener.match(line):
            if buffer:
                yield buffer
            buffer = line
        elif buffer:
            buffer = f"{buffer} {line}"
    if buffer:
        yield buffer


def parse_pdf(path):
    district = DISTRICTS.get(path.stem.split("_")[0], path.stem)
    text = subprocess.run(["pdftotext", "-layout", str(path), "-"],
                          capture_output=True, text=True).stdout
    rows = []
    for page_no, page in enumerate(text.split("\f"), 1):
        if "RESERVATION" not in page.upper():
            continue
        for line in _records(page.split("\n")):
            parsed = parse_line(line)
            if not parsed:
                continue
            fixed, repaired = repair(parsed["sarpanch_raw"])
            got = normalize_reservation(fixed)
            if not got:
                continue
            caste, woman, script = got
            base = {
                "state": "Andhra Pradesh", "year": "2020",
                "district": district, "block": parsed["mandal"],
                "gram_panchayat": parsed["panchayat"],
                "ward_count": parsed["ward_count"], "script": script,
            }
            rows.append(emit.stamp(dict(
                base, ward_no="", tier="sarpanch",
                reservation=label(caste, woman), caste_reservation=caste,
                woman_reserved=woman, ocr_repaired=int(repaired),
                reservation_raw=parsed["sarpanch_raw"],
            ), path, page_no, ROOT))

            for index, raw in enumerate(parsed["ward_raws"], 1):
                fixed, repaired = repair(raw)
                got = normalize_reservation(fixed)
                if not got:
                    continue
                caste, woman, script = got
                rows.append(emit.stamp(dict(
                    base, ward_no=str(index), tier="ward",
                    reservation=label(caste, woman), caste_reservation=caste,
                    woman_reserved=woman, ocr_repaired=int(repaired),
                    reservation_raw=raw, script=script,
                ), path, page_no, ROOT))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    rows = []
    files = sorted(AP.glob("*.pdf"))[: args.limit]
    for path in files:
        got = parse_pdf(path)
        rows += got
        print(f"  {path.name:20s} {len(got):6d} rows", file=sys.stderr)

    by_tier = collections.defaultdict(list)
    for row in rows:
        by_tier[row["tier"]].append(row)

    for tier in sorted(by_tier):
        subset = by_tier[tier]
        stem = ROOT / "data" / "ap" / f"{tier}_reservation_2020"
        csv_path, _ = emit.write(subset, stem, COLUMNS)
        women = sum(r["woman_reserved"] for r in subset)
        repaired = sum(r["ocr_repaired"] for r in subset)
        districts = {r["district"] for r in subset}
        print(f"{tier:9s} {len(subset):6d} seats  {len(districts)} districts  "
              f"women {women / max(len(subset), 1) * 100:4.1f}%  "
              f"ocr-repaired {repaired / max(len(subset), 1) * 100:4.1f}%  "
              f"-> {csv_path.name}")

    print("\nsarpanch reservation split:")
    total = max(len(by_tier["sarpanch"]), 1)
    for k, v in collections.Counter(r["reservation"]
                                    for r in by_tier["sarpanch"]).most_common():
        print(f"   {v:6d}  {v / total * 100:5.1f}%  {k}")


if __name__ == "__main__":
    main()
