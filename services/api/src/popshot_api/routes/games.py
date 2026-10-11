"""Players (members and guests) and logging games.

Any active member can add a guest and log a game, whether or not they played in it. A game
counts as soon as it's logged; there's no confirmation step. Whoever logged a game can fix
it (edit) or delete it.

Errors follow groups.py: a group you can't see is a 404.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from sqlalchemy import text
from sqlalchemy.orm import Session

from popshot_api.db import CurrentUserSession
from popshot_api.push import Message
from popshot_api.routes.groups import NOT_FOUND, Format, PersonName
from popshot_api.routes.notifications import CurrentNotifier, Notifier
from popshot_api.scoring import GameRules, ScoreError, validate_match

router = APIRouter(prefix="/v1/groups/{group_id}")

# Guests per group. Generous for a crew, and stops a script from filling the roster.
MAX_GUESTS = 100
# Games logged per group per day. Far beyond any real session.
MAX_GAMES_PER_DAY = 200
# A game can be logged up to this long after it was played.
MAX_LOG_DELAY = timedelta(days=30)
# Clock slack between the phone and the server.
CLOCK_SLACK = timedelta(minutes=10)
GAMES_SHOWN = 50

TEAM_SIZE: dict[str, int] = {"doubles": 2, "singles": 1}

MATCH_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, detail="We couldn't find that game.")


class Player(BaseModel):
    id: UUID
    display_name: str
    avatar_url: str | None
    # None for a guest who hasn't signed up.
    user_id: UUID | None
    is_guest: bool
    is_me: bool


class NewGuest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: PersonName


class GameScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team_a: StrictInt
    team_b: StrictInt


class LogGame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Format
    points_to: Literal[11, 15, 21]
    win_by_two: bool
    best_of: Literal[1, 3]
    # When it was played; defaults to now.
    played_at: datetime | None = None
    team_a: Annotated[list[UUID], Field(min_length=1, max_length=2)]
    team_b: Annotated[list[UUID], Field(min_length=1, max_length=2)]
    games: Annotated[list[GameScore], Field(min_length=1, max_length=3)]


class MatchPlayer(BaseModel):
    player_id: UUID
    display_name: str
    is_guest: bool
    team: Literal["A", "B"]


class MyReflection(BaseModel):
    went_well: list[str]
    to_improve: list[str]


class Match(BaseModel):
    id: UUID
    format: Format
    points_to: int
    win_by_two: bool
    best_of: int
    played_at: datetime
    entered_by_name: str | None
    entered_by_me: bool
    winner: Literal["A", "B"]
    players: list[MatchPlayer]
    games: list[GameScore]
    # Whether you played in it, and your own reflection on it (nobody else's is ever sent).
    i_played: bool = False
    my_reflection: MyReflection | None = None
    # Whoever logged a game can edit or delete it.
    can_edit: bool = False


def _require_member(session: Session, me: UUID, group_id: UUID) -> None:
    found = session.execute(
        text(
            "SELECT 1 FROM group_members "
            "JOIN groups ON groups.id = group_members.group_id "
            "WHERE group_id = :group_id AND user_id = :me AND status = 'active'"
        ),
        {"group_id": group_id, "me": me},
    ).scalar_one_or_none()
    if found is None:
        raise NOT_FOUND


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


# Players you can put in a game: guests, and members who are still active. Removed members
# keep their player rows (their games stay on the record) but aren't offered. The same
# condition appears in each query below.
_LIST_PLAYERS = """
    SELECT p.id, p.display_name, u.avatar_url, p.user_id, p.user_id IS NULL AS is_guest,
           p.user_id IS NOT DISTINCT FROM :me AS is_me
    FROM players p
    LEFT JOIN group_members gm ON gm.group_id = p.group_id AND gm.user_id = p.user_id
    LEFT JOIN users u ON u.id = p.user_id
    WHERE p.group_id = :group_id AND (p.user_id IS NULL OR gm.status = 'active')
    ORDER BY p.user_id IS NOT DISTINCT FROM :me DESC, p.user_id IS NULL,
             lower(p.display_name), p.id
"""
_NAME_TAKEN = """
    SELECT 1 FROM players p
    LEFT JOIN group_members gm ON gm.group_id = p.group_id AND gm.user_id = p.user_id
    WHERE p.group_id = :group_id AND (p.user_id IS NULL OR gm.status = 'active')
      AND lower(p.display_name) = lower(:name)
    LIMIT 1
