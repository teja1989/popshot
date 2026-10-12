"""Recaps: a crew's games grouped into outings, and what's worth celebrating in each.

An outing is a run of games with no gap longer than OUTING_GAP between them: a morning
session, a lunchtime game, an evening meetup. No time zones needed. Its key is its first
match's id.

Awards only ever celebrate (agreed with the crew): nothing for losing, nobody is "worst".
- Always There: has played every week for ALWAYS_THERE_WEEKS weeks or more, counting this one.
- Great Partner: won with the most different partners in the outing (at least 2).
- Welcome Wagon: partnered someone in their very first outing.
- Personal Best: more games than in any earlier outing, and at least PERSONAL_BEST_MIN.
- Close Call: won a game by exactly CLOSE_CALL_MARGIN points.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

from popshot_api.rating import PlayedMatch
from popshot_api.stats import weeks_in_a_row

OUTING_GAP = timedelta(hours=3)
ALWAYS_THERE_WEEKS = 4
PERSONAL_BEST_MIN = 3
CLOSE_CALL_MARGIN = 2

AwardKind = Literal["always_there", "great_partner", "welcome_wagon", "personal_best", "close_call"]
AWARD_ORDER: tuple[AwardKind, ...] = (
    "always_there",
    "great_partner",
    "welcome_wagon",
    "personal_best",
    "close_call",
)


@dataclass(frozen=True, slots=True)
class Outing:
    matches: tuple[PlayedMatch, ...]  # oldest first

    @property
    def key(self) -> UUID:
        return self.matches[0].id

    @property
    def start(self) -> datetime:
        return self.matches[0].played_at

    @property
    def end(self) -> datetime:
        return self.matches[-1].played_at


@dataclass(frozen=True, slots=True)
class Award:
    kind: AwardKind
    players: tuple[UUID, ...]
    # What it's for: weeks in a row, partners won with, games played, or close games won.
    value: int


@dataclass(frozen=True, slots=True)
class Recap:
    outing: Outing
    # Everyone who played, most games first.
    players: tuple[tuple[UUID, int], ...]
    newcomers: tuple[UUID, ...]
    awards: tuple[Award, ...]


def _in_order(matches: Iterable[PlayedMatch]) -> list[PlayedMatch]:
    return sorted(matches, key=lambda m: (m.played_at, str(m.id)))


def outings(matches: Iterable[PlayedMatch]) -> list[Outing]:
    """All of a crew's outings, oldest first."""
    found: list[list[PlayedMatch]] = []
    for match in _in_order(matches):
        if found and match.played_at - found[-1][-1].played_at <= OUTING_GAP:
            found[-1].append(match)
        else:
            found.append([match])
    return [Outing(tuple(group)) for group in found]


def _players(match: PlayedMatch) -> tuple[UUID, ...]:
    return (*match.team_a, *match.team_b)


def _games_by_player(matches: Iterable[PlayedMatch]) -> dict[UUID, int]:
    counts: dict[UUID, int] = {}
    for match in matches:
        for pid in _players(match):
            counts[pid] = counts.get(pid, 0) + 1
    return counts


def _sorted(players: Iterable[UUID]) -> tuple[UUID, ...]:
    return tuple(sorted(set(players), key=str))


def _always_there(here: set[UUID], runs: dict[UUID, int]) -> list[Award]:
    regulars = [pid for pid in here if runs.get(pid, 0) >= ALWAYS_THERE_WEEKS]
    if not regulars:
        return []
    return [Award("always_there", _sorted(regulars), max(runs[pid] for pid in regulars))]


def _great_partner(matches: Iterable[PlayedMatch]) -> list[Award]:
    won_with: dict[UUID, set[UUID]] = {}
    for match in matches:
        winners = match.team_a if match.winner == "A" else match.team_b
        if len(winners) == 2:
            first, second = winners
            won_with.setdefault(first, set()).add(second)
            won_with.setdefault(second, set()).add(first)
    most = max((len(partners) for partners in won_with.values()), default=0)
    if most < 2:
        return []
    best = [pid for pid, partners in won_with.items() if len(partners) == most]
    return [Award("great_partner", _sorted(best), most)]


def _welcome_wagon(matches: Iterable[PlayedMatch], newcomers: tuple[UUID, ...]) -> list[Award]:
    welcomers: set[UUID] = set()
    for match in matches:
        for team in (match.team_a, match.team_b):
            if any(pid in newcomers for pid in team):
                welcomers.update(pid for pid in team if pid not in newcomers)
    return [Award("welcome_wagon", _sorted(welcomers), len(newcomers))] if welcomers else []


def _personal_bests(here: dict[UUID, int], earlier: Sequence[Outing]) -> list[Award]:
    best_before: dict[UUID, int] = {}
    for o in earlier:
        for pid, n in _games_by_player(o.matches).items():
            best_before[pid] = max(best_before.get(pid, 0), n)
    return [
        Award("personal_best", (pid,), n)
        for pid, n in sorted(here.items(), key=lambda item: (-item[1], str(item[0])))
        if pid in best_before and n >= PERSONAL_BEST_MIN and n > best_before[pid]
    ]


def _close_call(matches: Iterable[PlayedMatch]) -> list[Award]:
    winners: set[UUID] = set()
    close_games = 0
    for match in matches:
        for game in match.games:
            if abs(game.team_a - game.team_b) == CLOSE_CALL_MARGIN:
                close_games += 1
                winners.update(match.team_a if game.team_a > game.team_b else match.team_b)
    return [Award("close_call", _sorted(winners), close_games)] if winners else []


def recap(outing: Outing, earlier: Sequence[Outing]) -> Recap:
    """What happened in `outing`, given every outing before it (oldest first)."""
    here = _games_by_player(outing.matches)
    before = [m for o in earlier for m in o.matches]
    seen_before = set(_games_by_player(before))
    newcomers = _sorted(pid for pid in here if pid not in seen_before)
    runs = weeks_in_a_row([*before, *outing.matches], outing.end)
    awards = [
        *_always_there(set(here), runs),
        *_great_partner(outing.matches),
        *_welcome_wagon(outing.matches, newcomers),
        *_personal_bests(here, earlier),
        *_close_call(outing.matches),
    ]
    players = tuple(sorted(here.items(), key=lambda item: (-item[1], str(item[0]))))
    return Recap(outing=outing, players=players, newcomers=newcomers, awards=tuple(awards))


def find(all_outings: Sequence[Outing], key: UUID) -> tuple[Outing, list[Outing]] | None:
    """The outing with `key` and the outings before it, or None."""
    for i, outing in enumerate(all_outings):
        if outing.key == key:
            return outing, list(all_outings[:i])
    return None
