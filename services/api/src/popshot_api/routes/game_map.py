"""Your game map on You (docs/game-map.md, popshot_api.game_map), and your weekly games goal.

Worked out from your own games in the crews you're in, on each read. Only you see it: every
query is about the signed-in player. While 'you.map' is off for you, these routes don't
exist (404).
"""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from popshot_api import game_map
from popshot_api.db import CurrentUserSession
from popshot_api.routes.board import group_matches, group_ratings
from popshot_api.routes.stats import PlayerRef, _players

router = APIRouter(prefix="/v1/me/map")

FEATURE = "you.map"
NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found.")
MAX_WEEKS = 26

WeeklyGames = Annotated[int, Field(ge=game_map.GOAL_RANGE[0], le=game_map.GOAL_RANGE[1])]


class PointOut(BaseModel):
    ending: datetime
    games: int
    per_week: float
    # None with fewer than min_games games in the window.
    form: float | None
    box: game_map.Box | None


class CrewOut(BaseModel):
    group_id: UUID
    name: str


class PartnerOut(BaseModel):
    group_id: UUID
    player: PlayerRef
    games: int


class GameMap(BaseModel):
    goal: int
    # False while you're on the default goal.
    goal_set: bool
    min_games: int = game_map.MIN_GAMES
    window_days: int = game_map.WINDOW.days
    # Oldest first; the last is now.
    points: list[PointOut]
    # What you can slice by: your crews, and partners with at least min_games games together.
    crews: list[CrewOut]
    partners: list[PartnerOut]


class Goal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weekly_games: WeeklyGames


def _require_map(session: Session) -> None:
    on: bool = session.execute(
        text("SELECT app_feature_on_for_me(:key)"), {"key": FEATURE}
    ).scalar_one()
    if not on:
        raise NOT_FOUND


def _goal(session: Session, me: UUID) -> int | None:
    found: int | None = session.execute(
        text("SELECT weekly_games FROM play_goals WHERE user_id = :me"), {"me": me}
    ).scalar_one_or_none()
    return found


def my_games(
    session: Session, me: UUID
) -> tuple[list[game_map.MyGame], list[CrewOut], list[PartnerOut]]:
    """Every game you've played in the crews you're an active member of."""
    crews = session.execute(
        text(
            """
            SELECT p.id AS player_id, g.id AS group_id, g.name
            FROM players p
            JOIN group_members m ON m.group_id = p.group_id AND m.user_id = :me
                                AND m.status = 'active'
            JOIN groups g ON g.id = p.group_id AND g.deleted_at IS NULL
            WHERE p.user_id = :me
            ORDER BY lower(g.name), g.id
            """
        ),
        {"me": me},
    ).all()
    games: list[game_map.MyGame] = []
    partners: list[PartnerOut] = []
    for crew in crews:
        matches = group_matches(session, crew.group_id)
        edges: dict[UUID, float] = {}
        group_ratings(session, crew.group_id, matches, edges=edges)
        together: dict[UUID, int] = {}
        for match in matches:
            for team, sign in ((match.team_a, 1.0), (match.team_b, -1.0)):
                if crew.player_id in team:
                    mates = frozenset(team) - {crew.player_id}
                    games.append(
                        game_map.MyGame(
                            match.played_at, crew.group_id, sign * edges[match.id], mates
                        )
                    )
                    for mate in mates:
                        together[mate] = together.get(mate, 0) + 1
        often = {pid: n for pid, n in together.items() if n >= game_map.MIN_GAMES}
        if often:
            names = _players(session, crew.group_id)
            partners += [
                PartnerOut(group_id=crew.group_id, player=names[pid], games=n)
                for pid, n in sorted(often.items(), key=lambda kv: (-kv[1], str(kv[0])))
                if pid in names
            ]
    listed = [CrewOut(group_id=c.group_id, name=c.name) for c in crews]
    return games, listed, partners


@router.get("")
def get_map(
    user: CurrentUserSession,
    weeks: Annotated[int, Query(ge=1, le=MAX_WEEKS)] = 6,
    crew: UUID | None = None,
    partner: UUID | None = None,
    format: game_map.Format | None = None,
) -> GameMap:
    session, me = user.session, user.user_id
    _require_map(session)
    stored = _goal(session, me)
    goal = stored if stored is not None else game_map.DEFAULT_GOAL
    games, crews, partners = my_games(session, me)
    chosen = game_map.sliced(games, crew=crew, partner=partner, format=format)
    points = [
        PointOut(
            ending=p.ending,
            games=p.games,
            per_week=round(p.per_week, 2),
            form=None if p.form is None else round(p.form, 3),
            box=game_map.box(p, goal),
        )
        for p in game_map.trail(chosen, datetime.now(UTC), weeks)
    ]
    return GameMap(
        goal=goal, goal_set=stored is not None, points=points, crews=crews, partners=partners
    )


@router.put("/goal")
def set_goal(body: Goal, user: CurrentUserSession) -> Goal:
    """Your weekly games goal: the middle line of your map's rhythm."""
    session, me = user.session, user.user_id
    _require_map(session)
    session.execute(
        text(
            """
            INSERT INTO play_goals (user_id, weekly_games) VALUES (:me, :n)
            ON CONFLICT (user_id) DO UPDATE SET weekly_games = EXCLUDED.weekly_games,
                                                updated_at = now()
            """
        ),
        {"me": me, "n": body.weekly_games},
    )
    return body