"""
_PLAYABLE_IDS = """
    SELECT p.id FROM players p
    LEFT JOIN group_members gm ON gm.group_id = p.group_id AND gm.user_id = p.user_id
    WHERE p.group_id = :group_id AND (p.user_id IS NULL OR gm.status = 'active')
      AND p.id = ANY(:ids)
"""


@router.get("/players")
def list_players(group_id: UUID, user: CurrentUserSession) -> list[Player]:
    _require_member(user.session, user.user_id, group_id)
    rows = user.session.execute(
        text(_LIST_PLAYERS), {"group_id": group_id, "me": user.user_id}
    ).mappings()
    return [Player(**row) for row in rows]


@router.post("/players", status_code=status.HTTP_201_CREATED)
def add_guest(group_id: UUID, body: NewGuest, user: CurrentUserSession) -> Player:
    session, me = user.session, user.user_id
    _require_member(session, me, group_id)
    clash = session.execute(
        text(_NAME_TAKEN), {"group_id": group_id, "name": body.display_name}
    ).scalar_one_or_none()
    if clash is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"There's already a player called {body.display_name}. Pick them instead.",
        )
    guests = session.execute(
        text("SELECT count(*) FROM players WHERE group_id = :group_id AND user_id IS NULL"),
        {"group_id": group_id},
    ).scalar_one()
    if guests >= MAX_GUESTS:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"A group can have up to {MAX_GUESTS} guests."
        )
    player_id: UUID = session.execute(
        text("INSERT INTO players (group_id, display_name) VALUES (:group_id, :name) RETURNING id"),
        {"group_id": group_id, "name": body.display_name},
    ).scalar_one()
    session.execute(
        text(
            "INSERT INTO audit_log (group_id, actor_user_id, action, target_id) "
            "VALUES (:group_id, :me, 'player.guest_added', :player)"
        ),
        {"group_id": group_id, "me": me, "player": player_id},
    )
    return Player(
        id=player_id,
        display_name=body.display_name,
        avatar_url=None,
        user_id=None,
        is_guest=True,
        is_me=False,
    )


def _played_at(value: datetime | None, now: datetime, keep: datetime | None = None) -> datetime:
    """When the game was played: as given (checked), else `keep` (when editing), else now."""
    if value is None:
        return keep or now
    if value.tzinfo is None:
        raise _unprocessable("Include a time zone with the time it was played.")
    if value > now + CLOCK_SLACK:
        raise _unprocessable("That time is in the future.")
    if value < now - MAX_LOG_DELAY:
        raise _unprocessable("Games can be logged up to 30 days after they were played.")
    return value


def _check_game(
    session: Session, group_id: UUID, body: LogGame, keep_played_at: datetime | None = None
) -> datetime:
    """Validate a game being logged or edited; return when it was played."""
    size = TEAM_SIZE[body.format]
    if len(body.team_a) != size or len(body.team_b) != size:
        raise _unprocessable(
            "Doubles needs two players on each team."
            if size == 2
            else "Singles needs one player on each side."
        )
    everyone = [*body.team_a, *body.team_b]
    if len(set(everyone)) != len(everyone):
        raise _unprocessable("Each player can only be in a game once.")
    try:
        validate_match(
            GameRules(body.points_to, body.win_by_two),
            body.best_of,
            [(g.team_a, g.team_b) for g in body.games],
        )
    except ScoreError as error:
        raise _unprocessable(str(error)) from error

    played_at = _played_at(body.played_at, datetime.now(UTC), keep_played_at)

    found = session.execute(text(_PLAYABLE_IDS), {"group_id": group_id, "ids": everyone}).scalars()
    if set(found) != set(everyone):
        raise _unprocessable("Some of those players aren't in this group.")
    return played_at


def _write_lineup(session: Session, group_id: UUID, match_id: UUID, body: LogGame) -> None:
    session.execute(
        text(
            "INSERT INTO match_players (match_id, group_id, player_id, team) "
            "VALUES (:match_id, :group_id, :player_id, CAST(:team AS team_side))"
        ),
        [
            {"match_id": match_id, "group_id": group_id, "player_id": p, "team": team}
            for team, players in (("A", body.team_a), ("B", body.team_b))
            for p in players
        ],
    )
    session.execute(
        text(
            "INSERT INTO match_games (match_id, group_id, game_number, team_a_score, "
            "team_b_score) VALUES (:match_id, :group_id, :number, :a, :b)"
        ),
        [
            {"match_id": match_id, "group_id": group_id, "number": n, "a": g.team_a, "b": g.team_b}
            for n, g in enumerate(body.games, start=1)
        ],
    )


def _audit(session: Session, group_id: UUID, me: UUID, action: str, match_id: UUID) -> None:
    session.execute(
        text(
            "INSERT INTO audit_log (group_id, actor_user_id, action, target_id) "
            "VALUES (:group_id, :me, :action, :match_id)"
        ),
        {"group_id": group_id, "me": me, "action": action, "match_id": match_id},
    )


@router.post("/matches", status_code=status.HTTP_201_CREATED)
def log_game(
    group_id: UUID, body: LogGame, user: CurrentUserSession, notifier: CurrentNotifier
) -> Match:
    session, me = user.session, user.user_id
    _require_member(session, me, group_id)
    played_at = _check_game(session, group_id, body)

    today = session.execute(
        text(
            "SELECT count(*) FROM matches "
            "WHERE group_id = :group_id AND created_at > now() - interval '1 day'"
        ),
        {"group_id": group_id},
    ).scalar_one()
    if today >= MAX_GAMES_PER_DAY:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"This group has logged {MAX_GAMES_PER_DAY} games today. Try again tomorrow.",
        )

    match_id: UUID = session.execute(
        text(
            """
            INSERT INTO matches (group_id, format, points_to, win_by_two, best_of, played_at,
                                 entered_by)
            VALUES (:group_id, CAST(:format AS match_format), :points_to, :win_by_two,
                    :best_of, :played_at, :me)
            RETURNING id
            """
        ),
        {
            "group_id": group_id,
            "format": body.format,
            "points_to": body.points_to,
            "win_by_two": body.win_by_two,
            "best_of": body.best_of,
            "played_at": played_at,
            "me": me,
        },
    ).scalar_one()
    _write_lineup(session, group_id, match_id, body)
    _audit(session, group_id, me, "match.logged", match_id)
    game = _matches(session, me, group_id, match_id=match_id)[0]
    _tell_players(session, notifier, game, me)
    return game


def _tell_players(session: Session, notifier: Notifier, game: Match, me: UUID) -> None:
    """Let the members who played know (not guests, not whoever logged it). No score in the
    message: it shows on lock screens."""
    rows = session.execute(
        text(
            """
            SELECT p.user_id, p.display_name FROM match_players mp
            JOIN players p ON p.id = mp.player_id AND p.group_id = mp.group_id
            WHERE mp.match_id = :match_id AND p.user_id IS NOT NULL
            """
        ),
        {"match_id": game.id},
    ).all()
    logger = session.execute(
        text("SELECT display_name FROM users WHERE id = :me"), {"me": me}
    ).scalar_one()
    notifier.notify(
        session,
        [r.user_id for r in rows if r.user_id != me],
        "games",
        Message(
            title=f"{logger} logged a game you played",
            body="Tap to see how it went.",
            url="/games",
            tag=f"game-{game.id}",
        ),
    )


@router.get("/matches")
def list_games(group_id: UUID, user: CurrentUserSession) -> list[Match]:
    _require_member(user.session, user.user_id, group_id)
    return _matches(user.session, user.user_id, group_id)


@router.get("/matches/{match_id}")
def get_game(group_id: UUID, match_id: UUID, user: CurrentUserSession) -> Match:
    _require_member(user.session, user.user_id, group_id)
    found = _matches(user.session, user.user_id, group_id, match_id=match_id)
    if not found:
        raise MATCH_NOT_FOUND
    return found[0]


def _own_game(session: Session, me: UUID, group_id: UUID, match_id: UUID) -> datetime:
    """Lock a game you logged; return when it was played. 404 if missing, 403 if not yours."""
    row = session.execute(
        text(
            "SELECT entered_by, played_at FROM matches "
            "WHERE id = :match_id AND group_id = :group_id FOR UPDATE"
        ),
        {"match_id": match_id, "group_id": group_id},
    ).one_or_none()
    if row is None:
        raise MATCH_NOT_FOUND
    if row.entered_by != me:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Only the person who logged a game can change or delete it.",
        )
    played_at: datetime = row.played_at
    return played_at


@router.put("/matches/{match_id}")
def edit_game(group_id: UUID, match_id: UUID, body: LogGame, user: CurrentUserSession) -> Match:
    """Fix a game you logged: players, rules and scores. Leave played_at out to keep it."""
    session, me = user.session, user.user_id
    _require_member(session, me, group_id)
    kept = _own_game(session, me, group_id, match_id)
    played_at = _check_game(session, group_id, body, keep_played_at=kept)
    params = {"match_id": match_id, "group_id": group_id}
    session.execute(text("DELETE FROM match_players WHERE match_id = :match_id"), params)
    session.execute(text("DELETE FROM match_games WHERE match_id = :match_id"), params)
    _write_lineup(session, group_id, match_id, body)
    session.execute(
        text(
            """
            UPDATE matches
            SET format = CAST(:format AS match_format), points_to = :points_to,
                win_by_two = :win_by_two, best_of = :best_of, played_at = :played_at
            WHERE id = :match_id AND group_id = :group_id
            """
        ),
        {
            **params,
            "format": body.format,
            "points_to": body.points_to,
            "win_by_two": body.win_by_two,
            "best_of": body.best_of,
            "played_at": played_at,
        },
    )
    _audit(session, group_id, me, "match.edited", match_id)
    return _matches(session, me, group_id, match_id=match_id)[0]


@router.delete("/matches/{match_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_game(group_id: UUID, match_id: UUID, user: CurrentUserSession) -> Response:
    session, me = user.session, user.user_id
    _require_member(session, me, group_id)
    _own_game(session, me, group_id, match_id)
    session.execute(
        text("DELETE FROM matches WHERE id = :match_id AND group_id = :group_id"),
        {"match_id": match_id, "group_id": group_id},
    )
    _audit(session, group_id, me, "match.deleted", match_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _matches(
    session: Session, me: UUID, group_id: UUID, match_id: UUID | None = None
) -> list[Match]:
    rows = session.execute(
        text(
            """
            SELECT m.id, m.format, m.points_to, m.win_by_two, m.best_of, m.played_at,
                   u.display_name AS entered_by_name, m.entered_by = :me AS entered_by_me,
                   (SELECT json_agg(json_build_object(
                               'player_id', p.id, 'display_name', p.display_name,
                               'is_guest', p.user_id IS NULL, 'team', mp.team)
                           ORDER BY mp.team, lower(p.display_name), p.id)
                    FROM match_players mp JOIN players p ON p.id = mp.player_id
                    WHERE mp.match_id = m.id) AS players,
                   (SELECT json_agg(json_build_object(
                               'team_a', g.team_a_score, 'team_b', g.team_b_score)
                           ORDER BY g.game_number)
                    FROM match_games g WHERE g.match_id = m.id) AS games,
                   EXISTS (SELECT 1 FROM match_players mp JOIN players p ON p.id = mp.player_id
                           WHERE mp.match_id = m.id AND p.user_id = :me) AS i_played,
                   CASE WHEN r.match_id IS NOT NULL THEN json_build_object(
                       'went_well', r.went_well, 'to_improve', r.to_improve) END
                       AS my_reflection
            FROM matches m
            LEFT JOIN users u ON u.id = m.entered_by
            LEFT JOIN match_reflections r ON r.match_id = m.id AND r.user_id = :me
            WHERE m.group_id = :group_id AND (CAST(:match_id AS uuid) IS NULL OR m.id = :match_id)
            ORDER BY m.played_at DESC, m.id
            LIMIT :limit
            """
        ),
        {"group_id": group_id, "me": me, "match_id": match_id, "limit": GAMES_SHOWN},
    ).mappings()
    matches = []
    for row in rows:
        games = [GameScore(**g) for g in row["games"] or []]
        wins_a = sum(1 for g in games if g.team_a > g.team_b)
        winner: Literal["A", "B"] = "A" if wins_a * 2 > len(games) else "B"
        matches.append(
            Match(
                **{**row, "players": row["players"] or [], "games": games, "winner": winner},
                can_edit=row["entered_by_me"],
            )
        )
    return matches
