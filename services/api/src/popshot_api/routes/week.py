"""Your week (popshot_api.week): your last 7 days of games across your crews.

Runs as you, so it reads only crews you're an active member of, like everything else.
"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from popshot_api import week
from popshot_api.db import CurrentUserSession
from popshot_api.routes.board import group_matches

router = APIRouter(prefix="/v1")


class TopPartner(BaseModel):
    name: str
    games: int


class YourWeek(BaseModel):
    since: datetime
    until: datetime
    games: int
    wins: int
    close_games: int
    longest_win_streak: int
    crews: list[str]
    top_partner: TopPartner | None
    headline: str
    lines: list[str]


@router.get("/me/week")
def your_week(user: CurrentUserSession) -> YourWeek:
    session = user.session
    now = datetime.now(UTC)
    crews = session.execute(
        text(
            """
            SELECT g.id, g.name, p.id AS me
            FROM group_members m
            JOIN groups g ON g.id = m.group_id AND g.deleted_at IS NULL
            JOIN players p ON p.group_id = m.group_id AND p.user_id = m.user_id
            WHERE m.user_id = :me AND m.status = 'active'
            ORDER BY g.name
            """
        ),
        {"me": user.user_id},
    ).all()
    crew_weeks = []
    for crew in crews:
        matches = week.in_window(group_matches(session, crew.id), now)
        if not matches:
            continue
        rows = session.execute(
            text("SELECT id, display_name FROM players WHERE group_id = :g"), {"g": crew.id}
        ).all()
        names: dict[UUID, str] = {row.id: row.display_name for row in rows}
        crew_weeks.append(week.CrewWeek(crew=crew.name, me=crew.me, matches=matches, names=names))
    improve = session.execute(
        text("SELECT improve FROM user_focus WHERE user_id = :me"), {"me": user.user_id}
    ).scalar_one_or_none()
    summary = week.summarize(crew_weeks, list(improve or []))
    return YourWeek(
        since=now - week.WINDOW,
        until=now,
        games=summary.games,
        wins=summary.wins,
        close_games=summary.close_games,
        longest_win_streak=summary.longest_win_streak,
        crews=summary.crews,
        top_partner=(
            TopPartner(name=summary.top_partner[0], games=summary.top_partner[1])
            if summary.top_partner
            else None
        ),
        headline=summary.headline,
        lines=summary.lines,
    )
