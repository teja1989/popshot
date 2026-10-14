"""Learn: published shots, for anyone, signed in or not (migration 0029).

Only published copies come back, and only while the 'learn.public' switch is on for everyone;
otherwise the list is empty and every shot is not found.
"""

from datetime import datetime
from typing import Annotated, Any, Literal

import structlog
from fastapi import APIRouter, HTTPException, Path, status
from pydantic import BaseModel, ValidationError
from sqlalchemy import text

from popshot_api.db import PublicSession
from popshot_api.focus import FOCUS_OPTIONS
from popshot_api.learn.scene import Scene

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/public/learn")

Level = Literal["beginner", "intermediate", "advanced", "expert"]
SLUG_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"
SLUG_MAX = 60
NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, detail="We couldn't find that shot.")

_FOCUS = {o.id: o for o in FOCUS_OPTIONS}


class FocusRef(BaseModel):
    id: str
    label: str
    area: str


class ShotSummary(BaseModel):
    slug: str
    title: str
    summary: str
    level: Level
    focus: list[FocusRef]
    published_at: datetime


class Shot(ShotSummary):
    tips: list[str]
    drill_steps: list[str]
    scene: Scene


def focus_refs(ids: list[str]) -> list[FocusRef]:
    return [FocusRef(id=i, label=_FOCUS[i].label, area=_FOCUS[i].area) for i in ids if i in _FOCUS]


@router.get("/shots")
def list_shots(session: PublicSession) -> list[ShotSummary]:
    rows = session.execute(text("SELECT * FROM app_public_shots()")).all()
    return [
        ShotSummary(
            slug=r.slug,
            title=r.title,
            summary=r.summary,
            level=r.level,
            focus=focus_refs(r.focus_ids),
            published_at=r.published_at,
        )
        for r in rows
    ]


@router.get("/shots/{slug}")
def get_shot(
    slug: Annotated[str, Path(pattern=SLUG_PATTERN, max_length=SLUG_MAX)], session: PublicSession
) -> Shot:
    row = session.execute(text("SELECT * FROM app_public_shot(:s)"), {"s": slug}).one_or_none()
    if row is None:
        raise NOT_FOUND
    shot: dict[str, Any] = row.shot
    try:
        scene = Scene.model_validate(shot["scene"])
    except (KeyError, ValidationError):
        # Published under rules that have since changed: hide it rather than send it broken.
        log.warning("learn.bad_published_scene", slug=slug)
        raise NOT_FOUND from None
    return Shot(
        slug=row.slug,
        title=shot["title"],
        summary=shot["summary"],
        level=shot["level"],
        focus=focus_refs(shot["focus_ids"]),
        published_at=row.published_at,
        tips=shot["tips"],
        drill_steps=shot["drill_steps"],
        scene=scene,
    )
