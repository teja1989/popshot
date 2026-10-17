from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from popshot_api.ops.tick import RECAP_AFTER, RECAP_LOOKBACK, RECAP_WITHIN, due_recaps
from popshot_api.recap import MIN_GAMES, day_key

# Monday 12 October 2026, 4pm in New York.
NOW = datetime(2026, 10, 12, 20, tzinfo=UTC)
CREW = uuid4()
ANA, BO = uuid4(), uuid4()


def row(ago: timedelta, users: list[UUID], group: UUID = CREW, zone: str = "UTC") -> Any:
    return SimpleNamespace(
        group_id=group,
        group_name="Lunch Dinkers",
        time_zone=zone,
        match_id=uuid4(),
        played_at=NOW - ago,
        user_ids=users,
    )


def day(last: timedelta, users: list[UUID], group: UUID = CREW, zone: str = "UTC") -> list[Any]:
    """MIN_GAMES games ten minutes apart, the last `last` ago."""
    return [row(last + timedelta(minutes=10 * i), users, group, zone) for i in range(MIN_GAMES)][
        ::-1
    ]


def test_a_day_is_due_between_one_and_six_hours_after_its_last_game() -> None:
    rows = [row(timedelta(hours=3), [ANA]), *day(timedelta(hours=2), [ANA, BO])]
    (due,) = due_recaps(rows, NOW)
    assert due.outing.key == day_key(CREW, date(2026, 10, 12))
    assert len(due.outing.matches) == MIN_GAMES + 1
    assert due.players == {ANA, BO}
    assert due.crew == "Lunch Dinkers"
    assert due_recaps(day(RECAP_AFTER - timedelta(minutes=1), [ANA]), NOW) == []
    assert due_recaps(day(RECAP_WITHIN + timedelta(minutes=1), [ANA]), NOW) == []
    assert len(due_recaps(day(RECAP_AFTER, [ANA]), NOW)) == 1


def test_a_day_with_fewer_games_gets_no_push() -> None:
    assert due_recaps(day(timedelta(hours=2), [ANA])[1:], NOW) == []


def test_each_crew_on_its_own_and_guests_left_out() -> None:
    other = uuid4()
    rows = [*day(timedelta(hours=2), []), *day(timedelta(hours=3), [BO], group=other)]
    found = {d.group_id: d.players for d in due_recaps(rows, NOW)}
    assert found == {CREW: frozenset(), other: frozenset({BO})}


def test_days_follow_the_crews_own_clock() -> None:
    # 9pm to 10pm in New York last night is 1am to 2am UTC today: its own day, long over.
    last_night = day(timedelta(hours=18), [ANA], zone="America/New_York")
    this_afternoon = day(timedelta(hours=2), [ANA], zone="America/New_York")
    (due,) = due_recaps([*last_night, *this_afternoon], NOW)
    assert due.outing.key == day_key(CREW, date(2026, 10, 12))
    assert len(due.outing.matches) == MIN_GAMES


def test_the_job_reads_back_far_enough_for_any_whole_day() -> None:
    # A due day ended at most RECAP_WITHIN ago and lasts at most 25 hours.
    assert RECAP_WITHIN + timedelta(hours=25) <= RECAP_LOOKBACK
