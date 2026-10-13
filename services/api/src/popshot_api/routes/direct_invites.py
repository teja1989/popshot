"""Direct invites: a lead or co-lead invites a person, who accepts or declines.

There's no open search for people. A lead invites someone they know (anyone who is or was
in a crew with them) or someone who gave them their Popshot code. Codes are random, shown
on the person's You page, and can be changed at any time. Looking codes up is limited, so
they can't be found by trying them in bulk.

Accepting joins the crew at once. Declining is quiet: the invite leaves the lead's list and
nobody is told. The person can also stop a crew from inviting them again; that crew still
sees "sent".

All of it goes through the database functions in migration 0018, because the person
invited isn't in the crew and the crew can't otherwise see them.
"""

import re
import secrets
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from popshot_api.db import CurrentUserSession
from popshot_api.push import Message
from popshot_api.recap_lines import first_name
from popshot_api.routes.invites import _require_admin
from popshot_api.routes.notifications import CurrentNotifier

router = APIRouter(prefix="/v1")

# Crockford base32: no I, L, O or U, so codes read out loud without mix-ups.
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
CODE_LENGTH = 8
_CODE = re.compile(f"[{ALPHABET}]{{{CODE_LENGTH}}}")
_TYPED = str.maketrans({"O": "0", "I": "1", "L": "1", "-": None, " ": None})
NEW_CODE_TRIES = 5
LOOKUP_LIMITED = "PS429"

INVITE_NOT_FOUND = HTTPException(
    status.HTTP_404_NOT_FOUND, detail="That invite isn't open any more."
)
TOO_MANY_LOOKUPS = HTTPException(
    status.HTTP_429_TOO_MANY_REQUESTS,
    detail="That's a lot of codes for one hour. Try again later.",
)
SEND_REFUSED = {
    "not_found": HTTPException(
        status.HTTP_404_NOT_FOUND, detail="We couldn't find that person to invite."
    ),
    "member": HTTPException(status.HTTP_409_CONFLICT, detail="They're already in the crew."),
    "requested": HTTPException(
        status.HTTP_409_CONFLICT,
        detail="They've already asked to join. You can let them in from the members list.",
    ),
    "too_many": HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        detail="This crew has a lot of invites waiting. Cancel some first.",
    ),
}

Standing = Literal["member", "requested", "invited"]


def normalize_code(typed: str) -> str | None:
    """A code as stored, from what someone typed ("k7m2-qx4p", "K7M2 QX4P"), or None."""
    code = typed.upper().translate(_TYPED)
    return code if _CODE.fullmatch(code) else None


def show_code(code: str) -> str:
    return f"{code[:4]}-{code[4:]}"


def _new_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


class InviteCode(BaseModel):
    # "K7M2-QX4P"
    code: str


class Person(BaseModel):
    user_id: UUID
    display_name: str
    avatar_url: str | None
    # Where they stand with this crew already, if anywhere.
    standing: Standing | None


class Lookup(BaseModel):
    # Null when no one has that code.
    person: Person | None


class CodeLookup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Annotated[str, Field(max_length=32)]


class SendInvite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID


class Sent(BaseModel):
    # Always "sent": whether the person can see it isn't the crew's to know.
    outcome: Literal["sent"]


class GroupDirectInvite(BaseModel):
    id: UUID
    user_id: UUID
    display_name: str
    avatar_url: str | None
    invited_by_name: str | None
    created_at: datetime
    expires_at: datetime


class MyInvite(BaseModel):
    id: UUID
    group_id: UUID
    group_name: str
    invited_by_name: str | None
    members: int
    created_at: datetime
    expires_at: datetime
    # The crew's profile, without its home courts (those are for members).
    about: str | None = None
    usual_days: list[str] = []
    usual_times: list[str] = []


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # "block": decline, and don't let this crew invite me again.
    answer: Literal["accept", "decline", "block"]


class Answered(BaseModel):
    group_id: UUID
    answer: Literal["accept", "decline", "block"]


class InviteBlock(BaseModel):
    group_id: UUID
    group_name: str
    created_at: datetime


# Your code.


def _set_new_code(session: Session, me: UUID) -> str:
    for _ in range(NEW_CODE_TRIES):
        code = _new_code()
        try:
            with session.begin_nested():
                session.execute(
                    text("UPDATE users SET invite_code = :code WHERE id = :me"),
                    {"code": code, "me": me},
                )
        except IntegrityError:
            continue  # Someone already has it: about a one-in-a-trillion chance.
        return code
    raise RuntimeError("couldn't find a free invite code")


@router.get("/me/invite-code")
def my_invite_code(user: CurrentUserSession) -> InviteCode:
    """Your Popshot code, made the first time you ask."""
    code = user.session.execute(
        text("SELECT invite_code FROM users WHERE id = :me"), {"me": user.user_id}
    ).scalar_one()
    return InviteCode(code=show_code(code or _set_new_code(user.session, user.user_id)))


@router.post("/me/invite-code")
def change_invite_code(user: CurrentUserSession) -> InviteCode:
    """A new code. The old one stops working."""
    return InviteCode(code=show_code(_set_new_code(user.session, user.user_id)))


