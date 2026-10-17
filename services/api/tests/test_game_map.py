from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from popshot_api.game_map import (
    MIN_GAMES,
    WINDOW,
    MyGame,
    Point,
    box,
    point,
    sliced,
    trail,
)

NOW = datetime(2026, 10, 17, 18, tzinfo=UTC)
CREW, OTHER = uuid4(), uuid4()
SAM = uuid4()


def game(
    ago: timedelta, edge: float = 0.05, crew: UUID = CREW, partners: Iterable[UUID] = ()
) -> MyGame:
    return MyGame(NOW - ago, crew, edge, frozenset(partners))


def test_a_point_needs_enough_games_for_form() -> None:
    few = [game(timedelta(days=d)) for d in range(MIN_GAMES - 1)]
    assert point(few, NOW).form is None
    assert box(point(few, NOW), 2) is None
    enough = [game(timedelta(days=d), edge=0.1 * (d % 2)) for d in range(MIN_GAMES)]
    assert point(enough, NOW).form == sum(g.edge for g in enough) / MIN_GAMES


def test_rhythm_is_games_a_week_over_the_window() -> None:
    games = [game(timedelta(days=d)) for d in (0, 3, 10, 20, 27)]
    at = point(games, NOW)
    assert at.games == 5
    assert at.per_week == 5 / (WINDOW / timedelta(days=7))
    # Exactly the window ago is out; just inside is in.
    edges = [game(WINDOW), game(WINDOW - timedelta(seconds=1))]
    assert point(edges, NOW).games == 1


def test_the_four_boxes() -> None:
    def at(per_week: float, form: float) -> Point:
        return Point(NOW, 8, per_week, form)

    assert box(at(2, 0.0), 2) == "in_the_groove"  # on the lines counts as ahead and often
    assert box(at(1.5, 0.03), 2) == "sharp_play_more"
    assert box(at(3, -0.01), 2) == "building"
    assert box(at(1, -0.05), 2) == "getting_going"
    assert box(at(1, 0.05), 1) == "in_the_groove"


def test_the_trail_is_one_point_a_week_ending_now() -> None:
    games = [game(timedelta(days=d)) for d in range(0, 60, 2)]
    points = trail(games, NOW, 6)
    assert [p.ending for p in points] == [NOW - timedelta(weeks=w) for w in range(5, -1, -1)]
    assert all(p.form is not None for p in points)
    assert trail([], NOW, 3) == [Point(NOW - timedelta(weeks=w), 0, 0.0, None) for w in (2, 1, 0)]


def test_slices() -> None:
    singles = game(timedelta(days=1))
    with_sam = game(timedelta(days=2), partners={SAM})
    elsewhere = game(timedelta(days=3), crew=OTHER, partners={uuid4()})
    games = [singles, with_sam, elsewhere]
    assert sliced(games) == games
    assert sliced(games, crew=CREW) == [singles, with_sam]
    assert sliced(games, partner=SAM) == [with_sam]
    assert sliced(games, format="singles") == [singles]
    assert sliced(games, format="doubles") == [with_sam, elsewhere]
    assert sliced(games, crew=uuid4()) == []
