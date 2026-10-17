"""Groups: create one, list yours, open one, change its settings, leave it, delete it.

Every query filters explicitly by the signed-in user; row-level security is the backstop,
not the filter. A group you can't see is a 404, never a 403, so the API doesn't confirm that
a group exists to someone outside it.
"""

import re
import unicodedata
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)
from sqlalchemy import text
from sqlalchemy.orm import Session

from popshot_api.courts import list_courts
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


Day = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
TimeOfDay = Literal["morning", "midday", "evening"]
DAYS: tuple[Day, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
TIMES: tuple[TimeOfDay, ...] = ("morning", "midday", "evening")

# Shown to people outside the crew, so no links, web or email addresses (as the database's
# check in migration 0022).
_LINK = re.compile(
    r"https?://|www\.|[\w.%+-]+@[\w-]+\.[a-z]|"
    r"\b[\w-]+\.(com|net|org|io|app|co|ly|me|gg|xyz|info|biz|link|site)\b",
    re.IGNORECASE,
)


def _no_links(value: str) -> str:
    if _LINK.search(value):
        raise ValueError("Leave out links and web or email addresses.")
    return value


About = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    AfterValidator(_no_control_characters),
    AfterValidator(_no_links),
]
CourtName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
    AfterValidator(_no_control_characters),
    AfterValidator(_no_links),
]


# An IANA time zone name such as "America/New_York", as browsers give it (Intl). The
# database keeps only names Postgres knows (migration 0040); zone_to_keep asks it first.
TimeZone = Annotated[
    str,
    StringConstraints(min_length=1, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_+/-]{0,63}$"),
]


# Zones IANA renamed, under the old names browsers still report (ICU keeps them). Postgres
# builds without the old aliases (Debian's tzdata without tzdata-legacy) refuse them, so
# the current name is kept instead.
RENAMED_ZONES = {
    "Africa/Asmera": "Africa/Asmara",
    "America/Buenos_Aires": "America/Argentina/Buenos_Aires",
    "America/Catamarca": "America/Argentina/Catamarca",
    "America/Cordoba": "America/Argentina/Cordoba",
    "America/Godthab": "America/Nuuk",
    "America/Indianapolis": "America/Indiana/Indianapolis",
    "America/Jujuy": "America/Argentina/Jujuy",
    "America/Louisville": "America/Kentucky/Louisville",
    "America/Mendoza": "America/Argentina/Mendoza",
    "Asia/Calcutta": "Asia/Kolkata",
    "Asia/Katmandu": "Asia/Kathmandu",
    "Asia/Rangoon": "Asia/Yangon",
    "Asia/Saigon": "Asia/Ho_Chi_Minh",
    "Atlantic/Faeroe": "Atlantic/Faroe",
    "Europe/Kiev": "Europe/Kyiv",
    "Pacific/Enderbury": "Pacific/Kanton",
    "Pacific/Ponape": "Pacific/Pohnpei",
    "Pacific/Truk": "Pacific/Chuuk",
}


def zone_to_keep(session: Session, name: str) -> str | None:
    """The zone's current name when Postgres knows it, else None."""
    current = RENAMED_ZONES.get(name, name)
    known = session.execute(
        text("SELECT EXISTS (SELECT 1 FROM pg_timezone_names WHERE name = :name)"),
        {"name": current},
    ).scalar_one()
    return current if known else None


