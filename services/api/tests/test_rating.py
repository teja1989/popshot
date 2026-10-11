import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from popshot_api.rating import (
    LEVEL_START,
    MAX,
    MIN,
    RANKED_AFTER,
    RESTING_AFTER,
    START,
    STEADY_AFTER,
    STEP_NEW,
    STEP_SETTLED,
    TREND_EDGE,
    TREND_MIN_GAMES,
    TREND_WINDOW,
    GameScore,
    PlayedMatch,
    expected_share,
    reliability,
    replay,
    step,
    trend,
    week_change,
)

T0 = datetime(2026, 9, 1, 18, tzinfo=UTC)
A, B, C, D = (uuid4() for _ in range(4))


def match(a: list[UUID], b: list[UUID], *games: tuple[int, int], at: datetime = T0) -> PlayedMatch:
    return PlayedMatch(
        id=uuid4(), played_at=at, team_a=a, team_b=b, games=[GameScore(x, y) for x, y in games]
    )


def test_expected_share() -> None:
    assert expected_share(3.0, 3.0) == pytest.approx(0.5)
    # A 1.0 gap expects roughly an 11-7 split.
    assert expected_share(4.0, 3.0) == pytest.approx(11 / 18, abs=0.01)
    assert expected_share(3.0, 4.0) == pytest.approx(1 - expected_share(4.0, 3.0))


def test_winners_go_up_losers_down_from_equal_ratings() -> None:
    rated = replay([match([A, B], [C, D], (11, 5))], {})
    assert rated[A].rating > START
    assert rated[B].rating > START
    assert rated[C].rating < START
    assert rated[D].rating < START
    assert rated[A].rating == pytest.approx(rated[B].rating)


def test_margin_matters() -> None:
    close = replay([match([A], [B], (11, 9))], {})[A].rating
    blowout = replay([match([A], [B], (11, 1))], {})[A].rating
    assert START < close < blowout


def test_beating_a_stronger_player_earns_more() -> None:
    vs_strong = replay([match([A], [B], (11, 9))], {B: 4.0})[A].rating
    vs_weak = replay([match([A], [B], (11, 9))], {B: 2.5})[A].rating
    assert vs_strong > START
    # Winning 11-9 against a much weaker player is closer than expected: a small dip.
    assert vs_weak < START < vs_strong


def test_each_game_of_a_best_of_three_counts() -> None:
    one = replay([match([A], [B], (11, 5))], {})[A].rating
    three = replay([match([A], [B], (11, 5), (9, 11), (11, 5))], {})
    assert three[A].rating != pytest.approx(one)
    assert (three[A].matches, three[A].wins, three[B].wins) == (1, 1, 0)


def test_new_players_move_faster() -> None:
    assert step(0) > step(5) > step(15) == step(40)


def test_self_rated_start_and_clamps() -> None:
    rated = replay([match([A], [B], *[(11, 0)] * 3) for _ in range(60)], {A: 5.9, B: 2.1})
    assert rated[A].rating <= MAX
    assert rated[B].rating >= MIN
    assert rated[A].rating == MAX
    assert rated[B].rating == MIN


def test_order_is_by_when_played_not_when_logged() -> None:
    late = match([A], [B], (11, 2), at=T0 + timedelta(days=2))
    early = match([B], [A], (11, 2), at=T0)
    assert replay([late, early], {})[A].rating == pytest.approx(replay([early, late], {})[A].rating)
    assert replay([late, early], {})[A].results == ["L", "W"]


def test_reliability_and_movement() -> None:
    games = [match([A], [B], (11, 7), at=T0 + timedelta(days=i)) for i in range(20)]
    rated = replay(games, {})[A]
    last = T0 + timedelta(days=19)
    assert reliability(rated, last) == 100
    assert reliability(rated, last + timedelta(days=60)) == 75
    assert reliability(rated, last + timedelta(days=400)) == 50
    assert reliability(replay(games[:5], {})[A], last) == 25
    change = week_change(rated, last)
    assert change is not None
    assert change != 0
    assert week_change(replay(games[:1], {})[A], T0 + timedelta(days=3)) is None


