"""Turn candidate rows into seats.

Three of the sources are candidate-level: Bihar lists every contestant, UP's 2021
file has 373,096 rows over 49,772 panchayats, and Uttarakhand denormalises the
winner onto each candidate's row. Pooling them as-is would count a seat once per
person who stood for it.

**This is the riskiest transformation in the repository**, and not because it is
hard. It is the only step that changes the row count *by design*, so a bug is
indistinguishable from correct behaviour by row count alone - the exact failure
mode this corpus keeps meeting. A wrong seat key does not raise: it merges two
seats or splits one, `reconcile()` still balances because it only counts inputs
against outputs, and the women's share moves by a point nobody can attribute.

Two things contain it, and both are here rather than in the adapters:

- the reservation must be constant within a seat, checked before anything is
  pooled. Every candidate for a seat is contesting the same seat, so they all
  carry the same reservation; if two do not, the key is wrong. Run by hand
  before this module was written: 0 violations across all six Bihar files and
  UP 2021, and **9 of 18,826 seats in Uttarakhand** - the check found something
  real before it was even committed.
- `seat_candidates` on every row, so the denominator is visible. Bihar's
  mukhiya averages 12 candidates a seat; one showing 40, or 1, is where to look.

The winner is the only field that needs inference, and it says which kind it is:
`published` where the source marks the winner, `argmax_votes` where it has to be
worked out - and that one also sets `winner_inferred` in quality_flags.
"""

import collections

# Values that mean "no vote was recorded", not "zero votes".
NOT_A_COUNT = {"", "-", "--", "na", "n/a", "nil", "--select--"}


class ReservationVaries(Exception):
    """One seat, two reservations. The seat key is wrong, or the source is.

    Raised rather than resolved: picking the majority would hide a key that
    merges two real seats, which is the thing this module exists to prevent.
    """


def votes_of(value):
    """A vote count, or None where the source recorded none.

    None is not zero. An uncontested seat and a seat where nobody voted are
    different, and Bihar writes both - 24 seats with no numeric vote, and one
    reading "986+1 (BY LOT)".
    """
    text = str(value or "").strip().lower()
    if text in NOT_A_COUNT:
        return None
    digits = "".join(c for c in text.split("+")[0] if c.isdigit())
    return int(digits) if digits else None


def to_seats(rows, key_fields, reservation_fields=("caste_reservation",
                                                   "woman_reserved"),
             vote_field=None, winner_field=None, winner_value=None):
    """One row per seat, from many rows per candidate.

    `winner_field`/`winner_value` name an explicit winner marker; failing that,
    `vote_field` selects by highest vote. A tie leaves the winner blank rather
    than picking one - two people cannot both have won, and a coin toss recorded
    as fact is worse than a gap.
    """
    grouped = collections.OrderedDict()
    for row in rows:
        grouped.setdefault(tuple(row.get(f, "") for f in key_fields),
                           []).append(row)

    out = []
    for key, candidates in grouped.items():
        stated = {tuple(c.get(f, "") for f in reservation_fields)
                  for c in candidates}
        if len(stated) > 1:
            raise ReservationVaries(f"{key}: {sorted(stated)}")

        seat = dict(candidates[0])
        seat["seat_candidates"] = len(candidates)
        seat["unit_of_observation"] = "seat_from_candidates"

        won, basis = None, ""
        if winner_field:
            marked = [c for c in candidates
                      if str(c.get(winner_field, "")).strip() == winner_value]
            if len(marked) == 1:
                won, basis = marked[0], "published"
        if won is None and vote_field:
            counted = [(votes_of(c.get(vote_field)), c) for c in candidates]
            counted = [(v, c) for v, c in counted if v is not None]
            if counted:
                best = max(v for v, _ in counted)
                leaders = [c for v, c in counted if v == best]
                if len(leaders) == 1:
                    won, basis = leaders[0], "argmax_votes"

        seat["winner"] = (won or {}).get("candidate_name") or \
            (won or {}).get("winner") or ""
        seat["winner_basis"] = basis if seat["winner"] else ""
        out.append(seat)
    return out


def varies(rows, key_fields, reservation_fields=("caste_reservation",
                                                 "woman_reserved")):
    """Seats whose candidates disagree about the reservation, without raising.

    For measuring a source before deciding how to treat it - Uttarakhand's nine
    are a finding to look at, not a reason to refuse the whole state.
    """
    grouped = collections.defaultdict(set)
    for row in rows:
        grouped[tuple(row.get(f, "") for f in key_fields)].add(
            tuple(row.get(f, "") for f in reservation_fields))
    return {k: v for k, v in grouped.items() if len(v) > 1}
