from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from popshot_api.ops.tick import RECAP_AFTER, RECAP_LOOKBACK, RECAP_WITHIN, due_recaps

NOW = datetime(2026, 10, 12, 20, tzinfo=UTC)
CREW = uuid4()
ANA, BO = uuid4(), uuid4()


def row(ago: timedelta, users: list[UUID], group: UUID = CREW) -> Any:
    return SimpleNamespace(
        group_id=group,
        group_name="Lunch Dinkers",
        match_id=uuid4(),
        played_at=NOW - ago,
        user_ids=users,
    )


def test_an_outing_is_due_between_one_and_six_hours_after_its_last_game() -> None:
    rows = [row(timedelta(hours=3), [ANA]), row(timedelta(hours=2), [ANA, BO])]
    (due,) = due_recaps(rows, NOW)
    assert due.outing.key == rows[0].match_id
    assert due.players == {ANA, BO}
    assert due.crew == "Lunch Dinkers"
    assert due_recaps([row(RECAP_AFTER - timedelta(minutes=1), [ANA])], NOW) == []
    assert due_recaps([row(RECAP_WITHIN + timedelta(minutes=1), [ANA])], NOW) == []
    assert len(due_recaps([row(RECAP_AFTER, [ANA])], NOW)) == 1


def test_each_crew_and_outing_on_its_own_and_guests_left_out() -> None:
    other = uuid4()
    rows = [
        row(timedelta(hours=5), [ANA]),
        row(timedelta(hours=1.5), []),  # 3.5 hours later, guests only: nobody to tell
        row(timedelta(hours=2), [BO], group=other),
    ]
    found = {(d.group_id, d.outing.key): d.players for d in due_recaps(rows, NOW)}
    assert found == {
        (CREW, rows[0].match_id): frozenset({ANA}),
        (CREW, rows[1].match_id): frozenset(),
        (other, rows[2].match_id): frozenset({BO}),
    }


def test_an_outing_that_may_have_started_before_the_window_is_skipped() -> None:
    edge = row(RECAP_LOOKBACK - timedelta(hours=1), [ANA])
    assert due_recaps([edge], NOW) == []
