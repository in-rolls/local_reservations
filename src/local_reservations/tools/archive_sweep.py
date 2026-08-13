"""What the web archive holds for every state election commission.

    uv run python -m local_reservations.tools.archive_sweep.py            # every state
    uv run python -m local_reservations.tools.archive_sweep.py --only Karnataka

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
import urllib.parse

from local_reservations.common import fetch
from local_reservations.paths import ROOT

OUT = ROOT / "data" / "archive_inventory.csv"
HOSTS = ROOT / "data" / "archive_hosts.csv"

COLUMNS = ["state", "host", "pdfs", "first_capture", "last_capture",
           "reservation", "results", "delimitation", "other",
           "top_directories", "status"]

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


def cdx(host, prefix=True, limit=5000):
    """Archived URLs for a host. [] where the archive holds none, None where
    the question could not be asked.

    The distinction is the whole point. A run that folded a rate-limited query
    into [] reported Gujarat at 0 PDFs, Odisha at 0 and Jharkhand at 0, having
    found 614, 817 and 6 an hour earlier - and printed all three in the same
    words it uses for a state with no web presence. An empty answer and an
    unanswered question are not the same fact and must not share a value.

    The pacing, the retries and the reading of Retry-After all live in
    common/fetch.py, because the archive firewalls an IP for an hour if 429s
    are ignored for a minute and a per-script sleep loop cannot be trusted with
    that.
    """
    query = urllib.parse.quote(host + "/" if prefix else host, safe=":/")
    url = (f"http://web.archive.org/cdx/search/cdx?url={query}&limit={limit}"
           f"&fl=original,timestamp&collapse=urlkey&output=json"
           f"&matchType={'prefix' if prefix else 'domain'}")
    try:
        body = fetch.body(url, timeout=180).decode("utf-8", "replace")
    except fetch.Unanswered:
        return None
    try:
        rows = json.loads(body or "[]")
    except json.JSONDecodeError:
        # a truncated or HTML body is the archive failing to answer, not the
        # archive answering "nothing"
        return None
    return rows[1:] if rows else []


def resolve(state):
    """The first candidate host with anything archived, every candidate tried,
    and whether any query failed - a host is only "not found" if every
    candidate was actually asked."""
    tried, failed = [], False
    for host in candidates(state):
        tried.append(host)
        rows = cdx(host, prefix=False, limit=1)
        if rows is None:
            failed = True
        elif rows:
            return host, tried, False
    return "", tried, failed


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
    """(row, candidates tried, status). row is None unless status is "ok"."""
    host, tried, failed = resolve(state)
    if not host:
        return None, tried, "query failed" if failed else "no host"
    listing = cdx(host)
    if listing is None:
        return None, tried, "query failed"
    rows = [r for r in listing if r and r[0].lower().endswith(".pdf")]
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
        "status": "ok",
    }, tried, "ok"


def previous():
    """What the last run recorded, by state, so a failed query can carry the
    answer forward instead of overwriting it with a worse one."""
    if not OUT.exists():
        return {}
    with OUT.open(encoding="utf-8") as fh:
        return {r["state"]: r for r in csv.DictReader(fh)}


def main():
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--only", help="one state")
    args = ap.parse_args()

    states = [args.only] if args.only else sorted(ABBREV)
    prior = previous()
    found, attempts = [], []
    for state in states:
        row, tried, status = sweep(state)
        if row:
            found.append(row)
            print(f"  {state:<20} {row['host']:<30} {row['pdfs']:>5} PDFs  "
                  f"res={row['reservation']:<4} res_out={row['results']:<4}",
                  flush=True)
        elif status == "query failed" and state in prior:
            row = dict(prior[state], status="carried forward")
            found.append(row)
            print(f"  {state:<20} {row['host']:<30} {row['pdfs']:>5} PDFs  "
                  "(carried forward - the archive did not answer)",
                  flush=True)
        elif status == "query failed":
            print(f"  {state:<20} {'?':<30} the archive did not answer, and "
                  f"there is no earlier number to carry", flush=True)
        else:
            print(f"  {state:<20} {'-':<30} nothing archived under "
                  f"{len(tried)} candidate host(s)", flush=True)
        attempts.append({
            "state": state, "resolved": row["host"] if row else "",
            "status": row["status"] if row else status,
            "candidates_tried": " ".join(tried)})

    # --only rewrites one state and must not drop the other thirty.
    if args.only:
        kept = [r for s, r in sorted(prior.items()) if s != args.only]
        found = found + [dict(r, status=r.get("status") or "ok") for r in kept]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore",
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted(found, key=lambda r: -int(r["pdfs"])))
    with HOSTS.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, lineterminator="\n",
                                fieldnames=["state", "resolved", "status",
                                            "candidates_tried"])
        writer.writeheader()
        writer.writerows(attempts)
    stale = sum(1 for r in found if r["status"] == "carried forward")
    carried = f"  ({stale} carried forward from an earlier run)" if stale else ""
    print(f"\n{len(found)} states with an archived host -> "
          f"{OUT.relative_to(ROOT)}{carried}")
    print(f"every candidate tried -> {HOSTS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
