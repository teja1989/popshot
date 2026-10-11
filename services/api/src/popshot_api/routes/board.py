"""Crew points and the Board.

Ratings aren't stored: each read replays the group's games (see popshot_api.rating), which
is fast at crew scale and can never drift from an edited or deleted game.

The Board has three sections:
- ranked: RANKED_AFTER games or more, and a game within RESTING_AFTER. Guests included.
- getting_started: fewer games than that (members with none yet appear here too).
- resting: ranked once, but no games for RESTING_AFTER. Their rating is kept.
People who have left the group still count in everyone's history but aren't listed.
"""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.orm import Session

from popshot_api.db import CurrentUserSession
from popshot_api.rating import (
    FORM_LENGTH,
    LEVEL_START,
    RANKED_AFTER,
    RESTING_AFTER,
    GameScore,
    PlayedMatch,
    PlayerRating,
    reliability,
    replay,
    week_change,
)
from popshot_api.routes.games import _require_member

router = APIRouter(prefix="/v1")

Level = Literal["beginner", "intermediate", "advanced", "expert"]


class BoardRow(BaseModel):
    player_id: UUID
    display_name: str
    avatar_url: str | None
    is_guest: bool
    is_me: bool
    rating: float
    reliability: int
    matches: int
    wins: int
    form: list[Literal["W", "L"]]
    week_change: float | None
    rank: int | None = None
    # Games still needed to be ranked (getting started only).
    to_go: int = 0


class Board(BaseModel):
    ranked: list[BoardRow]
    getting_started: list[BoardRow]
    resting: list[BoardRow]
    ranked_after: int = RANKED_AFTER
    resting_after_days: int = RESTING_AFTER.days


class MyRating(BaseModel):
    group_id: UUID
    group_name: str
    rating: float
    matches: int
    rank: int | None
    ranked_of: int
    to_go: int


class LevelBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: Level | None


def group_matches(session: Session, group_id: UUID) -> list[PlayedMatch]:
    rows = session.execute(
        text(
            """
            SELECT m.id, m.played_at,
                   (SELECT array_agg(mp.player_id ORDER BY mp.player_id)
                    FROM match_players mp WHERE mp.match_id = m.id AND mp.team = 'A') AS team_a,
                   (SELECT array_agg(mp.player_id ORDER BY mp.player_id)
                    FROM match_players mp WHERE mp.match_id = m.id AND mp.team = 'B') AS team_b,
                   (SELECT json_agg(json_build_array(g.team_a_score, g.team_b_score)
                                    ORDER BY g.game_number)
                    FROM match_games g WHERE g.match_id = m.id) AS games
            FROM matches m WHERE m.group_id = :group_id
            """
        ),
        {"group_id": group_id},
    ).all()
    return [
        PlayedMatch(
            id=row.id,
            played_at=row.played_at,
            team_a=row.team_a or [],
            team_b=row.team_b or [],
            games=[GameScore(a, b) for a, b in row.games or []],
        )
        for row in rows
        if row.team_a and row.team_b
    ]


def group_ratings(session: Session, group_id: UUID) -> dict[UUID, PlayerRating]:
    starts = {
        row.player_id: LEVEL_START[row.self_level]
        for row in session.execute(
            text("SELECT * FROM app_group_levels(:group_id)"), {"group_id": group_id}
        )
        if row.self_level in LEVEL_START
    }
    return replay(group_matches(session, group_id), starts)


def build_board(session: Session, me: UUID, group_id: UUID, now: datetime) -> Board:
    rated = group_ratings(session, group_id)
    # Listed players: guests, and members who are still active.
    listed = session.execute(
        text(
            """
            SELECT p.id, p.display_name, u.avatar_url, p.user_id IS NULL AS is_guest,
                   p.user_id IS NOT DISTINCT FROM :me AS is_me
            FROM players p
            LEFT JOIN group_members gm ON gm.group_id = p.group_id AND gm.user_id = p.user_id
            LEFT JOIN users u ON u.id = p.user_id
            WHERE p.group_id = :group_id AND (p.user_id IS NULL OR gm.status = 'active')
            """
        ),
        {"group_id": group_id, "me": me},
    ).all()

    ranked: list[BoardRow] = []
    starting: list[BoardRow] = []
    resting: list[BoardRow] = []
    for p in listed:
        r = rated.get(p.id)
        if r is None and p.is_guest:
            continue  # a guest who never played
        matches = r.matches if r else 0
        row = BoardRow(
            player_id=p.id,
            display_name=p.display_name,
            avatar_url=p.avatar_url,
            is_guest=p.is_guest,
            is_me=p.is_me,
            rating=round(r.rating, 2) if r else 0.0,
            reliability=reliability(r, now) if r else 0,
            matches=matches,
            wins=r.wins if r else 0,
            form=(r.results[-FORM_LENGTH:][::-1] if r else []),
            week_change=_rounded(week_change(r, now)) if r else None,
            to_go=max(0, RANKED_AFTER - matches),
        )
        if r is not None and r.last_played is not None and matches >= RANKED_AFTER:
            (resting if now - r.last_played > RESTING_AFTER else ranked).append(row)
        else:
            starting.append(row)

    ranked.sort(key=lambda x: (-x.rating, -x.reliability, -x.matches, x.display_name.lower()))
    for position, row in enumerate(ranked, start=1):
        row.rank = position
    starting.sort(key=lambda x: (-x.matches, x.display_name.lower()))
    resting.sort(key=lambda x: (-x.rating, x.display_name.lower()))
    return Board(ranked=ranked, getting_started=starting, resting=resting)


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


@router.get("/groups/{group_id}/board")
def board(group_id: UUID, user: CurrentUserSession) -> Board:
    _require_member(user.session, user.user_id, group_id)
    return build_board(user.session, user.user_id, group_id, datetime.now(UTC))


@router.get("/me/ratings")
def my_ratings(user: CurrentUserSession) -> list[MyRating]:
    """Your crew points in each group you've played in, most games first."""
    session, me = user.session, user.user_id
    groups = session.execute(
        text(
            """
            SELECT g.id, g.name FROM group_members m JOIN groups g ON g.id = m.group_id
            WHERE m.user_id = :me AND m.status = 'active'
            """
        ),
        {"me": me},
    ).all()
    now = datetime.now(UTC)
    mine: list[MyRating] = []
    for group in groups:
        board_ = build_board(session, me, group.id, now)
        rows = [*board_.ranked, *board_.getting_started, *board_.resting]
        row = next((r for r in rows if r.is_me and r.matches > 0), None)
        if row is None:
            continue
        mine.append(
            MyRating(
                group_id=group.id,
                group_name=group.name,
                rating=row.rating,
                matches=row.matches,
                rank=row.rank,
                ranked_of=len(board_.ranked),
                to_go=row.to_go,
            )
        )
    return sorted(mine, key=lambda r: (-r.matches, r.group_name.lower()))


@router.put("/me/level")
def set_level(body: LevelBody, user: CurrentUserSession) -> LevelBody:
    """Your self-rated level: where your crew points start. Null to clear it."""
    user.session.execute(
        text("UPDATE users SET self_level = :level WHERE id = :me"),
        {"level": body.level, "me": user.user_id},
    )
    return body
