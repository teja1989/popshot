from datetime import UTC, date, datetime, timedelta, timezone

from popshot_api.ops.tick import week_due

# Monday 12 October 2026.
MONDAY = date(2026, 10, 12)


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


def test_due_from_13_utc_on_monday_until_the_day_ends() -> None:
    assert week_due(at(MONDAY, 12, 59)) is None
    assert week_due(at(MONDAY, 13)) == MONDAY
    assert week_due(at(MONDAY, 23, 59)) == MONDAY
    assert week_due(at(MONDAY + timedelta(days=1), 0)) is None
    # Any other day.
    for days in range(1, 7):
        assert week_due(at(MONDAY + timedelta(days=days), 14)) is None


def test_the_monday_is_a_utc_monday() -> None:
    # 9am Monday in New York is 13:00 UTC: due.
    new_york = timezone(timedelta(hours=-4))
    assert week_due(datetime(2026, 10, 12, 9, tzinfo=new_york)) == MONDAY
    # 8pm Monday in Tokyo is still 11:00 UTC: not yet.
    tokyo = timezone(timedelta(hours=9))
    assert week_due(datetime(2026, 10, 12, 20, tzinfo=tokyo)) is None
