"""Admin lookup: find a person, open a person, open a crew. Read-only.

Same gate as routes/admin.py (allowlist, recent sign-in, 404 for everyone else). Emails
come from Firebase when a person is opened (popshot_api.accounts) and are never stored.
"""

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import text

from popshot_api.accounts import AccountLookup, LookupUnavailableError
from popshot_api.db import CurrentUserSession
from popshot_api.routes.admin import record_view, require_admin

router = APIRouter(prefix="/v1/admin", dependencies=[Depends(require_admin)])

Role = Literal["lead", "co_lead", "member"]
Status = Literal["pending", "active", "removed"]


def _lookup(request: Request) -> AccountLookup:
    lookup: AccountLookup = request.app.state.account_lookup
    return lookup


def _not_found(what: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No such {what}.")


class PersonRow(BaseModel):
    id: UUID
    display_name: str
    avatar_url: str | None
    created_at: datetime
    last_active: date | None
    groups: int


class PeopleResults(BaseModel):
    people: list[PersonRow]
    # Searching by email needs Firebase; false when it couldn't be asked.
    email_search: bool


@router.get("/people")
def people(
    user: CurrentUserSession,
    request: Request,
    q: str = Query(min_length=2, max_length=100),
) -> PeopleResults:
    """By name (any part), id, or exact email."""
    record_view(user, "people")
    q = q.strip()
    subject: str | None = None
    email_search = True
    name: str | None = q
    if "@" in q:
        name = None
        try:
            account = _lookup(request).by_email(q.lower())
        except LookupUnavailableError:
            account, email_search = None, False
        if account is None:
            return PeopleResults(people=[], email_search=email_search)
        subject = account.subject
    rows = user.session.execute(
        text("SELECT * FROM app_admin_people(:q, :subject)"), {"q": name, "subject": subject}
    ).all()
    return PeopleResults(
        people=[PersonRow.model_validate(r._mapping) for r in rows], email_search=email_search
    )


class PersonGroup(BaseModel):
    group_id: UUID
    name: str
    role: Role
    status: Status
    left_on_own: bool
    joined_at: datetime
    deleted_at: datetime | None
    games: int


class Person(BaseModel):
    id: UUID
    display_name: str
    avatar_url: str | None
    created_at: datetime
    self_level: str | None
    last_active: date | None
    active_days_30: int
    push_devices: int
    # From Firebase, when it could be asked (see `account`).
    email: str | None
    last_sign_in: datetime | None
    disabled: bool | None
    account: Literal["found", "missing", "unavailable"]
    groups: list[PersonGroup]


@router.get("/people/{person_id}")
def person(person_id: UUID, user: CurrentUserSession, request: Request) -> Person:
    record_view(user, "person", person_id)
    row = user.session.execute(
        text("SELECT * FROM app_admin_person(:id)"), {"id": person_id}
    ).one_or_none()
    if row is None:
        raise _not_found("person")
    groups = user.session.execute(
        text("SELECT * FROM app_admin_person_groups(:id)"), {"id": person_id}
    ).all()
    account_state: Literal["found", "missing", "unavailable"] = "missing"
    try:
        account = _lookup(request).by_subject(row.auth_subject)
    except LookupUnavailableError:
        account, account_state = None, "unavailable"
    if account is not None:
        account_state = "found"
    fields = {k: v for k, v in row._mapping.items() if k != "auth_subject"}
    return Person(
        **fields,
        email=account.email if account else None,
        last_sign_in=account.last_sign_in if account else None,
        disabled=account.disabled if account else None,
        account=account_state,
        groups=[PersonGroup.model_validate(g._mapping) for g in groups],
    )


class GroupMember(BaseModel):
    user_id: UUID
    display_name: str
    avatar_url: str | None
    role: Role
    status: Status
    left_on_own: bool
    joined_at: datetime
    games: int


class GroupAction(BaseModel):
    created_at: datetime
    action: str
    admin_name: str
    target_user_id: UUID | None
    target_name: str | None
    reason: str
    details: dict[str, Any]


class GroupDetail(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    created_by: UUID
    deleted_at: datetime | None
    members: int
    pending: int
    guests: int
    games: int
    last_game_at: datetime | None
    upcoming_nights: int
    open_invites: int
    people: list[GroupMember]
    # Changes an admin made to this crew (routes/admin_actions.py), newest first.
    actions: list[GroupAction]


@router.get("/groups/{group_id}")
def group(group_id: UUID, user: CurrentUserSession) -> GroupDetail:
    record_view(user, "group", group_id)
    row = user.session.execute(
        text("SELECT * FROM app_admin_group(:id)"), {"id": group_id}
    ).one_or_none()
    if row is None:
        raise _not_found("crew")
    members = user.session.execute(
        text("SELECT * FROM app_admin_group_members(:id)"), {"id": group_id}
    ).all()
    actions = user.session.execute(
        text("SELECT * FROM app_admin_group_actions(:id)"), {"id": group_id}
    ).all()
    return GroupDetail(
        **row._mapping,
        people=[GroupMember.model_validate(m._mapping) for m in members],
        actions=[GroupAction.model_validate(a._mapping) for a in actions],
    )
