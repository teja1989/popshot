"""Score rules for a pickleball game and a best-of-N match.

A game is played to `points_to` (11, 15 or 21). With win-by-2 on, the game continues past
`points_to` until one side leads by two. A final score is valid only if the game had just
ended at exactly that score: it is over, and it was not already over one point earlier.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

POINTS_TO_OPTIONS = frozenset({11, 15, 21})
BEST_OF_OPTIONS = frozenset({1, 3, 5})
# Sanity cap so a typo like 1100 is rejected. A real win-by-2 game never gets close.
MAX_POINTS = 99


class Team(StrEnum):
    A = "A"
    B = "B"


class ScoreError(ValueError):
    """The score can't be the final score of a game or match under the given rules."""


@dataclass(frozen=True, slots=True)
class GameRules:
    points_to: int
    win_by_two: bool

    def __post_init__(self) -> None:
        if self.points_to not in POINTS_TO_OPTIONS:
            raise ScoreError("Games are played to 11, 15 or 21.")


def _check_points(value: object) -> int:
    # bool is a subclass of int; reject it explicitly.
    if not isinstance(value, int) or isinstance(value, bool):
        raise ScoreError("Scores must be whole numbers.")
    if not 0 <= value <= MAX_POINTS:
        raise ScoreError(f"Scores must be between 0 and {MAX_POINTS}.")
    return value


def validate_game(rules: GameRules, team_a: int, team_b: int) -> Team:
    """Return the winning team, or raise ScoreError if this can't be a final score."""
    a = _check_points(team_a)
    b = _check_points(team_b)
    if a == b:
        raise ScoreError("A game can't end in a tie.")
    winner, loser = max(a, b), min(a, b)
    target = rules.points_to

    if not rules.win_by_two:
        if winner != target:
            raise ScoreError(f"Without win-by-2, the winner finishes on exactly {target}.")
    elif loser <= target - 2:
        if winner != target:
            raise ScoreError(f"The winner finishes on {target} when the other side has {loser}.")
    elif winner != loser + 2:
        raise ScoreError("Past game point, the winner finishes exactly two points ahead.")

    return Team.A if a > b else Team.B


def validate_match(rules: GameRules, best_of: int, games: Sequence[tuple[int, int]]) -> Team:
    """Validate every game and the match shape; return the match winner."""
    if best_of not in BEST_OF_OPTIONS:
        raise ScoreError("A match is a single game, best of 3 or best of 5.")
    if not games:
        raise ScoreError("Enter at least one game.")

    needed = best_of // 2 + 1
    wins = {Team.A: 0, Team.B: 0}
    for number, (team_a, team_b) in enumerate(games, start=1):
        if max(wins.values()) == needed:
            raise ScoreError(f"The match was already decided before game {number}.")
        wins[validate_game(rules, team_a, team_b)] += 1

    for team, count in wins.items():
        if count == needed:
            return team
    raise ScoreError("The match isn't finished yet.")
