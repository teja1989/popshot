"""Staff: reports on open crews' listings, and taking a crew off the listing (migration 0036).

Reading the reports is recorded like any admin page. Unlisting, relisting and dismissing need
a recent sign-in and a reason, and are written to admin_actions.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from popshot_api.db import CurrentUserSession
from popshot_api.routes.admin import record_view, require_admin
from popshot_api.routes.admin_actions import Reason, require_fresh_sign_in

log = structlog.get_logger()

router = APIRouter(prefix="/v1/admin", dependencies=[Depends(require_admin)])
changes = APIRouter(
    prefix="/v1/admin",
    dependencies=[Depends(require_admin), Depends(require_fresh_sign_in)],
)


class ReportedCrew(BaseModel):
    group_id: UUID
    name: str
    open_to_all: bool
    unlisted_at: datetime | None
    reports: int
    reasons: list[str]
    notes: list[str]
    latest: datetime


class Why(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason


@router.get("/open-crews/reports")
def reported_crews(user: CurrentUserSession) -> list[ReportedCrew]:
    """Crews with reports nobody has dealt with, most reported first."""
    record_view(user, "reports")
    rows = user.session.execute(text("SELECT * FROM app_admin_open_crew_reports()")).mappings()
    return [ReportedCrew.model_validate(dict(row)) for row in rows]


def _done(
    outcome: Literal["done", "unchanged", "no_crew"],
    user: CurrentUserSession,
    action: str,
    group_id: UUID,
) -> Response:
    if outcome == "no_crew":
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such crew.")
    if outcome == "done":
        log.info("admin.action", action=action, user_id=str(user.user_id), group_id=str(group_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@changes.post("/open-crews/{group_id}/unlist", status_code=status.HTTP_204_NO_CONTENT)
def unlist(group_id: UUID, body: Why, user: CurrentUserSession) -> Response:
    """Close the crew and keep it off the listing; its open reports are settled."""
    outcome = user.session.execute(
        text("SELECT app_admin_unlist_crew(:g, :why)"), {"g": group_id, "why": body.reason}
    ).scalar_one()
    return _done(outcome, user, "crew.unlisted", group_id)


@changes.post("/open-crews/{group_id}/relist", status_code=status.HTTP_204_NO_CONTENT)
def relist(group_id: UUID, body: Why, user: CurrentUserSession) -> Response:
    """Let the crew's lead open it again (it stays closed until they do)."""
    outcome = user.session.execute(
        text("SELECT app_admin_relist_crew(:g, :why)"), {"g": group_id, "why": body.reason}
    ).scalar_one()
    return _done(outcome, user, "crew.relisted", group_id)


@changes.post("/open-crews/{group_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss(group_id: UUID, body: Why, user: CurrentUserSession) -> Response:
    """The reports need nothing done; the crew stays listed."""
    outcome = user.session.execute(
        text("SELECT app_admin_dismiss_crew_reports(:g, :why)"), {"g": group_id, "why": body.reason}
    ).scalar_one()
    return _done(outcome, user, "crew.reports_dismissed", group_id)