class CrewProfile(BaseModel):
    """The whole profile, replaced at once. An empty "about" clears it."""

    model_config = ConfigDict(extra="forbid")

    about: About | None = None
    usual_days: list[Day] = Field(default_factory=list, max_length=7)
    usual_times: list[TimeOfDay] = Field(default_factory=list, max_length=3)

    @field_validator("about", mode="before")
    @classmethod
    def _blank_is_none(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value


class CreateGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: GroupName
    default_format: Format = "doubles"
    default_points_to: Literal[11, 15, 21] = 11
    default_win_by_two: bool = True
    # The creator's own time zone. One Postgres doesn't know is left out, never refused.
    time_zone: TimeZone | None = None


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
    # When they first joined (or asked to).
    joined_at: datetime
    # Their latest game in this group, if any.
    last_played_at: datetime | None = None


class FormerMember(BaseModel):
    user_id: UUID
    display_name: str
    avatar_url: str | None
    # When they were removed or declined.
    since: datetime


class Court(BaseModel):
    id: UUID
    # The crew's own name for it.
    label: str
    # Set when it was found on Google Maps, for an "Open in Maps" link.
    google_place_id: str | None
    is_default: bool


class GroupDetail(GroupSummary):
    default_format: Format
    default_points_to: int
    default_win_by_two: bool
    created_at: datetime
    # Its days (and recaps) follow this clock. None until a lead's browser sends it.
    time_zone: str | None = None
    # The crew profile.
    about: str | None = None
    usual_days: list[Day] = []
    usual_times: list[TimeOfDay] = []
    # The crew's saved courts (migration 0036, ADR 0007), default included: members only.
    courts: list[Court] = []
    # Open crews (0038): anyone on Popshot can find the crew and join, up to max_members.
    open_to_all: bool = False
    max_members: int = 12
    # Popshot's staff took it off the listing; its lead can't open it until it's relisted.
    unlisted: bool = False
    # It was closed because its default court stopped being one from the map: leads see a
    # note to pick one, until the crew opens again.
    closed_for_court: bool = False
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
    time_zone: TimeZone | None = None


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
    zone = body.time_zone and zone_to_keep(user.session, body.time_zone)
    if zone:
        user.session.execute(
            text("UPDATE groups SET time_zone = :time_zone WHERE id = :group_id"),
            {"time_zone": zone, "group_id": group_id},
        )
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
                       g.default_win_by_two, g.created_at, g.time_zone,
                       g.about, g.usual_days, g.usual_times,
                       g.open_to_all, g.max_members, g.unlisted_at IS NOT NULL AS unlisted,
                       g.closed_for_court_at IS NOT NULL AS closed_for_court,
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
                SELECT u.id AS user_id, u.display_name, u.avatar_url, gm.role, gm.status,
                       gm.created_at AS joined_at,
                       (SELECT max(m.played_at) FROM players p
                        JOIN match_players mp ON mp.player_id = p.id
                        JOIN matches m ON m.id = mp.match_id
                        WHERE p.group_id = gm.group_id AND p.user_id = gm.user_id
                       ) AS last_played_at
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
    # crew_courts' policy shows them to active members only.
    saved = list_courts(session, group_id) if group["my_status"] == "active" else []
    return GroupDetail(
        **group,
        courts=[Court(**asdict(c)) for c in saved],
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
    """Rename the group, change its time zone or the rules new games start with. Leads and
    co-leads."""
    session, me = user.session, user.user_id
    if _my_membership(session, me, group_id) not in ("lead", "co_lead"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Only the group's lead or a co-lead can do that."
        )
    zone = body.time_zone and zone_to_keep(session, body.time_zone)
    if body.time_zone is not None and not zone:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="We don't know that time zone."
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
                    default_win_by_two = coalesce(:default_win_by_two, default_win_by_two),
                    time_zone = coalesce(:time_zone, time_zone)
                WHERE id = :group_id
                """
            ),
            {
                "group_id": group_id,
                "name": body.name,
                "default_format": body.default_format,
                "default_points_to": body.default_points_to,
                "default_win_by_two": body.default_win_by_two,
                "time_zone": zone,
            },
        )
        _log(session, group_id, me, "group.updated", group_id)
    return _detail_or_404(session, me, group_id)


def _in_order(values: list[str], order: tuple[str, ...]) -> list[str]:
    return [v for v in order if v in values]


@router.put("/{group_id}/profile")
def set_profile(group_id: UUID, body: CrewProfile, user: CurrentUserSession) -> GroupDetail:
    """The crew profile: about, and usual days and times. Leads and co-leads.

    Its courts are saved separately (routes/courts.py)."""
    session, me = user.session, user.user_id
    if _my_membership(session, me, group_id) not in ("lead", "co_lead"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Only the group's lead or a co-lead can do that."
        )
    session.execute(
        text(
            """
            UPDATE groups SET about = :about, usual_days = :days, usual_times = :times
            WHERE id = :group_id
            """
        ),
        {
            "group_id": group_id,
            "about": body.about,
            "days": _in_order(list(body.usual_days), DAYS),
            "times": _in_order(list(body.usual_times), TIMES),
        },
    )
    _log(session, group_id, me, "group.profile_updated", group_id)
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
