"""Invite links, joining through them, and managing who is in a group.

An invite link carries a random token. Only its SHA-256 is stored, and the token is shown
once, to the lead or co-lead who made it. Every join through a link waits for approval.

Errors follow groups.py: a group you can't see is a 404. Inside a group you can see, asking
for something your role doesn't allow is a 403. A dead, unknown or malformed invite token
is one 404, so a caller can't tell which.
"""

import hashlib
import re
import secrets
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from popshot_api.db import CurrentUserSession
from popshot_api.routes.groups import NOT_FOUND, GroupDetail, Role, group_detail
from popshot_api.routes.notifications import CurrentNotifier

router = APIRouter()

INVITE_DAYS = 7
MAX_INVITE_USES = 10
# Live (unused, unexpired, not cancelled) links per group. Plenty for a crew, and stops a
# script from filling the table.
MAX_LIVE_INVITES = 20

# secrets.token_urlsafe(32): 32 random bytes, 43 URL-safe characters.
TOKEN_BYTES = 32
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")

DEAD_INVITE = HTTPException(
    status.HTTP_404_NOT_FOUND,
    detail="This invite link isn't valid any more. Ask for a new one.",
)
ADMINS_ONLY = HTTPException(
    status.HTTP_403_FORBIDDEN, detail="Only the group's lead or a co-lead can do that."
)
LEAD_ONLY = HTTPException(status.HTTP_403_FORBIDDEN, detail="Only the group's lead can do that.")
MEMBER_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, detail="We couldn't find that member.")


class CreateInvite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_uses: Annotated[int, Field(ge=1, le=MAX_INVITE_USES)] = 1


class Invite(BaseModel):
    id: UUID
    created_by_name: str | None
    max_uses: int
    use_count: int
    expires_at: datetime
    created_at: datetime


class NewInvite(Invite):
    # Shown once. The server keeps only its hash.
    token: str


class InviteToken(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: Annotated[str, Field(max_length=64)]


JoinStatus = Literal["active", "pending", "removed"]


class InvitePreview(BaseModel):
    group_name: str
    invited_by: str
    # Only when you're already in the group, or waiting to be let in.
    group_id: UUID | None
    # Your membership, if you have one.
    my_status: JoinStatus | None


class Joined(BaseModel):
    group_id: UUID | None
    status: JoinStatus


Action = Literal[
    "approve", "decline", "make_co_lead", "make_member", "remove", "make_lead", "restore"
]


class MemberChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Action


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("ascii")).digest()


def _token_hash(body: InviteToken) -> bytes:
    if _TOKEN.fullmatch(body.token) is None:
        raise DEAD_INVITE
    return hash_token(body.token)


def _my_role(session: Session, me: UUID, group_id: UUID) -> Role:
    """Your role in a group you're an active member of; a 404 otherwise."""
    role: Role | None = session.execute(
        text(
            "SELECT role FROM group_members "
            "JOIN groups ON groups.id = group_members.group_id "
            "WHERE group_id = :group_id AND user_id = :me AND status = 'active'"
        ),
        {"group_id": group_id, "me": me},
    ).scalar_one_or_none()
    if role is None:
        raise NOT_FOUND
    return role


def _require_admin(session: Session, me: UUID, group_id: UUID) -> Role:
    role = _my_role(session, me, group_id)
    if role not in ("lead", "co_lead"):
        raise ADMINS_ONLY
    return role


def _audit(session: Session, group_id: UUID, me: UUID, action: str, target: UUID) -> None:
    session.execute(
        text(
            "INSERT INTO audit_log (group_id, actor_user_id, action, target_id) "
            "VALUES (:group_id, :me, :action, :target)"
        ),
        {"group_id": group_id, "me": me, "action": action, "target": target},
    )


_LIST_INVITES = """
    SELECT i.id, u.display_name AS created_by_name, i.max_uses, i.use_count, i.expires_at,
           i.created_at
    FROM group_invites i
    LEFT JOIN users u ON u.id = i.created_by
    WHERE i.group_id = :group_id AND i.revoked_at IS NULL AND i.expires_at > now()
      AND i.use_count < i.max_uses
    ORDER BY i.created_at DESC, i.id
"""


