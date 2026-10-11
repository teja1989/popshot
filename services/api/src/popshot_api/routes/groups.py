"""Groups: create one, list yours, open one, change its settings, leave it, delete it.

Every query filters explicitly by the signed-in user; row-level security is the backstop,
not the filter. A group you can't see is a 404, never a 403, so the API doesn't confirm that
a group exists to someone outside it.
"""

import unicodedata
from datetime import datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints
from sqlalchemy import text
from sqlalchemy.orm import Session

from popshot_api.db import CurrentUserSession

router = APIRouter(prefix="/v1/groups")

Role = Literal["lead", "co_lead", "member"]
MemberStatus = Literal["active", "pending"]
Format = Literal["doubles", "singles"]

# A generous cap that stops a script from creating groups without end.
MAX_LED_GROUPS = 20
MEMBER_PREVIEW = 4

NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, detail="We couldn't find that group.")


def _no_control_characters(value: str) -> str:
    if any(unicodedata.category(ch) in {"Cc", "Cf", "Zl", "Zp"} for ch in value):
        raise ValueError("Use letters, numbers, spaces and punctuation only.")
    return value


GroupName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=60),
    AfterValidator(_no_control_characters),
]

# A player's or your own display name.
PersonName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=40),
    AfterValidator(_no_control_characters),
]


class CreateGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: GroupName
    default_format: Format = "doubles"
    default_points_to: Literal[11, 15, 21] = 11
    default_win_by_two: bool = True


class MemberPreview(BaseModel):
    display_name: str
    avatar_url: str | None


class GroupSummary(BaseModel):
    id: UUID
    name: str
    my_role: Role
    my_status: MemberStatus
    # Only for active members; someone waiting for approval doesn't see the roster yet.
    member_count: int | None
    # Up to MEMBER_PREVIEW active members, the lead first, for the faces on a group card.
    member_preview: list[MemberPreview] = []
    # Games logged in the group, and how many of them you played in. Active members only.
    games_logged: int | None = None
    my_games: int | None = None


class Member(BaseModel):
    user_id: UUID
    display_name: str
    avatar_url: str | None
    role: Role
    status: MemberStatus


class FormerMember(BaseModel):
    user_id: UUID
    display_name: str
    avatar_url: str | None
    # When they were removed or declined.
    since: datetime


class GroupDetail(GroupSummary):
    default_format: Format
    default_points_to: int
    default_win_by_two: bool
    created_at: datetime
    members: list[Member]
    # Leads and co-leads only: people removed or declined, who can be restored.
    former_members: list[FormerMember] = []


class GroupSettings(BaseModel):
    """What a lead or co-lead can change. Leave a field out to keep it."""

    model_config = ConfigDict(extra="forbid")

    name: GroupName | None = None
    default_format: Format | None = None
    default_points_to: Literal[11, 15, 21] | None = None
    default_win_by_two: bool | None = None


class DeletedGroup(BaseModel):
    id: UUID
    name: str
    deleted_at: datetime
    # The last moment it can be restored.
    restorable_until: datetime


RESTORE_DAYS = 30


