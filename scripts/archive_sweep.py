"""What the web archive holds for every state election commission.

    python3 scripts/archive_sweep.py            # every state
    python3 scripts/archive_sweep.py --only Karnataka

Written because the corpus's largest recent find was an accident. Chasing an
unrelated question, a query against the whole of karsec.gov.in returned 828
archived PDFs including 196 taluk panchayat elected-member gazettes for 2016 -
a tier Karnataka contributes nothing to, naming winners, sitting in a public
archive. Nothing here would have found it: probe_sources.py reads eighteen
hand-picked URLs and none is a commission's site, and ap/harvest.py queries the
archive for one hard-coded path in one state.

So this asks every state the same question and writes the answer down. It
**downloads nothing**; it is an inventory, and its output is the input to a
decision about what is worth harvesting.

The host is derived rather than curated. Commissions name their sites on a few
patterns - karsec.gov.in, sec.gujarat.gov.in, wbsec.gov.in,
mahasec.maharashtra.gov.in - and generating candidates from those resolved seven
of the first eight states tried. Every candidate is recorded, not only the one
that answered: a state reported as holding nothing looks identical to a state
whose domain was guessed wrong, and that difference is the whole value of the
file.
"""

import argparse
import collections
import csv
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "archive_inventory.csv"
HOSTS = ROOT / "data" / "archive_hosts.csv"

COLUMNS = ["state", "host", "pdfs", "first_capture", "last_capture",
           "reservation", "results", "delimitation", "other", "top_directories"]

# Two-letter-ish forms the commissions actually use in their hostnames.
ABBREV = {
    "Andhra Pradesh": "ap", "Arunachal Pradesh": "arunachal", "Assam": "assam",
    "Bihar": "bihar", "Chhattisgarh": "cg", "Goa": "goa", "Gujarat": "gujarat",
    "Haryana": "haryana", "Himachal Pradesh": "hp", "Jammu & Kashmir": "jk",
    "Jharkhand": "jharkhand", "Karnataka": "kar", "Kerala": "kerala",
    "Madhya Pradesh": "mp", "Maharashtra": "maha", "Manipur": "manipur",
    "Meghalaya": "meghalaya", "Mizoram": "mizoram", "Nagaland": "nagaland",
    "Odisha": "odisha", "Puducherry": "py", "Punjab": "punjab",
    "Rajasthan": "raj", "Sikkim": "sikkim", "Tamil Nadu": "tn",
    "Telangana": "tg", "Tripura": "tripura", "Uttar Pradesh": "up",
    "Uttarakhand": "uk", "West Bengal": "wb", "NCT of Delhi": "delhi",
}

# Confirmed by hand, and kept because deriving them every run would re-guess a
# question already answered. Anything not here is derived from ABBREV.
KNOWN = {
    "Karnataka": "karsec.gov.in",
    "Maharashtra": "mahasec.maharashtra.gov.in",
    "Andhra Pradesh": "sec.ap.gov.in",
    "West Bengal": "wbsec.gov.in",
    "Tamil Nadu": "tnsec.tn.gov.in",
    "Madhya Pradesh": "mplocalelection.gov.in",
    # None of these follow the patterns below, and the first sweep reported all
    # three as "nothing archived" - which is what an unresolved host looks like
    # and is why every candidate tried is written to archive_hosts.csv.
    "Haryana": "secharyana.gov.in",
    "Rajasthan": "sec.rajasthan.gov.in",
    "Telangana": "tsec.gov.in",
}


def candidates(state):
    """Hostnames this state's commission might use, most likely first."""
    if state in KNOWN:
        yield KNOWN[state]
    short = ABBREV.get(state, state.split()[0].lower())
    slug = state.lower().replace(" ", "").replace("&", "")
    yield f"{short}sec.gov.in"
    yield f"sec.{slug}.gov.in"
    yield f"{slug}sec.gov.in"
    yield f"sec.{short}.gov.in"
    yield f"{short}sec.nic.in"


def cdx(host, prefix=True, limit=5000, tries=3):
    """Archived URLs for a host. [] where the archive holds none."""
    query = urllib.parse.quote(host + "/" if prefix else host, safe=":/")
    url = (f"http://web.archive.org/cdx/search/cdx?url={query}&limit={limit}"
           f"&fl=original,timestamp&collapse=urlkey&output=json"
           f"&matchType={'prefix' if prefix else 'domain'}")
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=180) as response:
                rows = json.loads(response.read().decode("utf-8", "replace")
                                  or "[]")
            return rows[1:] if rows else []
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            # The CDX API rate-limits rather than refusing, so a failure here is
            # usually "slow down" and not "no such host".
            time.sleep(3 * (attempt + 1))
    return []


def resolve(state):
    """The first candidate host the archive has anything for, and all tried."""
    tried = []
    for host in candidates(state):
        tried.append(host)
        if cdx(host, prefix=False, limit=1):
            return host, tried
    return "", tried


# What a filename says it is. Ordered: a reservation gazette for an elected-
# members list is still an elected-members list, and "form" matches too much to
# be trusted before the specific words.
KIND = [
    ("results", r"elected|winner|result|form.?21|form.?25|declaration"),
    ("reservation", r"reserv|roster|rotation|aarakshan|আসন"),
    ("delimitation", r"delimit|ward.?format|boundary"),
]


def classify(url):
    name = urllib.parse.unquote(url).lower()
    for kind, pattern in KIND:
        if re.search(pattern, name):
            return kind
    return "other"


def sweep(state):
    host, tried = resolve(state)
    if not host:
        return None, tried
    rows = [r for r in cdx(host) if r and r[0].lower().endswith(".pdf")]
    kinds = collections.Counter(classify(u) for u, _ in rows)
    stamps = sorted(t for _, t in rows if t)
    directories = collections.Counter(
        "/".join(urllib.parse.unquote(u).split("/")[3:-1])[:44] for u, _ in rows)
    return {
        "state": state, "host": host, "pdfs": len(rows),
        "first_capture": stamps[0][:6] if stamps else "",
        "last_capture": stamps[-1][:6] if stamps else "",
        "reservation": kinds["reservation"], "results": kinds["results"],
        "delimitation": kinds["delimitation"], "other": kinds["other"],
        "top_directories": " | ".join(
            f"{d}({n})" for d, n in directories.most_common(3) if d),
    }, tried


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", help="one state")
    args = ap.parse_args()

    states = [args.only] if args.only else sorted(ABBREV)
    found, attempts = [], []
    for state in states:
        row, tried = sweep(state)
        attempts.append({"state": state, "resolved": row["host"] if row else "",
                         "candidates_tried": " ".join(tried)})
        if row:
            found.append(row)
            print(f"  {state:<20} {row['host']:<30} {row['pdfs']:>5} PDFs  "
                  f"res={row['reservation']:<4} res_out={row['results']:<4}",
                  flush=True)
        else:
            print(f"  {state:<20} {'-':<30} nothing archived under "
                  f"{len(tried)} candidate host(s)", flush=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore",
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted(found, key=lambda r: -r["pdfs"]))
    with HOSTS.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, lineterminator="\n",
                                fieldnames=["state", "resolved",
                                            "candidates_tried"])
        writer.writeheader()
        writer.writerows(attempts)
    print(f"\n{len(found)} of {len(states)} states resolved -> "
          f"{OUT.relative_to(ROOT)}")
    print(f"every candidate tried -> {HOSTS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
