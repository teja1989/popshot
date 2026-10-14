"""Admin: the content library (migration 0033). Admin service only.

Looking needs the admin gate (routes/admin.py). Changing also needs a recent sign-in and a
reason, which the database function logs with the change in admin_actions. Links are tidied
here (content.normalise_link) and checked again by the database.
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import text

from popshot_api.content import BadLinkError, normalise_host, normalise_link
from popshot_api.db import CurrentUserSession
from popshot_api.focus import OFFERED_IDS
from popshot_api.routes.admin import record_view, require_admin
from popshot_api.routes.admin_actions import Reason, require_fresh_sign_in

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/admin/content", dependencies=[Depends(require_admin)])
changes = APIRouter(
    prefix="/v1/admin/content",
    dependencies=[Depends(require_admin), Depends(require_fresh_sign_in)],
)

Kind = Literal["video", "article"]
Level = Literal["beginner", "intermediate", "advanced", "expert"]
Status = Literal["draft", "published"]


def _skills(ids: list[str]) -> list[str]:
    unknown = sorted({i for i in ids if i not in OFFERED_IDS})
    if unknown:
        raise ValueError(f"Unknown skills: {', '.join(unknown)}")
    if len(set(ids)) != len(ids):
        raise ValueError("Each skill can only be picked once.")
    return ids


def _unique(values: list[Level]) -> list[Level]:
    if len(set(values)) != len(values):
        raise ValueError("Each level can only be picked once.")
    return values


Skills = Annotated[
    list[Annotated[str, Field(max_length=40)]],
    Field(min_length=1, max_length=4),
    AfterValidator(_skills),
]


class Item(BaseModel):
    id: UUID
    kind: Kind
    url: str
    title: str
    source: str
    skills: list[str]
    levels: list[Level]
    minutes: int | None
    status: Status
    updated_at: datetime
    updated_by: str | None


class Host(BaseModel):
    host: str
    added_at: datetime


class EditItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Kind
    url: Annotated[str, Field(min_length=1, max_length=500)]
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    source: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    skills: Skills
    levels: Annotated[list[Level], Field(max_length=4), AfterValidator(_unique)] = []
    minutes: Annotated[int, Field(ge=1, le=120)] | None = None
    reason: Reason


class SetStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status
    reason: Reason


class NewHost(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: Annotated[str, Field(min_length=1, max_length=100)]
    reason: Reason


class Added(BaseModel):
    id: UUID
    url: str


_REFUSED: dict[str, tuple[int, str]] = {
    "no_item": (status.HTTP_404_NOT_FOUND, "No such item."),
    "bad_link": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "That site isn't on the allowed list. Add it first, with a reason.",
    ),
    "duplicate": (status.HTTP_409_CONFLICT, "That link is already in the library."),
}


def _refuse_if(outcome: str) -> None:
    if outcome in _REFUSED:
        code, detail = _REFUSED[outcome]
        raise HTTPException(status_code=code, detail=detail)


def _link(raw: str) -> str:
    try:
        return normalise_link(raw)
    except BadLinkError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from None


@router.get("")
def list_content(user: CurrentUserSession) -> list[Item]:
    record_view(user, "content")
    rows = user.session.execute(text("SELECT * FROM app_admin_content()")).mappings()
    return [Item.model_validate({**row, "updated_by": row["updated_by_name"]}) for row in rows]


@router.get("/hosts")
def list_hosts(user: CurrentUserSession) -> list[Host]:
    rows = user.session.execute(text("SELECT * FROM app_admin_content_hosts()")).mappings()
    return [Host.model_validate(dict(row)) for row in rows]


def _values(body: EditItem) -> dict[str, object]:
    return {
        "kind": body.kind,
        "url": _link(body.url),
        "title": body.title,
        "source": body.source,
        "skills": body.skills,
        "levels": list(body.levels),
        "minutes": body.minutes,
        "why": body.reason,
    }


@changes.post("", status_code=status.HTTP_201_CREATED)
def add_content(body: EditItem, user: CurrentUserSession) -> Added:
    values = _values(body)
    row = user.session.execute(
        text(
            "SELECT * FROM app_admin_add_content(:kind, :url, :title, :source, :skills, "
            ":levels, :minutes, :why)"
        ),
        values,
    ).one()
    _refuse_if(row.outcome)
    log.info("admin.action", action="content.add", user_id=str(user.user_id), item=str(row.id))
    return Added(id=row.id, url=str(values["url"]))


@changes.put("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def edit_content(item_id: UUID, body: EditItem, user: CurrentUserSession) -> Response:
    outcome = user.session.execute(
        text(
            "SELECT app_admin_edit_content(:item, :kind, :url, :title, :source, :skills, "
            ":levels, :minutes, :why)"
        ),
        {"item": item_id, **_values(body)},
    ).scalar_one()
    _refuse_if(outcome)
    log.info("admin.action", action="content.edit", user_id=str(user.user_id), item=str(item_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@changes.put("/{item_id}/status", status_code=status.HTTP_204_NO_CONTENT)
def set_status(item_id: UUID, body: SetStatus, user: CurrentUserSession) -> Response:
    outcome = user.session.execute(
        text("SELECT app_admin_set_content_status(:item, :status, :why)"),
        {"item": item_id, "status": body.status, "why": body.reason},
    ).scalar_one()
    _refuse_if(outcome)
    if outcome == "done":
        log.info(
            "admin.action", action="content.status", user_id=str(user.user_id), item=str(item_id)
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@changes.post("/hosts", status_code=status.HTTP_204_NO_CONTENT)
def add_host(body: NewHost, user: CurrentUserSession) -> Response:
    try:
        host = normalise_host(body.host)
    except BadLinkError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from None
    outcome = user.session.execute(
        text("SELECT app_admin_add_content_host(:host, :why)"), {"host": host, "why": body.reason}
    ).scalar_one()
    if outcome == "done":
        log.info("admin.action", action="content.host_add", user_id=str(user.user_id), host=host)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
