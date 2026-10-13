"""The admin page: app-wide numbers for the people in POPSHOT_ADMIN_EMAILS.

Anyone else gets 404, exactly like a path that doesn't exist, so the page isn't advertised.
Admins also need to have signed in within RECENT_SIGN_IN: a token refreshes silently for
as long as the browser keeps its session, so this asks for a fresh Google sign-in (and its
2-Step Verification) at least that often. Each view is recorded in admin_views and logged.
"""

import time
from datetime import date, datetime
from typing import Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import text

from popshot_api.auth.dependencies import CurrentIdentity
from popshot_api.db import CurrentUserSession, UserSession
from popshot_api.settings import Settings

log = structlog.get_logger(__name__)

RECENT_SIGN_IN = 12 * 60 * 60  # seconds
WEEKS = 12
COHORTS = 8


def require_admin(identity: CurrentIdentity, request: Request) -> None:
    settings: Settings = request.app.state.settings
    if identity.email.lower() not in settings.admins:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    if time.time() - identity.auth_time > RECENT_SIGN_IN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sign in again to open the admin page.",
        )


# Runs before anything else on these routes, so a non-admin never reaches the database.
router = APIRouter(prefix="/v1/admin", dependencies=[Depends(require_admin)])


Page = Literal["overview", "groups", "people", "person", "group", "funnel"]


def record_view(user: UserSession, page: Page, target: UUID | None = None) -> None:
    """Who opened which admin page, and which person or crew. Search terms aren't kept."""
    user.session.execute(
        text("INSERT INTO admin_views (user_id, page, target_id) VALUES (:me, :page, :target)"),
        {"me": user.user_id, "page": page, "target": target},
    )
    log.info(
        "admin.viewed",
        page=page,
        user_id=str(user.user_id),
        target_id=str(target) if target else None,
    )


class Totals(BaseModel):
    users: int
    new_users_7d: int
    active_users_7d: int
    active_users_30d: int
    live_groups: int
    deleted_groups: int
    games: int
    games_30d: int
    push_users: int
    level_set: int


class Week(BaseModel):
    week_start: date
    active_users: int
    new_users: int
    active_crews: int
    games: int
    nights: int
    answers: int


class Cohort(BaseModel):
    cohort_week: date
    signed_up: int
    week_1: int
    week_2: int
    week_3: int
    week_4: int


class Overview(BaseModel):
    totals: Totals
    # Oldest first.
    weeks: list[Week]
    retention: list[Cohort]


class AdminGroup(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    members: int
    games: int
    games_30d: int
    last_game_at: datetime | None
    upcoming_nights: int


@router.get("/overview")
def overview(user: CurrentUserSession) -> Overview:
    record_view(user, "overview")
    session = user.session
    totals = session.execute(text("SELECT * FROM app_admin_totals()")).one()
    weeks = session.execute(text("SELECT * FROM app_metrics_weekly(:n)"), {"n": WEEKS}).all()
    cohorts = session.execute(text("SELECT * FROM app_metrics_retention(:n)"), {"n": COHORTS}).all()
    return Overview(
        totals=Totals.model_validate(totals._mapping),
        weeks=[Week.model_validate(w._mapping) for w in weeks],
        retention=[Cohort.model_validate(c._mapping) for c in cohorts],
    )


@router.get("/groups")
def groups(user: CurrentUserSession) -> list[AdminGroup]:
    record_view(user, "groups")
    rows = user.session.execute(text("SELECT * FROM app_admin_groups()")).all()
    return [AdminGroup.model_validate(r._mapping) for r in rows]
