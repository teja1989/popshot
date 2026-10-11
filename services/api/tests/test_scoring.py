import json
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from popshot_api.scoring import (
    MAX_POINTS,
    GameRules,
    ScoreError,
    Team,
    validate_game,
    validate_match,
)

rules_strategy = st.builds(
    GameRules, points_to=st.sampled_from([11, 15, 21]), win_by_two=st.booleans()
)
points = st.integers(min_value=0, max_value=MAX_POINTS)


def _over(rules: GameRules, a: int, b: int) -> bool:
    """Independent oracle: is the game over at this score?"""
    lead = abs(a - b)
    reached = max(a, b) >= rules.points_to
    return reached and (lead >= 2 if rules.win_by_two else lead >= 1)


@cache
def _reachable(rules: GameRules, a: int, b: int) -> bool:
    """Can a game get to this score one rally at a time without ending earlier?"""
    if a == 0 and b == 0:
        return True
    from_a = a > 0 and _reachable(rules, a - 1, b) and not _over(rules, a - 1, b)
    from_b = b > 0 and _reachable(rules, a, b - 1) and not _over(rules, a, b - 1)
    return from_a or from_b


def _is_final(rules: GameRules, a: int, b: int) -> bool:
    return _over(rules, a, b) and _reachable(rules, a, b)


@given(rules_strategy, points, points)
def test_validate_game_matches_the_rally_oracle(rules: GameRules, a: int, b: int) -> None:
    if _is_final(rules, a, b):
        assert validate_game(rules, a, b) is (Team.A if a > b else Team.B)
    else:
        with pytest.raises(ScoreError):
            validate_game(rules, a, b)


@given(rules_strategy, points, points)
def test_validate_game_is_symmetric(rules: GameRules, a: int, b: int) -> None:
    try:
        first = validate_game(rules, a, b)
    except ScoreError:
        with pytest.raises(ScoreError):
            validate_game(rules, b, a)
    else:
        assert validate_game(rules, b, a) is not first


@pytest.mark.parametrize(
    ("points_to", "win_by_two", "a", "b", "ok"),
    [
        (11, True, 11, 9, True),
        (11, True, 11, 0, True),
        (11, True, 11, 10, False),
        (11, True, 12, 10, True),
        (11, True, 13, 11, True),
        (11, True, 12, 9, False),
        (11, True, 14, 11, False),
        (11, False, 11, 10, True),
        (11, False, 12, 10, False),
        (15, True, 15, 13, True),
        (15, True, 17, 15, True),
        (21, True, 21, 19, True),
        (21, True, 22, 20, True),
        (21, False, 21, 20, True),
        (21, False, 20, 18, False),
        (11, True, 10, 8, False),
        (11, True, 5, 5, False),
    ],
)
def test_known_scores(points_to: int, win_by_two: bool, a: int, b: int, ok: bool) -> None:
    rules = GameRules(points_to, win_by_two)
    if ok:
        validate_game(rules, a, b)
    else:
        with pytest.raises(ScoreError):
            validate_game(rules, a, b)


@pytest.mark.parametrize("bad", [-1, MAX_POINTS + 1, True, 11.0, "11", None])
def test_rejects_non_scores(bad: object) -> None:
    with pytest.raises(ScoreError):
        validate_game(GameRules(11, True), bad, 0)  # type: ignore[arg-type]


@pytest.mark.parametrize("points_to", [0, 7, 10, 12, 25])
def test_rejects_unsupported_points_to(points_to: int) -> None:
    with pytest.raises(ScoreError):
        GameRules(points_to, True)


RULES = GameRules(11, True)


@pytest.mark.parametrize(
    ("best_of", "games", "winner"),
    [
        (1, [(11, 7)], Team.A),
        (1, [(4, 11)], Team.B),
        (3, [(11, 7), (11, 9)], Team.A),
        (3, [(11, 7), (9, 11), (8, 11)], Team.B),
        (3, [(3, 11), (12, 10), (11, 0)], Team.A),
    ],
)
def test_valid_matches(best_of: int, games: list[tuple[int, int]], winner: Team) -> None:
    assert validate_match(RULES, best_of, games) is winner


@pytest.mark.parametrize(
    ("best_of", "games"),
    [
        (1, []),
        (1, [(11, 7), (11, 7)]),
        (3, [(11, 7)]),
        (3, [(11, 7), (7, 11)]),
        (3, [(11, 7), (11, 7), (11, 7)]),
        (3, [(11, 7), (11, 10)]),
        (2, [(11, 7), (11, 7)]),
        (5, [(11, 7), (11, 7), (11, 7)]),
    ],
)
def test_invalid_matches(best_of: int, games: list[tuple[int, int]]) -> None:
    with pytest.raises(ScoreError):
        validate_match(RULES, best_of, games)


@given(
    rules_strategy,
    st.lists(st.tuples(points, points), min_size=1, max_size=4),
)
def test_best_of_three_winner_has_exactly_two_games(
    rules: GameRules, games: list[tuple[int, int]]
) -> None:
    try:
        winner = validate_match(rules, 3, games)
    except ScoreError:
        return
    winners = [Team.A if a > b else Team.B for a, b in games]
    assert winners.count(winner) == 2
    assert winners[-1] is winner
    assert len(games) in (2, 3)


# Cases the web app's validator (apps/web/src/lib/scoring.ts) is tested against too.
SHARED = json.loads(
    (Path(__file__).resolve().parents[3] / "shared" / "score-cases.json").read_text()
)


@pytest.mark.parametrize("case", SHARED["games"], ids=lambda c: f"{c['a']}-{c['b']}")
def test_shared_game_cases(case: dict[str, Any]) -> None:
    rules = GameRules(case["points_to"], case["win_by_two"])
    if case["ok"]:
        validate_game(rules, case["a"], case["b"])
    else:
        with pytest.raises(ScoreError):
            validate_game(rules, case["a"], case["b"])


@pytest.mark.parametrize("case", SHARED["matches"])
def test_shared_match_cases(case: dict[str, Any]) -> None:
    rules = GameRules(case["points_to"], case["win_by_two"])
    games = [(a, b) for a, b in case["games"]]
    if case["winner"] is None:
        with pytest.raises(ScoreError):
            validate_match(rules, case["best_of"], games)
    else:
        assert validate_match(rules, case["best_of"], games) == case["winner"]