@router.get("")
def list_groups(user: CurrentUserSession) -> list[GroupSummary]:
    rows = user.session.execute(
        text(
            """
            SELECT g.id, g.name, m.role AS my_role, m.status AS my_status,
                   CASE WHEN m.status = 'active' THEN (
                       SELECT count(*) FROM group_members a
                       WHERE a.group_id = g.id AND a.status = 'active'
                   ) END AS member_count,
                   CASE WHEN m.status = 'active' THEN (
                       SELECT coalesce(json_agg(json_build_object(
                                  'display_name', p.display_name, 'avatar_url', p.avatar_url
                              ) ORDER BY p.ord), '[]'::json)
                       FROM (
                           SELECT u.display_name, u.avatar_url,
                                  row_number() OVER (
                                      ORDER BY array_position(
                                          ARRAY['lead', 'co_lead', 'member']::group_role[], a.role
                                      ), a.created_at, u.id
                                  ) AS ord
                           FROM group_members a
                           JOIN users u ON u.id = a.user_id
                           WHERE a.group_id = g.id AND a.status = 'active'
                       ) p
                       WHERE p.ord <= :preview
                   ) END AS member_preview,
                   CASE WHEN m.status = 'active' THEN (
                       SELECT count(*) FROM matches x WHERE x.group_id = g.id
                   ) END AS games_logged,
                   CASE WHEN m.status = 'active' THEN (
                       SELECT count(DISTINCT mp.match_id)
                       FROM match_players mp JOIN players p ON p.id = mp.player_id
                       WHERE mp.group_id = g.id AND p.user_id = :me
                   ) END AS my_games
            FROM group_members m
            JOIN groups g ON g.id = m.group_id
            WHERE m.user_id = :me AND m.status IN ('active', 'pending')
            ORDER BY lower(g.name), g.id
            """
        ),
        {"me": user.user_id, "preview": MEMBER_PREVIEW},
    ).mappings()
    return [GroupSummary(**{**row, "member_preview": row["member_preview"] or []}) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_group(body: CreateGroup, user: CurrentUserSession) -> GroupDetail:
    led = user.session.execute(
        text(
            "SELECT count(*) FROM group_members "
            "WHERE user_id = :me AND role = 'lead' AND status = 'active'"
        ),
        {"me": user.user_id},
    ).scalar_one()
    if led >= MAX_LED_GROUPS:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"You can lead up to {MAX_LED_GROUPS} groups.",
        )
    group_id: UUID = user.session.execute(
        text(
            "SELECT app_create_group(:name, CAST(:fmt AS match_format), "
            "CAST(:points AS smallint), :win_by_two)"
        ),
        {
            "name": body.name,
            "fmt": body.default_format,
            "points": body.default_points_to,
            "win_by_two": body.default_win_by_two,
        },
    ).scalar_one()
    detail = group_detail(user.session, user.user_id, group_id)
    if detail is None:  # pragma: no cover - the creator is always its active lead
        raise NOT_FOUND
    return detail


@router.get("/deleted")
def deleted_groups(user: CurrentUserSession) -> list[DeletedGroup]:
    """Groups you lead that were deleted in the last RESTORE_DAYS days."""
    rows = user.session.execute(text("SELECT * FROM app_deleted_groups()")).mappings()
    return [
        DeletedGroup(
            id=row["group_id"],
            name=row["name"],
            deleted_at=row["deleted_at"],
            restorable_until=row["deleted_at"] + timedelta(days=RESTORE_DAYS),
        )
        for row in rows
    ]


@router.get("/{group_id}")
def get_group(group_id: UUID, user: CurrentUserSession) -> GroupDetail:
    detail = group_detail(user.session, user.user_id, group_id)
    if detail is None:
        raise NOT_FOUND
    return detail


def group_detail(session: Session, me: UUID, group_id: UUID) -> GroupDetail | None:
    group = (
        session.execute(
            text(
                """
                SELECT g.id, g.name, g.default_format, g.default_points_to,
                       g.default_win_by_two, g.created_at,
                       m.role AS my_role, m.status AS my_status
                FROM groups g
                JOIN group_members m ON m.group_id = g.id AND m.user_id = :me
                WHERE g.id = :group_id AND m.status IN ('active', 'pending')
                """
            ),
            {"me": me, "group_id": group_id},
        )
        .mappings()
        .one_or_none()
    )
    if group is None:
        return None

    members: list[Member] = []
    if group["my_status"] == "active":
        # Leads and co-leads also see who is waiting for approval.
        is_admin = group["my_role"] in ("lead", "co_lead")
        rows = session.execute(
            text(
                """
                SELECT u.id AS user_id, u.display_name, u.avatar_url, gm.role, gm.status
                FROM group_members gm
                JOIN users u ON u.id = gm.user_id
                WHERE gm.group_id = :group_id
                  AND (gm.status = 'active' OR (gm.status = 'pending' AND :is_admin))
                -- Active members first (the enum itself declares 'pending' first).
                ORDER BY gm.status = 'pending',
                         array_position(ARRAY['lead', 'co_lead', 'member']::group_role[], gm.role),
                         lower(u.display_name), u.id
                """
            ),
            {"group_id": group_id, "is_admin": is_admin},
        ).mappings()
        members = [Member(**row) for row in rows]

    former: list[FormerMember] = []
    if group["my_status"] == "active" and group["my_role"] in ("lead", "co_lead"):
        former = [
            FormerMember(**row)
            for row in session.execute(
                text("SELECT * FROM app_former_members(:group_id)"), {"group_id": group_id}
            ).mappings()
        ]

    active = sum(1 for m in members if m.status == "active")
    return GroupDetail(
        **group,
        member_count=active if group["my_status"] == "active" else None,
        members=members,
        former_members=former,
    )