@router.get("/v1/groups/{group_id}/invites")
def list_invites(group_id: UUID, user: CurrentUserSession) -> list[Invite]:
    _require_admin(user.session, user.user_id, group_id)
    rows = user.session.execute(text(_LIST_INVITES), {"group_id": group_id}).mappings()
    return [Invite(**row) for row in rows]


@router.post("/v1/groups/{group_id}/invites", status_code=status.HTTP_201_CREATED)
def create_invite(group_id: UUID, body: CreateInvite, user: CurrentUserSession) -> NewInvite:
    _require_admin(user.session, user.user_id, group_id)
    live = user.session.execute(
        text(
            "SELECT count(*) FROM group_invites WHERE group_id = :group_id "
            "AND revoked_at IS NULL AND expires_at > now() AND use_count < max_uses"
        ),
        {"group_id": group_id},
    ).scalar_one()
    if live >= MAX_LIVE_INVITES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"This group has {MAX_LIVE_INVITES} open invite links. Cancel one first.",
        )
    token = secrets.token_urlsafe(TOKEN_BYTES)
    row = (
        user.session.execute(
            text(
                """
                INSERT INTO group_invites (group_id, token_hash, created_by, expires_at,
                                           max_uses, requires_approval)
                VALUES (:group_id, :token_hash, :me,
                        now() + make_interval(days => :days), :max_uses, true)
                RETURNING id, max_uses, use_count, expires_at, created_at
                """
            ),
            {
                "group_id": group_id,
                "token_hash": hash_token(token),
                "me": user.user_id,
                "days": INVITE_DAYS,
                "max_uses": body.max_uses,
            },
        )
        .mappings()
        .one()
    )
    _audit(user.session, group_id, user.user_id, "invite.created", row["id"])
    name = user.session.execute(
        text("SELECT display_name FROM users WHERE id = :me"), {"me": user.user_id}
    ).scalar_one()
    return NewInvite(**row, created_by_name=name, token=token)


