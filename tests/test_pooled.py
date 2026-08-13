"""What `pooled()` must keep, and why it is a test rather than a comment.

`pooled()` projects every row into the master's 36 declared columns. For a whole
phase it yielded only that projection, and the checks read it: `caste_share_vs_
population` - the strongest external check here, reserved seats sitting where
the reserved population lives - went from 2 passes to 2 silent skips, because
the columns it appeals to are exactly the ones the projection drops.

Nothing caught it. The check did not fail, it skipped; the row counts were
right; a verification step that promised no existing number would move did not
notice a number that had stopped existing. So the invariant is asserted here
instead: a pooled row carries the master's columns **over** the row it came
from, not instead of it.
"""


import pytest

from local_reservations.common import master


def test_the_projection_does_not_replace_the_source_row():
    """This is the shape `pooled()` yields: `dict(row, **projection)`."""
    source = {"state": "Karnataka", "year": "2007", "tier": "gp_head",
              "caste_reservation": "SC", "woman_reserved": "1",
              "pop_total": "1200", "pop_sc": "300", "ward_count": "12"}
    projected = master.to_master(source, "karnataka/gp_head/2007",
                                 "local_elections", "abc", "dataset")
    pooled = dict(source, **projected)

    # the master's own columns are present and win. row_id and seat_key_unique
    # are not among them: build() assigns those once it has seen every row, so
    # they cannot be decided one row at a time.
    assigned_later = {"row_id", "seat_key_unique"}
    assert set(master.MASTER_COLUMNS) - assigned_later <= set(pooled)
    assert pooled["dataset_id"] == "karnataka/gp_head/2007"
    # and what the projection drops is still there for the checks to read
    for column in ("pop_total", "pop_sc", "ward_count"):
        assert pooled[column] == source[column], column


@pytest.mark.parametrize("column", ["pop_total", "pop_sc", "ward_count",
                                    "seat_from_image", "printings_agree"])
def test_the_columns_the_checks_appeal_to_are_not_master_columns(column):
    """Each of these is read by a check and dropped by the projection, which is
    what made the loss silent. If one is ever promoted into MASTER_COLUMNS this
    test says so, and the reason for the one above goes with it."""
    assert column not in master.MASTER_COLUMNS
