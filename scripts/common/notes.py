"""What is wrong with a slice, and whether anyone can do anything about it.

The readme's per-slice table carried its caveats as free text in a Notes column,
which mixed two things that need separating:

  - facts about what a document contains, which no amount of work on *that
    document* changes; and
  - places where the document contains more than our parse recovered.

Read together they are background noise. Read apart, the second list is a
worklist. So a note is a declaration with a **status**:

    SOURCE_PROPERTY   the document says what it says. Nothing to do.
    OPEN_GAP          the document holds more than we took. `closes_with` says
                      what would close it.
    UNDETERMINED      we have not established which of the two it is - and that
                      is itself the work.

`UNDETERMINED` is the honest third answer and it earns its place. "No winner was
published" is a claim about the universe of documents, not about the file in
hand; asserting it as a source property is asserting something nobody checked.

Every note is detected from the rows, so a note cannot be marked done while the
condition still holds, and cannot linger once it stops holding. Fix Jharkhand's
image-only column and the line disappears from WORKLIST.md on the next build.
"""

import collections

import canon
import reference

SOURCE_PROPERTY = "source property"
OPEN_GAP = "open gap"
UNDETERMINED = "undetermined"
# Closable, but not from here. Kept apart from OPEN_GAP because "nobody has done
# this" and "nobody here can do this" are different claims, and a worklist that
# mixes them is one nobody trusts.
BLOCKED = "blocked"

NOTES = []


def note(note_id, text, status, because, closes_with=""):
    def register(detect):
        NOTES.append({
            "id": note_id, "text": text, "status": status, "because": because,
            "closes_with": closes_with, "detect": detect,
        })
        return detect
    return register


def found(rows_affected, detail="", status=None):
    return {"rows_affected": rows_affected, "detail": detail, "status": status}


# --------------------------------------------------------- source properties

@note("reserved_only_listing",
      "lists only the reserved seats",
      SOURCE_PROPERTY,
      because="The document is a roster of reserved seats. Its shares describe "
              "which pages were published, not the state - J&K 2018 reads 82% "
              "women for that reason alone.")
def reserved_only_listing(s):
    if s.scope == "reserved_only":
        return found(s.n, "shares here are a property of the document")
    return None


@note("no_ward_column_in_the_source",
      "the source has no ward column",
      SOURCE_PROPERTY,
      because="Anantapur's PROFORMA-I is a sarpanch list printed without ward "
              "columns, so there is no count to read and no wards missing.")
def no_ward_column_in_the_source(s):
    if "ward_count" not in s.rows[0] or s.tier != "gp_head":
        return None
    none = sum(1 for r in s.rows if not (r.get("ward_count") or "").strip()
               and str(r.get("wards_parsed") or "0") == "0")
    return found(none, "sarpanch rows carrying no wards at all") if none else None


# ----------------------------------------------------------------- open gaps

@note("names_not_transliterated",
      "place names are in a legacy font",
      OPEN_GAP,
      because="Kruti Dev is a deterministic byte mapping, not damage. The names "
              "are recoverable; they simply have not been converted, so these "
              "rows cannot be joined to any other source on name.",
      closes_with="a Kruti Dev to Unicode transliterator applied to district, "
                  "block and gram_panchayat")
def names_not_transliterated(s):
    affected = sum(1 for r in s.rows if r.get("script") == "krutidev")
    return found(affected) if affected else None


@note("seat_id_drawn_as_an_image",
      "the seat identifier is an image, not text",
      OPEN_GAP,
      because="On three pages of the Lohardaga notification the whole seat "
              "column is 40 embedded images. The text layer holds only the "
              "district's roman numeral, so the block, panchayat and ward "
              "number are unreachable by parsing - and those rows then collide "
              "with each other on the seat key.",
      closes_with="Devanagari OCR of the seat column on pages 22-24 of "
                  "LOHARDAGA ZP PSS MUKHIYA GPS.pdf. The images render clean "
                  "Unicode, easier than the Kruti Dev the rest of the state is "
                  "in, and split_seat_id already parses the shape they use")
def seat_id_drawn_as_an_image(s):
    affected = sum(1 for r in s.rows
                   if (r.get("seat_id_raw") or "").strip().isupper()
                   and len((r.get("seat_id_raw") or "").split()) == 1
                   and not canon.unit_name(r))
    return found(affected) if affected else None


@note("gender_not_stated",
      "the source states a caste but no gender",
      OPEN_GAP,
      because="Where a document marks both the women's and the open seats, a "
              "code whose marker did not survive the scan is unknown, not male "
              "- and woman_reserved defaults to 0, which silently turns a "
              "woman's seat into an open one. Worse, the two markers are not "
              "lost at equal rates: Prakasam loses (G) about twice as often as "
              "(W), so its surviving rows read 66% women against a statutory "
              "half. Neither the raw share nor the filtered one estimates the "
              "truth there.",
      closes_with="a second reading of the affected pages - the codes are "
                  "printed, they simply did not survive this scan. Anantapur "
                  "fell from 25% unmarked to 4% once the hyphen and run-on "
                  "forms of the marker were recognised, so the remainder is "
                  "likely reachable the same way")
def gender_not_stated(s):
    if "gender_stated" not in s.rows[0]:
        return None
    unstated = [r for r in s.rows if r.get("gender_stated") != "1"]
    if not unstated:
        return None
    worst = collections.Counter(r.get("district", "") for r in unstated)
    where = ", ".join(f"{d} {n:,}" for d, n in worst.most_common(3))
    return found(len(unstated), where)


