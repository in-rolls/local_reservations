"""Fetch Andhra Pradesh's gram panchayat reservation gazettes from the archive.

sec.ap.gov.in refuses connections from outside India, so the eight districts we
do not hold sat on the worklist as blocked. The Wayback Machine crawled the site
in December 2022 and serves it from anywhere, which turns "needs an India
egress" into "needs a URL" for whatever it happened to capture.

It captured six of the thirteen `*_res_gp.pdf` files. Five are the ones already
here; the sixth is West Godavari, which is not. The other seven districts were
never crawled, and no amount of trying changes that - the honest outcome is one
district recovered and seven still blocked.

Downloads are checked against the copies already on disk, so a fetch that
returns something different from what we have is a finding rather than a silent
overwrite. Writes data/ap/2020_res_gp/ and appends to its manifest.
"""

import argparse
import csv
import hashlib
import sys
import urllib.request

from local_reservations.paths import ROOT

OUT = ROOT / "data" / "ap" / "2020_res_gp"
MANIFEST = OUT / "manifest.csv"

CDX = (
    "http://web.archive.org/cdx/search/cdx?url=sec.ap.gov.in/Documents/"
    "Notifications/SP_and_WM*&limit=500&fl=original,timestamp"
    "&collapse=urlkey&filter=original:.*res_gp.*"
)

# id -> the district it names, for the codes the archive uses
DISTRICTS = {
    "atp": "Anantapur",
    "est": "East Godavari",
    "kri": "Krishna",
    "nlr": "Nellore",
    "pkm": "Prakasam",
    "wg": "West Godavari",
}


def archived():
    """(url, timestamp) for every reservation gazette the archive holds."""
    with urllib.request.urlopen(CDX, timeout=120) as response:
        text = response.read().decode("utf-8", "replace")
    out = []
    for line in text.strip().split("\n"):
        if not line.strip():
            continue
        url, timestamp = line.split()[:2]
        out.append((url, timestamp))
    return out


def fetch(url, timestamp):
    # id_ asks the archive for the bytes as crawled, without its own banner
    wayback = f"http://web.archive.org/web/{timestamp}id_/{url}"
    request = urllib.request.Request(wayback, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    rows, fetched, matched, differed = [], 0, 0, []
    for url, timestamp in sorted(archived()):
        name = url.rsplit("/", 1)[-1]
        code = name.split("_")[0]
        target = OUT / name
        print(f"  {name:20} {DISTRICTS.get(code, '?'):16}", end="")
        if args.dry_run:
            print(" (dry run)")
            continue
        try:
            body = fetch(url, timestamp)
        except Exception as exc:
            print(f" FAILED {type(exc).__name__}")
            continue
        digest = hashlib.sha256(body).hexdigest()
        if target.exists():
            # A copy already here is the check on the archive's copy: if the
            # bytes differ, one of the two is not what we think it is.
            if hashlib.sha256(target.read_bytes()).hexdigest() == digest:
                matched += 1
                print(" already held, bytes identical")
            else:
                differed.append(name)
                print(" already held, BYTES DIFFER - not overwritten")
        else:
            target.write_bytes(body)
            fetched += 1
            print(f" fetched {len(body):,} bytes")
        rows.append(
            {
                "file": name,
                "district": DISTRICTS.get(code, ""),
                "url": url,
                "wayback_timestamp": timestamp,
                "sha256": digest,
                "bytes": len(body),
            }
        )

    if rows and not args.dry_run:
        with MANIFEST.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "file",
                    "district",
                    "url",
                    "wayback_timestamp",
                    "sha256",
                    "bytes",
                ],
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(sorted(rows, key=lambda r: r["file"]))

    print(f"\n{fetched} new, {matched} already held and identical")
    if differed:
        print(f"  DIFFERENT from our copy: {differed}")
    print(
        "  The archive crawled 6 of the 13 districts. The other 7 were never "
        "captured and remain blocked on an India egress."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
