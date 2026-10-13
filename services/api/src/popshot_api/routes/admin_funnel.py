"""The admin funnel (migration 0024): how new crews and people get going, where they came
from, and how the sharing loops are doing. Admin service only, behind the same check as the
other admin pages (routes/admin.py)."""

from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text

from popshot_api.db import CurrentUserSession
from popshot_api.routes.admin import record_view, require_admin

router = APIRouter(prefix="/v1/admin", dependencies=[Depends(require_admin)])

# How long a crew can go without a game before it counts as quiet.
QUIET_AFTER = timedelta(days=14)
# Crews listed by stage: those created in the last this many days.
STAGE_DAYS = 90


class CrewFunnel(BaseModel):
    created: int
    second_member: int
    first_game: int
    activated: int
    # Week 2 and week 4 only count crews old enough to have had them.
    week_2_eligible: int
    played_week_2: int
    week_4_eligible: int
    played_week_4: int
    median_hours_to_first_game: float | None


class PeopleFunnel(BaseModel):
    signed_up: int
    in_crew: int
    played: int
    week_2_eligible: int
    back_week_2: int


class SourceRow(BaseModel):
    source: str
    visits: int
    signed_up: int
    in_crew: int
    played: int


class Loops(BaseModel):
    recaps_shared: int
    share_views: int
    try_taps: int
    recap_signups: int
    invite_links: int
    link_joins: int
    direct_invites: int
    direct_accepted: int
    invite_signups: int
    code_signups: int
    # People who used the app in the period, to set the sign-ups above against.
    active_users: int


Stage = Literal[
    "deleted", "needs_member", "needs_first_game", "quiet", "activated", "getting_going"
]


class CrewStage(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    members: int
    games: int
    games_first_week: int
    first_game_at: datetime | None
    last_game_at: datetime | None
    stage: Stage


class WeekOfCrews(BaseModel):
    week_start: date
    active_crews: int


class Funnel(BaseModel):
    weeks: int
    since: datetime
    crews: CrewFunnel
    people: PeopleFunnel
    sources: list[SourceRow]
    loops: Loops
    stages: list[CrewStage]
    # Oldest first.
    active_crews: list[WeekOfCrews]


def stage_of(  # noqa: PLR0913  (one crew's numbers)
    *,
    deleted: bool,
    members: int,
    games: int,
    games_first_week: int,
    last_game_at: datetime | None,
    now: datetime,
) -> Stage:
    """Where a new crew is. Playing with guests only still counts as playing."""
    if deleted:
        return "deleted"
    if games == 0:
        return "needs_member" if members < 2 else "needs_first_game"
    if last_game_at is not None and now - last_game_at > QUIET_AFTER:
        return "quiet"
    if games_first_week >= 3:
        return "activated"
    return "getting_going"


@router.get("/funnel")
def funnel(
    user: CurrentUserSession,
    # 4, 8 or 12.
    weeks: Annotated[int, Query(ge=4, le=12, multiple_of=4)] = 4,
) -> Funnel:
    record_view(user, "funnel")
    session = user.session
    now = datetime.now(UTC)
    since = now - timedelta(weeks=weeks)
    window = {"since": since, "until": now}
    crews = session.execute(
        text("SELECT * FROM app_admin_funnel_crews(:since, :until)"), window
    ).one()
    people = session.execute(
        text("SELECT * FROM app_admin_funnel_people(:since, :until)"), window
    ).one()
    sources = session.execute(
        text("SELECT * FROM app_admin_funnel_sources(:since, :until)"), window
    ).all()
    loops = session.execute(
        text("SELECT * FROM app_admin_funnel_loops(:since, :until)"), window
    ).one()
    stages = session.execute(
        text("SELECT * FROM app_admin_crew_stages(:days)"), {"days": STAGE_DAYS}
    ).all()
    weekly = session.execute(text("SELECT * FROM app_metrics_weekly(:n)"), {"n": weeks}).all()
    return Funnel(
        weeks=weeks,
        since=since,
        crews=CrewFunnel.model_validate(crews._mapping),
        people=PeopleFunnel.model_validate(people._mapping),
        sources=[SourceRow.model_validate(s._mapping) for s in sources],
        loops=Loops.model_validate(loops._mapping),
        stages=[
            CrewStage(
                id=s.id,
                name=s.name,
                created_at=s.created_at,
                members=s.members,
                games=s.games,
                games_first_week=s.games_first_week,
                first_game_at=s.first_game_at,
                last_game_at=s.last_game_at,
                stage=stage_of(
                    deleted=s.deleted,
                    members=s.members,
                    games=s.games,
                    games_first_week=s.games_first_week,
                    last_game_at=s.last_game_at,
                    now=now,
                ),
            )
            for s in stages
        ],
        active_crews=[
            WeekOfCrews(week_start=w.week_start, active_crews=w.active_crews) for w in weekly
        ],
    )