@note("ward_list_incomplete",
      "some ward lists are shorter than the record says",
      OPEN_GAP,
      because="The line was cut at the page's right edge, so wards are missing "
              "rather than blank. This is measurable rather than hidden only "
              "because the record states its own count - and it biases the "
              "women's share downward, 37% across truncated records against "
              "47% across whole ones.",
      closes_with="re-reading the truncated records at a wider render, or from "
                  "the second proforma where one exists")
def ward_list_incomplete(s):
    short = sum(1 for r in s.rows if r.get("ward_list_complete") == "0")
    return found(short, f"{short / s.n:.0%} of rows") if short else None


@note("districts_missing",
      "some districts are not held",
      OPEN_GAP,
      because="The state has more districts than we have documents for, so "
              "every share here describes the districts we hold.",
      closes_with="harvesting the remaining districts' notifications")
def districts_missing(s):
    """Rows affected is an estimate of what is *missing*, not what we have.

    Counting every row of a partial state made the gap grow each time a
    district was added - West Godavari brought 9,070 wards and the entry went up
    by 9,921, which reads as a regression for what is plainly progress. The
    estimate is the average district's row count times the number of districts
    still unheld, so it falls as they are collected.
    """
    expected = reference.districts_expected(s.state, s.year)
    got = len({r.get("district") for r in s.rows if r.get("district")})
    if not (expected and got and got < expected):
        return None
    estimate = round(s.n / got * (expected - got))
    detail = f"{got} of {expected} districts, roughly {estimate:,} rows missing"
    access, why = reference.source_access(s.state)
    if access == "blocked":
        return found(estimate, f"{detail} - {why}", status=BLOCKED)
    return found(estimate, detail)


@note("panchayat_not_named",
      "the row does not say which panchayat",
      OPEN_GAP,
      because="The reservation and the winner were read but the seat column "
              "was not, so the row is a real seat whose identity is unknown. "
              "This is most of what looks like a key collision: two rows that "
              "both name no panchayat are not duplicates, they are two "
              "different seats we cannot tell apart. Jharkhand's OCR'd "
              "districts name it on 34% of rows against 92% for the districts "
              "that came as text.",
      closes_with="a better read of the seat column on the scanned pages - the "
                  "identifier is printed, it is the scan that did not carry it")
def panchayat_not_named(s):
    if s.tier in ("zp_member", "block_head", "zp_head"):
        return None          # numbered across the district, no panchayat to name
    missing = [r for r in s.rows if not canon.unit_name(r)]
    if not missing:
        return None
    worst = collections.Counter(r.get("district", "") for r in missing)
    return found(len(missing), ", ".join(f"{d} {n:,}"
                                         for d, n in worst.most_common(3)))


@note("seat_key_not_unique",
      "some rows do not identify a distinct seat",
      OPEN_GAP,
      because="Two rows sharing a district, block, panchayat and ward number "
              "cannot be told apart. Usually one of those four did not parse.",
      closes_with="parsing whichever identifier is blank on the colliding rows")
def seat_key_not_unique(s):
    # Rows that name no panchayat are counted by panchayat_not_named instead.
    # Lumping them here says two seats are duplicates when what is true is that
    # we cannot tell them apart - a different problem with a different fix.
    named = [r for r in s.rows if canon.unit_name(r)]
    counts = collections.Counter(
        (r.get("district", ""), r.get("block", ""), canon.unit_name(r),
         r.get("ward_no", ""), r.get("seat_no", "")) for r in named)
    dup = sum(n for n in counts.values() if n > 1)
    if not dup:
        return None
    worst = counts.most_common(1)[0] if counts else ((), 0)
    return found(dup, f"largest group {worst[1]} rows")


@note("district_not_printed",
      "the district column is mostly blank",
      OPEN_GAP,
      because="The source prints no district, but the file path names one, so "
              "it is recoverable from provenance rather than from the page.",
      closes_with="deriving district from source_path where the page omits it")
def district_not_printed(s):
    blank = sum(1 for r in s.rows if not (r.get("district") or "").strip())
    if blank > 0.5 * s.n:
        return found(blank, f"{blank / s.n:.0%} of rows")
    return None


# ------------------------------------------------------------- undetermined

@note("no_winner_recorded",
      "no winner is recorded",
      UNDETERMINED,
      because="Whether this is a source property depends on what stage of "
              "document it is. A pre-poll reservation roster names no winner "
              "and never will; for anything else, a results notification may "
              "exist that we have not looked for. Asserting the first without "
              "checking is a claim about every document a state published.",
      closes_with="declaring reference.DOCUMENT_STAGE for this slice - "
                  "pre_poll settles it as a source property, and anything else "
                  "means going to look")
def no_winner_recorded(s):
    if any((r.get("winner") or "").strip() for r in s.rows):
        return None
    stage = reference.document_stage(s.state, s.year, s.tier)
    if stage == "pre_poll":
        return found(s.n, "a pre-poll roster names no winner",
                     status=SOURCE_PROPERTY)
    return found(s.n, "no document stage declared for this slice")


@note("partial_listing",
      "the roster is incomplete",
      UNDETERMINED,
      because="The document holds fewer seats than the state has. Whether a "
              "complete roster was ever published is a different question from "
              "whether this file is complete, and only the second is settled.",
      closes_with="establishing whether a full roster exists for this cycle")
def partial_listing(s):
    if s.scope == "partial":
        return found(s.n, "measured against a complete cycle of the same state")
    return None


def for_slice(a_slice):
    """Every note that applies to one slice."""
    out = []
    for spec in NOTES:
        got = spec["detect"](a_slice)
        if not got:
            continue
        out.append({
            "note_id": spec["id"], "text": spec["text"],
            # a detector may settle an undetermined note on the spot
            "status": got.get("status") or spec["status"],
            "because": spec["because"], "closes_with": spec["closes_with"],
            "rows_affected": got["rows_affected"], "detail": got["detail"],
        })
    return out
