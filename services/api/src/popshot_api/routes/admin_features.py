"""Admin: feature switches and crew plans (migration 0027). Admin service only.

Looking needs the admin gate (routes/admin.py). Changing also needs a sign-in within
admin_actions.FRESH_SIGN_IN and a reason, which the database function stores with the change
in admin_actions, before and after, in the same transaction. Changes apply at once: nothing
caches them.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from popshot_api.db import CurrentUserSession
from popshot_api.routes.admin import record_view, require_admin
from popshot_api.routes.admin_actions import Reason, require_fresh_sign_in

log = structlog.get_logger(__name__)

Rollout = Literal["off", "crews", "everyone"]
Plan = Literal["organizer"]
PlanSource = Literal["beta", "comp", "subscription"]
FeatureKey = Path(pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$", max_length=64)

router = APIRouter(prefix="/v1/admin", dependencies=[Depends(require_admin)])
changes = APIRouter(
    prefix="/v1/admin",
    dependencies=[Depends(require_admin), Depends(require_fresh_sign_in)],
)


class Feature(BaseModel):
    key: str
    area: str
    title: str
    description: str
    needs_plan: Plan | None
    rollout: Rollout
    crews: int
    updated_at: datetime
    updated_by: str | None


class FeatureCrew(BaseModel):
    group_id: UUID
    name: str
    added_at: datetime
    added_by: str | None


class CrewPlan(BaseModel):
    plan: Plan
    source: PlanSource
    starts_at: datetime
    ends_at: datetime | None
    note: str | None
    granted_at: datetime
    granted_by: str | None


class CrewAccess(BaseModel):
    plans: list[CrewPlan]
    # What's on for this crew right now.
    features: list[str]


class PlanRow(BaseModel):
    group_id: UUID
    name: str
    plan: Plan
    source: PlanSource
    starts_at: datetime
    ends_at: datetime | None
    note: str | None


@router.get("/features")
def list_features(user: CurrentUserSession) -> list[Feature]:
    record_view(user, "features")
    rows = user.session.execute(text("SELECT * FROM app_admin_features()")).all()
    return [
        Feature(
            key=r.key,
            area=r.area,
            title=r.title,
            description=r.description,
            needs_plan=r.needs_plan,
            rollout=r.rollout,
            crews=r.crews,
            updated_at=r.updated_at,
            updated_by=r.updated_by_name,
        )
        for r in rows
    ]


@router.get("/features/{key}/crews")
def feature_crews(user: CurrentUserSession, key: str = FeatureKey) -> list[FeatureCrew]:
    rows = user.session.execute(
        text("SELECT * FROM app_admin_feature_crews(:key)"), {"key": key}
    ).all()
    return [
        FeatureCrew(group_id=r.group_id, name=r.name, added_at=r.added_at, added_by=r.added_by_name)
        for r in rows
    ]


@router.get("/plans")
def list_plans(user: CurrentUserSession) -> list[PlanRow]:
    rows = user.session.execute(text("SELECT * FROM app_admin_plans()")).all()
    return [
        PlanRow(
            group_id=r.group_id,
            name=r.name,
            plan=r.plan,
            source=r.source,
            starts_at=r.starts_at,
            ends_at=r.ends_at,
            note=r.note,
        )
        for r in rows
    ]


@router.get("/groups/{group_id}/access")
def crew_access(group_id: UUID, user: CurrentUserSession) -> CrewAccess:
    plans = user.session.execute(
        text("SELECT * FROM app_admin_crew_plan(:g)"), {"g": group_id}
    ).all()
    features = user.session.execute(
        text("SELECT feature FROM app_admin_crew_features(:g)"), {"g": group_id}
    ).scalars()
    return CrewAccess(
        plans=[
            CrewPlan(
                plan=p.plan,
                source=p.source,
                starts_at=p.starts_at,
                ends_at=p.ends_at,
                note=p.note,
                granted_at=p.granted_at,
                granted_by=p.granted_by_name,
            )
            for p in plans
        ],
        features=list(features),
    )


class SetRollout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rollout: Rollout
    reason: Reason


class SetPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # None: free for everyone it's rolled out to.
    needs_plan: Plan | None
    reason: Reason


class WithReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason


class GrantPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: PlanSource
    ends_at: datetime | None = None
    note: str | None = Field(default=None, max_length=200)
    reason: Reason


Outcome = Literal["done", "unchanged", "no_feature", "no_crew", "bad_end", "no_plan"]
_REFUSED: dict[str, tuple[int, str]] = {
    "no_feature": (status.HTTP_404_NOT_FOUND, "No such feature."),
    "no_crew": (status.HTTP_404_NOT_FOUND, "No such crew."),
    "no_plan": (status.HTTP_404_NOT_FOUND, "This crew has no running plan to end."),
    "bad_end": (status.HTTP_422_UNPROCESSABLE_CONTENT, "The end has to be in the future."),
}


def _done(outcome: Outcome, user: CurrentUserSession, action: str, **ids: str) -> Response:
    if outcome in _REFUSED:
        code, detail = _REFUSED[outcome]
        raise HTTPException(status_code=code, detail=detail)
    if outcome == "done":
        log.info("admin.action", action=action, user_id=str(user.user_id), **ids)
    # 'unchanged' is fine too: it already was that way.
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@changes.put("/features/{key}/rollout", status_code=status.HTTP_204_NO_CONTENT)
def set_rollout(body: SetRollout, user: CurrentUserSession, key: str = FeatureKey) -> Response:
    outcome = user.session.execute(
        text("SELECT app_admin_set_feature_rollout(:key, :rollout, :why)"),
        {"key": key, "rollout": body.rollout, "why": body.reason},
    ).scalar_one()
    return _done(outcome, user, "feature.rollout", feature=key)


@changes.put("/features/{key}/plan", status_code=status.HTTP_204_NO_CONTENT)
def set_plan(body: SetPlan, user: CurrentUserSession, key: str = FeatureKey) -> Response:
    outcome = user.session.execute(
        text("SELECT app_admin_set_feature_plan(:key, :plan, :why)"),
        {"key": key, "plan": body.needs_plan, "why": body.reason},
    ).scalar_one()
    return _done(outcome, user, "feature.plan", feature=key)


@changes.post("/features/{key}/crews/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def add_crew(
    group_id: UUID, body: WithReason, user: CurrentUserSession, key: str = FeatureKey
) -> Response:
    outcome = user.session.execute(
        text("SELECT app_admin_add_feature_crew(:key, :g, :why)"),
        {"key": key, "g": group_id, "why": body.reason},
    ).scalar_one()
    return _done(outcome, user, "feature.crew_add", feature=key, group_id=str(group_id))


@changes.post("/features/{key}/crews/{group_id}/remove", status_code=status.HTTP_204_NO_CONTENT)
def remove_crew(
    group_id: UUID, body: WithReason, user: CurrentUserSession, key: str = FeatureKey
) -> Response:
    outcome = user.session.execute(
        text("SELECT app_admin_remove_feature_crew(:key, :g, :why)"),
        {"key": key, "g": group_id, "why": body.reason},
    ).scalar_one()
    return _done(outcome, user, "feature.crew_remove", feature=key, group_id=str(group_id))


@changes.put("/groups/{group_id}/plans/{plan}", status_code=status.HTTP_204_NO_CONTENT)
def grant_plan(group_id: UUID, plan: Plan, body: GrantPlan, user: CurrentUserSession) -> Response:
    outcome = user.session.execute(
        text("SELECT app_admin_grant_plan(:g, :plan, :source, :ends, :note, :why)"),
        {
            "g": group_id,
            "plan": plan,
            "source": body.source,
            "ends": body.ends_at,
            "note": body.note,
            "why": body.reason,
        },
    ).scalar_one()
    return _done(outcome, user, "plan.grant", group_id=str(group_id))


@changes.post("/groups/{group_id}/plans/{plan}/end", status_code=status.HTTP_204_NO_CONTENT)
def end_plan(group_id: UUID, plan: Plan, body: WithReason, user: CurrentUserSession) -> Response:
    outcome = user.session.execute(
        text("SELECT app_admin_end_plan(:g, :plan, :why)"),
        {"g": group_id, "plan": plan, "why": body.reason},
    ).scalar_one()
    return _done(outcome, user, "plan.end", group_id=str(group_id))