@given(
    st.lists(
        st.tuples(st.integers(0, 15), st.integers(0, 15)).filter(lambda s: s != (0, 0)),
        min_size=1,
        max_size=40,
    ),
    st.floats(MIN, MAX),
    st.floats(MIN, MAX),
)
def test_ratings_always_stay_in_range(
    scores: list[tuple[int, int]], start_a: float, start_b: float
) -> None:
    rated = replay(
        [match([A, B], [C, D], s, at=T0 + timedelta(hours=i)) for i, s in enumerate(scores)],
        {A: start_a, C: start_b},
    )
    for player in rated.values():
        assert MIN <= player.rating <= MAX
        assert len(player.history) == player.matches == len(scores)


def test_edges_are_points_won_against_expected() -> None:
    rated = replay([match([A, B], [C, D], (11, 9))], {})
    # Even teams expect half the points; 11 of 20 is 5% more.
    assert [at for at, _ in rated[A].edges] == [T0]
    assert rated[A].edges[0][1] == pytest.approx(0.05)
    assert rated[C].edges[0][1] == pytest.approx(-0.05)
    # Over a best-of-three it's the average of the games, each against what was expected
    # going into it (ratings move between games).
    three = replay([match([A], [B], (11, 9), (7, 11))], {})
    first = 0.05
    after = replay([match([A], [B], (11, 9))], {})
    second = 7 / 18 - expected_share(after[A].rating, after[B].rating)
    assert three[A].edges[0][1] == pytest.approx((first + second) / 2)


def test_trend_needs_enough_games_in_the_window() -> None:
    now = T0 + timedelta(days=1)
    few = replay([match([A], [B], (11, 3), at=T0) for _ in range(TREND_MIN_GAMES - 1)], {})
    assert trend(few[A], now).label is None
    assert trend(few[A], now).games == TREND_MIN_GAMES - 1
    enough = replay([match([A], [B], (11, 3), at=T0) for _ in range(TREND_MIN_GAMES)], {})
    assert trend(enough[A], now).label == "climbing"
    assert trend(enough[B], now).label == "slipping"


def test_trend_only_counts_the_window() -> None:
    old = T0 - TREND_WINDOW - timedelta(days=1)
    games = [match([A], [B], (11, 3), at=old) for _ in range(20)]
    rated = replay(games, {})
    now = T0
    month = trend(rated[A], now)
    assert (month.games, month.change, month.edge, month.label) == (0, 0.0, None, None)
    # Then a month of games played as expected: steady, and points barely move.
    recent = [match([A], [B], (11, 3), at=T0 - timedelta(days=d)) for d in range(1, 8)]
    rated = replay(games + recent, {})
    month = trend(rated[A], now)
    assert month.games == len(recent)
    assert month.change == pytest.approx(rated[A].rating - rated[A].history[19][1])


def test_trend_change_counts_from_the_start_for_new_players() -> None:
    rated = replay([match([A], [B], (11, 9))], {A: 4.0})
    assert trend(rated[A], T0 + timedelta(days=1)).change == pytest.approx(rated[A].rating - 4.0)


def test_steady_when_playing_to_your_rating() -> None:
    a, b = 3.5, 3.0
    share = expected_share(a, b)
    # Scores as close to the expected split as whole points allow, at 21 points a game.
    won = round(21 * share)
    games = [match([A], [B], (won, 21 - won), at=T0) for _ in range(TREND_MIN_GAMES)]
    month = trend(replay(games, {A: a, B: b})[A], T0 + timedelta(days=1))
    assert month.edge is not None
    assert abs(month.edge) < TREND_EDGE
    assert month.label == "steady"


def test_the_explanation_matches_the_maths() -> None:
    """shared/crew-points.json is what the app tells people; it must be true."""
    told = json.loads(
        (Path(__file__).resolve().parents[3] / "shared" / "crew-points.json").read_text()
    )
    assert (told["min"], told["max"], told["start"]) == (MIN, MAX, START)
    assert told["steady_after"] == STEADY_AFTER
    assert told["ranked_after"] == RANKED_AFTER
    assert told["resting_after_days"] == RESTING_AFTER.days
    assert told["level_start"] == dict(LEVEL_START)
    ex = told["example"]
    expected = expected_share(ex["team"], ex["opponents"])
    won, lost = ex["score"]
    surprise = won / (won + lost) - expected
    assert round(expected, 2) == ex["expected_share"]
    assert round(STEP_SETTLED * surprise, 2) == ex["change_settled"]
    assert round(STEP_NEW * surprise, 2) == ex["change_new"]
