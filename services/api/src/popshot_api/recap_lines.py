"""Popshot's own commentator: a headline and a few lines for a recap, from its facts only.

Every line was written to be friendly to everyone: it celebrates, never mocks, and doesn't
refer to anyone as he or she. Lines are picked by the day's key, so a recap reads the same
every time it's opened, and different days get different lines.

(The AI commentator, when it's on, falls back to these.)
"""

import random
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from popshot_api.recap import AwardKind, Recap

MAX_LINES = 3
NAMES_SHOWN = 3

# {games}, {players}, {crew}, {at} (" at Riverside courts" or "").
HEADLINES = [
    "{games} games{at}. Paddles down, smiles up.",
    "{crew} was on court{at}: {games} games, {players} players.",
    "Paddles up! {games} games for {crew}{at}.",
    "{players} players, {games} games, zero regrets{at}.",
    "{games} games of dinks, drops and good company{at}.",
]
ONE_GAME = [
    "One game{at}. It still counts!",
    "A quick one for {crew}{at}: one game, on the record.",
]

# Keyed by award kind: ONE when the award is one person's, MANY when it's shared.
# {names}, {n}.
ONE: dict[AwardKind, list[str]] = {
    "always_there": [
        "{names} makes it {n} weeks in a row. The courts know that name by now.",
        "{n} weeks running for {names}. Reliable as a third-shot drop.",
    ],
    "great_partner": [
        "{names} won with {n} different partners. Everyone's favourite teammate.",
        "{n} partners, {n} kinds of chemistry: {names} plays well with everyone.",
    ],
    "welcome_wagon": [
        "Big thanks to {names} for partnering a first-timer.",
        "{names} rolled out the welcome mat for a new player.",
    ],
    "personal_best": [
        "{names} played {n} games, a personal best. Somebody get {names} some water!",
        "New record for {names}: {n} games in one day.",
    ],
    "close_call": [
        "{names} won one by a point or two. Nerves of steel.",
        "A point or two in it: {names} kept cool when it counted.",
    ],
}
MANY: dict[AwardKind, list[str]] = {
    "always_there": [
        "{names}: {n} weeks in a row and counting. The heart of the crew.",
        "Every week for {n} weeks: {names}. Showing up is half the game.",
    ],
    "great_partner": [
        "{names} each won with {n} different partners. Great teammates all round.",
    ],
    "welcome_wagon": [
        "Thanks to {names} for partnering the new faces.",
        "{names} made the newcomers feel right at home.",
    ],
    "personal_best": [],  # one award per person
    "close_call": [
        "Down-to-the-wire wins for {names}. Nerves of steel!",
        "A point or two in it: {names}. That's how you finish a rally.",
    ],
}
# {names} are the first-timers.
WELCOME_ONE = [
    "Welcome to the crew, {names}! First games in the books.",
    "First time on court with the crew for {names}. Welcome!",
]
WELCOME_MANY = [
    "Welcome to the crew, {names}! First games in the books.",
    "New faces on court: welcome, {names}!",
]
QUIET = [
    "Good games, good people, good dinks.",
    "Every game logged is a story for later.",
    "See you at the kitchen line next time.",
]


@dataclass(frozen=True, slots=True)
class Commentary:
    headline: str
    lines: tuple[str, ...]


def first_name(display_name: str) -> str:
    parts = display_name.split(maxsplit=1)
    return parts[0] if parts else display_name


def join_names(names: Sequence[str], most: int = NAMES_SHOWN) -> str:
    """ "Jo", "Jo and Sam", "Jo, Sam and Pat", "Jo, Sam, Pat and 2 more".

    Never "and 1 more": one extra name is shorter than saying so.
    """
    if len(names) > most + 1:
        return f"{', '.join(names[:most])} and {len(names) - most} more"
    if len(names) <= 1:
        return names[0] if names else ""
    return f"{', '.join(names[:-1])} and {names[-1]}"


def commentary(
    recap: Recap,
    display_names: Mapping[UUID, str],
    crew: str,
    venue: str | None,
    hidden: Collection[UUID] = frozenset(),
) -> Commentary:
    """`hidden`: people not to name (on shared cards). Lines say "Ana and 1 more" instead,
    and a line about only hidden people is left out."""
    # Not for security: picks the same lines for the same outing every time.
    rng = random.Random(recap.outing.key.int)  # noqa: S311
    games = len(recap.outing.matches)
    facts = {
        "games": games,
        "players": len(recap.players),
        "crew": crew,
        "at": f" at {venue}" if venue else "",
    }
    headline = rng.choice(ONE_GAME if games == 1 else HEADLINES).format(**facts)

    def names(ids: Sequence[UUID]) -> str:
        if not hidden:
            return join_names([first_name(display_names[pid]) for pid in ids])
        shown = [first_name(display_names[pid]) for pid in ids if pid not in hidden]
        shown = shown[:NAMES_SHOWN]
        more = len(ids) - len(shown)
        if not shown or not more:
            return join_names(shown)
        return f"{', '.join(shown)} and {more} more"

    lines: list[str] = []
    if recap.newcomers and (who := names(recap.newcomers)):
        pool = WELCOME_ONE if len(recap.newcomers) == 1 else WELCOME_MANY
        lines.append(rng.choice(pool).format(names=who))
    for award in recap.awards:
        if len(lines) >= MAX_LINES:
            break
        pool = ONE[award.kind] if len(award.players) == 1 else MANY[award.kind]
        if pool and (who := names(award.players)):
            lines.append(rng.choice(pool).format(names=who, n=award.value))
    if not lines:
        lines.append(rng.choice(QUIET))
    return Commentary(headline=headline, lines=tuple(lines))
