"""Admin: writing and publishing Learn shots (migration 0029). Admin service only.

Looking needs the admin gate (routes/admin.py). Changing also needs a sign-in within
admin_actions.FRESH_SIGN_IN. Creating, publishing, unpublishing and deleting need a reason
too, which the database stores with the change in admin_actions; saving the working copy
doesn't, since nobody else sees it until it's published.

A scene's shape is checked on every save (learn.scene.Scene). Whether it's a playable rally
(learn.scene.problems) is shown with every shot and must be clear to publish.
"""

import json
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import text
from sqlalchemy.orm import Session

from popshot_api.db import CurrentUserSession
from popshot_api.focus import KNOWN_IDS
from popshot_api.learn.scene import MAX_SCENE_BYTES, Scene, problems
from popshot_api.routes.admin import require_admin
from popshot_api.routes.admin_actions import Reason, require_fresh_sign_in
from popshot_api.routes.learn import SLUG_MAX, SLUG_PATTERN, Level

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/admin/learn", dependencies=[Depends(require_admin)])
changes = APIRouter(
    prefix="/v1/admin/learn",
    dependencies=[Depends(require_admin), Depends(require_fresh_sign_in)],
)

MAX_FOCUS = 4
MAX_TIPS = 8
MAX_STEPS = 10

