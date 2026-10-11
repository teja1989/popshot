"""Groups: create one, list yours, open one.

Every query filters explicitly by the signed-in user; row-level security is the backstop,
not the filter. A group you can't see is a 404, never a 403, so the API doesn't confirm that
a group exists to someone outside it.
"""

import unicodedata
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
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


class Member(BaseModel):
    user_id: UUID
    display_name: str
    avatar_url: str | None
    role: Role
    status: MemberStatus


class GroupDetail(GroupSummary):
    default_format: Format
    default_points_to: int
    default_win_by_two: bool
    created_at: datetime
    members: list[Member]


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
                   ) END AS member_preview
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

    active = sum(1 for m in members if m.status == "active")
    return GroupDetail(
        **group,
        member_count=active if group["my_status"] == "active" else None,
        members=members,
    )