# Finding and inviting people (leads and co-leads).


@router.get("/groups/{group_id}/people")
def known_people(
    group_id: UUID,
    user: CurrentUserSession,
    q: Annotated[str, Query(max_length=80)] = "",
) -> list[Person]:
    """People you know from your crews, whose name contains `q`."""
    _require_admin(user.session, user.user_id, group_id)
    rows = user.session.execute(
        text("SELECT * FROM app_known_people(:g, :q)"), {"g": group_id, "q": q.strip()}
    ).mappings()
    return [Person(**row) for row in rows]


@router.post("/groups/{group_id}/people/lookup")
def look_up_code(group_id: UUID, body: CodeLookup, user: CurrentUserSession) -> Lookup:
    """The person with this code: first name and photo, to check before inviting.

    No match is a normal answer (person: null), not an error: an error would roll back the
    request, and with it the record of the lookup that the hourly limit counts.
    """
    _require_admin(user.session, user.user_id, group_id)
    code = normalize_code(body.code)
    if code is None:
        return Lookup(person=None)
    try:
        with user.session.begin_nested():
            row = (
                user.session.execute(
                    text("SELECT * FROM app_lookup_invite_code(:g, :code)"),
                    {"g": group_id, "code": code},
                )
                .mappings()
                .one_or_none()
            )
    except DBAPIError as exc:
        if getattr(exc.orig, "sqlstate", None) == LOOKUP_LIMITED:
            raise TOO_MANY_LOOKUPS from None
        raise
    if row is None:
        return Lookup(person=None)
    return Lookup(person=Person(**{**row, "display_name": first_name(row["display_name"])}))


@router.post("/groups/{group_id}/direct-invites", status_code=status.HTTP_201_CREATED)
def send_invite(
    group_id: UUID, body: SendInvite, user: CurrentUserSession, notifier: CurrentNotifier
) -> Sent:
    _require_admin(user.session, user.user_id, group_id)
    outcome = user.session.execute(
        text("SELECT app_send_direct_invite(:g, :u)"), {"g": group_id, "u": body.user_id}
    ).scalar_one()
    if outcome != "sent":
        raise SEND_REFUSED[outcome]
    names = user.session.execute(
        text(
            "SELECT g.name AS crew, u.display_name AS lead FROM groups g, users u "
            "WHERE g.id = :g AND u.id = :me"
        ),
        {"g": group_id, "me": user.user_id},
    ).one()
    notifier.notify_invitee(
        user.session,
        group_id,
        body.user_id,
        Message(
            title=f"{first_name(names.lead)} invited you to {names.crew}",
            body="Open Popshot to say yes or no.",
            url="/",
            tag=f"invite-{group_id}",
        ),
    )
    return Sent(outcome="sent")


@router.get("/groups/{group_id}/direct-invites")
def group_invites(group_id: UUID, user: CurrentUserSession) -> list[GroupDirectInvite]:
    """Invites waiting for an answer. Declined ones just aren't here."""
    _require_admin(user.session, user.user_id, group_id)
    rows = user.session.execute(
        text("SELECT * FROM app_group_direct_invites(:g)"), {"g": group_id}
    ).mappings()
    return [GroupDirectInvite(**row) for row in rows]


@router.delete(
    "/groups/{group_id}/direct-invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT
)
def cancel_invite(group_id: UUID, invite_id: UUID, user: CurrentUserSession) -> Response:
    _require_admin(user.session, user.user_id, group_id)
    in_group = user.session.execute(
        text("SELECT 1 FROM app_group_direct_invites(:g) WHERE id = :i"),
        {"g": group_id, "i": invite_id},
    ).scalar_one_or_none()
    if (
        in_group is None
        or not user.session.execute(
            text("SELECT app_cancel_direct_invite(:i)"), {"i": invite_id}
        ).scalar_one()
    ):
        raise INVITE_NOT_FOUND
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Your invites.


@router.get("/me/invites")
def my_invites(user: CurrentUserSession) -> list[MyInvite]:
    rows = user.session.execute(text("SELECT * FROM app_my_direct_invites()")).mappings()
    return [MyInvite(**row) for row in rows]


@router.post("/me/invites/{invite_id}")
def answer_invite(invite_id: UUID, body: Answer, user: CurrentUserSession) -> Answered:
    group_id = user.session.execute(
        text("SELECT app_answer_direct_invite(:i, :a)"), {"i": invite_id, "a": body.answer}
    ).scalar_one()
    if group_id is None:
        raise INVITE_NOT_FOUND
    return Answered(group_id=group_id, answer=body.answer)


@router.get("/me/invite-blocks")
def my_blocks(user: CurrentUserSession) -> list[InviteBlock]:
    """Crews you've stopped from inviting you."""
    rows = user.session.execute(text("SELECT * FROM app_my_invite_blocks()")).mappings()
    return [InviteBlock(**row) for row in rows]


@router.delete("/me/invite-blocks/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def unblock(group_id: UUID, user: CurrentUserSession) -> Response:
    if not user.session.execute(
        text("SELECT app_unblock_invites(:g)"), {"g": group_id}
    ).scalar_one():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="That crew isn't blocked.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
