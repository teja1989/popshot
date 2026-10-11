"""Admin actions: changes an admin makes to fix a crew. Admin service only.

On top of the admin gate (routes/admin.py), a change needs a sign-in within FRESH_SIGN_IN,
and a reason, which is stored with the change in admin_actions (migration 0013) by the same
database function, in the same transaction.
"""

import time
from typing import Annotated, Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import text

from popshot_api.auth.dependencies import CurrentIdentity
from popshot_api.db import CurrentUserSession
from popshot_api.routes.admin import require_admin

log = structlog.get_logger(__name__)

FRESH_SIGN_IN = 15 * 60  # seconds

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=500)]


def require_fresh_sign_in(identity: CurrentIdentity) -> None:
    if time.time() - identity.auth_time > FRESH_SIGN_IN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sign in again to make changes.",
        )


router = APIRouter(
    prefix="/v1/admin",
    dependencies=[Depends(require_admin), Depends(require_fresh_sign_in)],
)


class MakeLead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    reason: Reason


class LeadChanged(BaseModel):
    lead: UUID
    previous_lead: UUID | None


_REFUSED: dict[str, tuple[int, str]] = {
    "no_crew": (status.HTTP_404_NOT_FOUND, "No such crew."),
    "not_member": (status.HTTP_409_CONFLICT, "Only an active member can be made the lead."),
    "already_lead": (status.HTTP_409_CONFLICT, "They're already the lead."),
}


@router.post("/groups/{group_id}/lead")
def make_lead(group_id: UUID, body: MakeLead, user: CurrentUserSession) -> LeadChanged:
    """Make an active member the crew's lead; the previous lead becomes a co-lead."""
    row = user.session.execute(
        text("SELECT * FROM app_admin_make_lead(:group, :lead, :why)"),
        {"group": group_id, "lead": body.user_id, "why": body.reason},
    ).one()
    outcome: Literal["done", "no_crew", "not_member", "already_lead"] = row.outcome
    if outcome != "done":
        code, detail = _REFUSED[outcome]
        raise HTTPException(status_code=code, detail=detail)
    log.info(
        "admin.action",
        action="crew.lead_changed",
        user_id=str(user.user_id),
        group_id=str(group_id),
        target_id=str(body.user_id),
    )
    return LeadChanged(lead=body.user_id, previous_lead=row.previous_lead)