@router.delete("/v1/groups/{group_id}/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_invite(group_id: UUID, invite_id: UUID, user: CurrentUserSession) -> Response:
    _require_admin(user.session, user.user_id, group_id)
    cancelled = user.session.execute(
        text(
            "UPDATE group_invites SET revoked_at = now() "
            "WHERE id = :id AND group_id = :group_id AND revoked_at IS NULL RETURNING id"
        ),
        {"id": invite_id, "group_id": group_id},
    ).scalar_one_or_none()
    if cancelled is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="We couldn't find that invite.")
    _audit(user.session, group_id, user.user_id, "invite.cancelled", invite_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# POST rather than GET, so the token stays out of URLs and request logs.
@router.post("/v1/invites/preview")
def preview_invite(body: InviteToken, user: CurrentUserSession) -> InvitePreview:
    row = (
        user.session.execute(
            text("SELECT * FROM app_preview_invite(:token_hash)"),
            {"token_hash": _token_hash(body)},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise DEAD_INVITE
    return InvitePreview(**row)


@router.post("/v1/invites/join")
def join(body: InviteToken, user: CurrentUserSession, notifier: CurrentNotifier) -> Joined:
    row = (
        user.session.execute(
            text("SELECT * FROM app_redeem_invite(:token_hash)"),
            {"token_hash": _token_hash(body)},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise DEAD_INVITE
    if row["status"] == "pending":
        notifier.notify_join_request(user.session, row["group_id"])
    # Someone removed from a group doesn't learn its ID again.
    group_id = None if row["status"] == "removed" else row["group_id"]
    return Joined(group_id=group_id, status=row["status"])


def _hand_over(session: Session, me: UUID, group_id: UUID, user_id: UUID) -> GroupDetail:
    """The lead makes an active member the lead, and becomes a co-lead."""
    if _my_role(session, me, group_id) != "lead":
        raise LEAD_ONLY
    # False when they aren't an active member (say, still waiting for approval).
    handed = session.execute(
        text("SELECT app_hand_over_lead(:group_id, :user_id)"),
        {"group_id": group_id, "user_id": user_id},
    ).scalar_one()
    if not handed:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="That person hasn't been let in yet.")
    detail = group_detail(session, me, group_id)
    if detail is None:  # pragma: no cover - you're still a co-lead
        raise NOT_FOUND
    return detail


@router.patch("/v1/groups/{group_id}/members/{user_id}")
def change_member(
    group_id: UUID, user_id: UUID, body: MemberChange, user: CurrentUserSession
) -> GroupDetail:
    session, me = user.session, user.user_id
    my_role = _require_admin(session, me, group_id)
    if user_id == me:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="You can't change your own membership here."
        )
    target = (
        session.execute(
            text(
                "SELECT role, status, left_at FROM group_members "
                "WHERE group_id = :group_id AND user_id = :user_id"
            ),
            {"group_id": group_id, "user_id": user_id},
        )
        .mappings()
        .one_or_none()
    )
    # Someone who left on their own isn't the admins' to bring back: they ask again with an
    # invite. Removed or declined people only show up for "restore".
    if (
        target is None
        or target["left_at"] is not None
        or (target["status"] == "removed") != (body.action == "restore")
    ):
        raise MEMBER_NOT_FOUND
    if target["role"] == "lead":
        # The caller isn't the lead (that's their own row, refused above).
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Nobody can change the group's lead.")

    action = body.action
    if action == "make_lead":
        return _hand_over(session, me, group_id, user_id)

    expected = {"approve": "pending", "decline": "pending", "restore": "removed"}.get(
        action, "active"
    )
    if target["status"] != expected:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="That person is already in the group."
            if expected == "pending"
            else "That person hasn't been let in yet.",
        )
    if action in ("make_co_lead", "make_member") and my_role != "lead":
        raise LEAD_ONLY
    if action == "remove" and target["role"] == "co_lead" and my_role != "lead":
        raise LEAD_ONLY

    new_role, new_status, audit_action = {
        "approve": (target["role"], "active", "member.approved"),
        "decline": ("member", "removed", "member.declined"),
        "make_co_lead": ("co_lead", "active", "member.made_co_lead"),
        "make_member": ("member", "active", "member.made_member"),
        "remove": ("member", "removed", "member.removed"),
        "restore": ("member", "active", "member.restored"),
    }[action]
    # The WHERE repeats what was checked, so a concurrent change makes this a no-op.
    changed = session.execute(
        text(
            """
            UPDATE group_members
            SET role = CAST(:role AS group_role), status = CAST(:status AS member_status),
                updated_at = now()
            WHERE group_id = :group_id AND user_id = :user_id
              AND role = CAST(:old_role AS group_role)
              AND status = CAST(:old_status AS member_status)
            RETURNING user_id
            """
        ),
        {
            "group_id": group_id,
            "user_id": user_id,
            "role": new_role,
            "status": new_status,
            "old_role": target["role"],
            "old_status": target["status"],
        },
    ).scalar_one_or_none()
    if changed is None:  # pragma: no cover - only under a concurrent change
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Someone else just changed this. Try again."
        )
    if action in ("approve", "restore"):
        # Their player record, so they can be put in games (a declined person never had one).
        session.execute(
            text(
                """
                INSERT INTO players (group_id, user_id, display_name)
                SELECT :group_id, u.id, u.display_name FROM users u WHERE u.id = :user_id
                ON CONFLICT (group_id, user_id) DO NOTHING
                """
            ),
            {"group_id": group_id, "user_id": user_id},
        )
    _audit(session, group_id, me, audit_action, user_id)

    detail = group_detail(session, me, group_id)
    if detail is None:  # pragma: no cover - an admin always sees their group
        raise NOT_FOUND
    return detail