Slug = Annotated[str, StringConstraints(pattern=SLUG_PATTERN, max_length=SLUG_MAX)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
Summary = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Line = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


def _known_focus(ids: list[str]) -> list[str]:
    unknown = sorted(set(ids) - KNOWN_IDS)
    if unknown:
        raise ValueError(f"Unknown focus areas: {', '.join(unknown)}")
    if len(set(ids)) != len(ids):
        raise ValueError("Each focus area can only be picked once.")
    return ids


def _fits(scene: Scene) -> Scene:
    if len(scene.model_dump_json()) > MAX_SCENE_BYTES:
        raise ValueError("This scene is too big. Try fewer keyframes or flights.")
    return scene


FocusIds = Annotated[
    list[Annotated[str, StringConstraints(max_length=40)]],
    Field(min_length=1, max_length=MAX_FOCUS),
    AfterValidator(_known_focus),
]
CheckedScene = Annotated[Scene, AfterValidator(_fits)]


class ShotFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: Slug
    title: Title
    summary: Summary
    level: Level
    focus_ids: FocusIds
    tips: list[Line] = Field(max_length=MAX_TIPS)
    drill_steps: list[Line] = Field(max_length=MAX_STEPS)
    scene: CheckedScene


class NewShot(ShotFields):
    reason: Reason


class SaveShot(ShotFields):
    # The version you were editing. If someone saved since, nothing changes (409).
    version: int = Field(ge=1)


class PublishShot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    reason: Reason


class WithReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason


class ProblemOut(BaseModel):
    code: str
    message: str
    flight: int | None
    actor: str | None


class ShotRow(BaseModel):
    id: UUID
    slug: str
    title: str
    level: Level
    focus_ids: list[str]
    version: int
    updated_at: datetime
    updated_by: str | None
    published_version: int | None
    published_at: datetime | None


class AdminShot(BaseModel):
    id: UUID
    slug: str
    title: str
    summary: str
    level: Level
    focus_ids: list[str]
    tips: list[str]
    drill_steps: list[str]
    # None if it was saved under rules that have since changed; the editor starts it afresh.
    scene: Scene | None
    version: int
    updated_at: datetime
    updated_by: str | None
    published_version: int | None
    published_at: datetime | None
    # Once published, the slug is the shot's address and can't change.
    slug_locked: bool
    # What stops it being published, if anything.
    problems: list[ProblemOut]


class Created(BaseModel):
    id: UUID


Outcome = Literal["done", "unchanged", "no_shot", "stale", "slug_taken", "slug_locked", "published"]
_REFUSED: dict[str, tuple[int, str]] = {
    "no_shot": (status.HTTP_404_NOT_FOUND, "No such shot."),
    "stale": (
        status.HTTP_409_CONFLICT,
        "Someone saved this shot since you opened it. Reload to see their changes.",
    ),
    "slug_taken": (status.HTTP_409_CONFLICT, "Another shot already has that address."),
    "slug_locked": (
        status.HTTP_409_CONFLICT,
        "This shot has been published, so its address can't change.",
    ),
    "published": (status.HTTP_409_CONFLICT, "Unpublish this shot before deleting it."),
}


def _refuse_unless_done(outcome: Outcome) -> None:
    if outcome in _REFUSED:
        code, detail = _REFUSED[outcome]
        raise HTTPException(status_code=code, detail=detail)


def _problems(scene: Scene) -> list[ProblemOut]:
    return [
        ProblemOut(code=p.code, message=p.message, flight=p.flight, actor=p.actor)
        for p in problems(scene)
    ]


def _params(body: ShotFields) -> dict[str, Any]:
    return {
        "slug": body.slug,
        "title": body.title,
        "summary": body.summary,
        "level": body.level,
        "focus": body.focus_ids,
        "tips": body.tips,
        "steps": body.drill_steps,
        "scene": json.dumps(body.scene.model_dump(mode="json")),
    }


def _load(session: Session, shot_id: UUID) -> AdminShot:
    row = session.execute(text("SELECT * FROM app_admin_shot(:id)"), {"id": shot_id}).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such shot.")
    try:
        scene: Scene | None = Scene.model_validate(row.scene)
    except ValueError:
        scene = None
    return AdminShot(
        id=row.id,
        slug=row.slug,
        title=row.title,
        summary=row.summary,
        level=row.level,
        focus_ids=row.focus_ids,
        tips=row.tips,
        drill_steps=row.drill_steps,
        scene=scene,
        version=row.version,
        updated_at=row.updated_at,
        updated_by=row.updated_by_name,
        published_version=row.published_version,
        published_at=row.published_at,
        slug_locked=row.first_published_at is not None,
        problems=_problems(scene) if scene else [],
    )


@router.get("/shots")
def list_shots(user: CurrentUserSession) -> list[ShotRow]:
    rows = user.session.execute(text("SELECT * FROM app_admin_shots()")).all()
    return [
        ShotRow(
            id=r.id,
            slug=r.slug,
            title=r.title,
            level=r.level,
            focus_ids=r.focus_ids,
            version=r.version,
            updated_at=r.updated_at,
            updated_by=r.updated_by_name,
            published_version=r.published_version,
            published_at=r.published_at,
        )
        for r in rows
    ]


@router.get("/shots/{shot_id}")
def get_shot(shot_id: UUID, user: CurrentUserSession) -> AdminShot:
    return _load(user.session, shot_id)


@changes.post("/shots", status_code=status.HTTP_201_CREATED)
def create_shot(body: NewShot, user: CurrentUserSession) -> Created:
    row = user.session.execute(
        text(
            "SELECT * FROM app_admin_create_shot(:slug, :title, :summary, :level, :focus, "
            ":tips, :steps, CAST(:scene AS jsonb), :why)"
        ),
        {**_params(body), "why": body.reason},
    ).one()
    _refuse_unless_done(row.outcome)
    log.info("admin.action", action="learn.create", user_id=str(user.user_id), slug=body.slug)
    return Created(id=row.shot_id)


@changes.put("/shots/{shot_id}")
def save_shot(shot_id: UUID, body: SaveShot, user: CurrentUserSession) -> AdminShot:
    outcome = user.session.execute(
        text(
            "SELECT app_admin_save_shot(:id, :version, :slug, :title, :summary, :level, :focus, "
            ":tips, :steps, CAST(:scene AS jsonb))"
        ),
        {**_params(body), "id": shot_id, "version": body.version},
    ).scalar_one()
    _refuse_unless_done(outcome)
    return _load(user.session, shot_id)


@changes.post("/shots/{shot_id}/publish", status_code=status.HTTP_204_NO_CONTENT)
def publish_shot(shot_id: UUID, body: PublishShot, user: CurrentUserSession) -> Response:
    shot = _load(user.session, shot_id)
    if shot.scene is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="This shot's scene needs saving again before it can be published.",
        )
    if shot.problems:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=" ".join(p.message for p in shot.problems),
        )
    # The database checks the version under a lock: if this isn't the version just checked,
    # or someone saved in between, it's refused as stale.
    outcome = user.session.execute(
        text("SELECT app_admin_publish_shot(:id, :version, :why)"),
        {"id": shot_id, "version": body.version, "why": body.reason},
    ).scalar_one()
    _refuse_unless_done(outcome)
    if outcome == "done":
        log.info("admin.action", action="learn.publish", user_id=str(user.user_id), slug=shot.slug)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@changes.post("/shots/{shot_id}/unpublish", status_code=status.HTTP_204_NO_CONTENT)
def unpublish_shot(shot_id: UUID, body: WithReason, user: CurrentUserSession) -> Response:
    outcome = user.session.execute(
        text("SELECT app_admin_unpublish_shot(:id, :why)"), {"id": shot_id, "why": body.reason}
    ).scalar_one()
    _refuse_unless_done(outcome)
    if outcome == "done":
        log.info("admin.action", action="learn.unpublish", user_id=str(user.user_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@changes.post("/shots/{shot_id}/delete", status_code=status.HTTP_204_NO_CONTENT)
def delete_shot(shot_id: UUID, body: WithReason, user: CurrentUserSession) -> Response:
    outcome = user.session.execute(
        text("SELECT app_admin_delete_shot(:id, :why)"), {"id": shot_id, "why": body.reason}
    ).scalar_one()
    _refuse_unless_done(outcome)
    log.info("admin.action", action="learn.delete", user_id=str(user.user_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