def _my_membership(session: Session, me: UUID, group_id: UUID) -> Role:
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


def _log(session: Session, group_id: UUID, me: UUID, action: str, target: UUID) -> None:
    session.execute(
        text(
            "INSERT INTO audit_log (group_id, actor_user_id, action, target_id) "
            "VALUES (:group_id, :me, :action, :target)"
        ),
        {"group_id": group_id, "me": me, "action": action, "target": target},
    )


def _detail_or_404(session: Session, me: UUID, group_id: UUID) -> GroupDetail:
    detail = group_detail(session, me, group_id)
    if detail is None:  # pragma: no cover - checked by the caller already
        raise NOT_FOUND
    return detail


@router.patch("/{group_id}")
def update_group(group_id: UUID, body: GroupSettings, user: CurrentUserSession) -> GroupDetail:
    """Rename the group or change the rules new games start with. Leads and co-leads."""
    session, me = user.session, user.user_id
    if _my_membership(session, me, group_id) not in ("lead", "co_lead"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Only the group's lead or a co-lead can do that."
        )
    changes = body.model_dump(exclude_none=True)
    if changes:
        # Each column is set only when given; the statement itself never changes.
        session.execute(
            text(
                """
                UPDATE groups SET
                    name = coalesce(:name, name),
                    default_format = coalesce(CAST(:default_format AS match_format),
                                              default_format),
                    default_points_to = coalesce(CAST(:default_points_to AS smallint),
                                                 default_points_to),
                    default_win_by_two = coalesce(:default_win_by_two, default_win_by_two)
                WHERE id = :group_id
                """
            ),
            {
                "group_id": group_id,
                "name": body.name,
                "default_format": body.default_format,
                "default_points_to": body.default_points_to,
                "default_win_by_two": body.default_win_by_two,
            },
        )
        _log(session, group_id, me, "group.updated", group_id)
    return _detail_or_404(session, me, group_id)


@router.post("/{group_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave_group(group_id: UUID, user: CurrentUserSession) -> Response:
    """Leave a group, or cancel your request to join one. The lead hands over first.

    Your games stay in the group's history. You can ask to join again with a new invite.
    """
    session, me = user.session, user.user_id
    membership = (
        session.execute(
            text(
                "SELECT role, status FROM group_members "
                "JOIN groups ON groups.id = group_members.group_id "
                "WHERE group_id = :group_id AND user_id = :me AND status IN ('active', 'pending')"
            ),
            {"group_id": group_id, "me": me},
        )
        .mappings()
        .one_or_none()
    )
    if membership is None:
        raise NOT_FOUND
    if membership["role"] == "lead":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Make someone else the lead before you leave, or delete the group.",
        )
    if membership["status"] == "active":
        # Logged first: once you've left, you can't write to the group's log.
        _log(session, group_id, me, "member.left", me)
    session.execute(
        text(
            """
            UPDATE group_members
            SET status = 'removed', role = 'member', left_at = now(), updated_at = now()
            WHERE group_id = :group_id AND user_id = :me
            """
        ),
        {"group_id": group_id, "me": me},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(group_id: UUID, user: CurrentUserSession) -> Response:
    """Delete the group. Lead only. It can be restored for RESTORE_DAYS days."""
    session, me = user.session, user.user_id
    if _my_membership(session, me, group_id) != "lead":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Only the group's lead can do that.")
    deleted = session.execute(
        text("SELECT app_delete_group(:group_id)"), {"group_id": group_id}
    ).scalar_one()
    if not deleted:  # pragma: no cover - only under a concurrent hand-over
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Something changed. Try again.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{group_id}/restore")
def restore_group(group_id: UUID, user: CurrentUserSession) -> GroupDetail:
    """Bring back a group you lead, deleted in the last RESTORE_DAYS days."""
    restored = user.session.execute(
        text("SELECT app_restore_group(:group_id)"), {"group_id": group_id}
    ).scalar_one()
    if not restored:
        raise NOT_FOUND
    return _detail_or_404(user.session, user.user_id, group_id)
