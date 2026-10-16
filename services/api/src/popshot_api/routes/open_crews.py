"""Open crews (migration 0038): a lead opens a crew, anyone signed in finds it nearby and joins.

The listing shows an open crew's name, about, usual times, its court on the map and how far
it is, and how many members it has. The court is the crew's default court, which must be one
from the map (crew courts, ADR 0007). Who the members are, and everything else, stays for
members. Joining makes you an active member at once; the crew's leads get a push.

Where you search from goes in the request body, never the address, so it isn't in any log.
While the crew.open switch is off for a crew, it isn't listed, and its lead can't open it.
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from popshot_api.db import CurrentUserSession
from popshot_api.places import PlacesUnavailableError
from popshot_api.push import Message
from popshot_api.routes.features import feature_live, feature_on
from popshot_api.routes.groups import (
    NOT_FOUND,
    GroupDetail,
    _detail_or_404,
    _log,
    _my_membership,
    _no_control_characters,
    _no_links,
)
from popshot_api.routes.notifications import CurrentNotifier
from popshot_api.routes.places import (
    PlaceId,
    PlaceSearch,
    SearchResult,
    _count,
    _places,
    _suggestion,
)

router = APIRouter(prefix="/v1")

FEATURE = "crew.open"
TOO_MANY = "PS429"

ADMINS_ONLY = HTTPException(
    status.HTTP_403_FORBIDDEN, detail="Only the crew's lead or a co-lead can do that."
)
NEEDS_COURT = HTTPException(
    status.HTTP_409_CONFLICT,
    detail="Make a court from the map the crew's default first.",
)
UNLISTED = HTTPException(
    status.HTTP_409_CONFLICT,
    detail="This crew can't be listed right now. Write to us if that seems wrong.",
)
FULL = HTTPException(status.HTTP_409_CONFLICT, detail="This crew is full right now.")
JOINS_LIMITED = HTTPException(
    status.HTTP_429_TOO_MANY_REQUESTS,
    detail="That's a lot of crews for one day. Try again tomorrow.",
)
REPORTS_LIMITED = HTTPException(
    status.HTTP_429_TOO_MANY_REQUESTS,
    detail="Thanks. That's all the reports for today; we'll look at them.",
)

MembersCap = Annotated[int, Field(ge=2, le=100)]


class OpenCrewSearch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lat: Annotated[float, Field(ge=-90, le=90)]
    lng: Annotated[float, Field(ge=-180, le=180)]
    radius_km: Annotated[int, Field(ge=1, le=100)] = 25


class PlaceStart(BaseModel):
    """Search from a town, park or court picked from a typed search, when the phone's
    location isn't shared."""

    model_config = ConfigDict(extra="forbid")

    place_id: PlaceId
    # The typed search's Google session, which the pick ends.
    session: UUID | None = None
    radius_km: Annotated[int, Field(ge=1, le=100)] = 25


class OpenCrew(BaseModel):
    """What the listing shows. Never who the members are."""

    group_id: UUID
    name: str
    about: str | None
    usual_days: list[str]
    usual_times: list[str]
    # The crew's own name for its court, and Google's ID for it (a public place).
    court: str
    google_place_id: str
    distance_km: float
    members: int
    max_members: int
    full: bool
    # 'active' or 'pending' when you're already in it (or waiting), else None.
    my_status: Literal["active", "pending"] | None


class PlaceAnswer(BaseModel):
    # 'not_found' or 'unavailable' when Google couldn't place it: answers, not errors (an
    # error would undo the lookup's count, routes/places.py).
    outcome: Literal["found", "not_found", "unavailable"]
    crews: list["OpenCrew"]


class OpenSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    open: bool
    max_members: MembersCap = 12


class JoinResult(BaseModel):
    outcome: Literal["joined", "already"]
    group: GroupDetail


ReportNote = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=300),
    AfterValidator(_no_control_characters),
    AfterValidator(_no_links),
]


class Report(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Literal["spam", "unsafe", "offensive", "not_pickleball", "other"]
    note: ReportNote | None = None


def _limited(session: Session, sql: str, params: dict[str, object], limited: HTTPException) -> str:
    """Run a function that counts against a limit (PS429), in its own savepoint."""
    try:
        with session.begin_nested():
            outcome: str = session.execute(text(sql), params).scalar_one()
    except DBAPIError as exc:
        if getattr(exc.orig, "sqlstate", None) == TOO_MANY:
            raise limited from None
        raise
    return outcome


def _near(session: Session, lat: float, lng: float, radius_km: int) -> list[OpenCrew]:
    rows = session.execute(
        text("SELECT * FROM app_open_crews_near(:lat, :lng, :radius, 20)"),
        {"lat": lat, "lng": lng, "radius": radius_km},
    ).mappings()
    return [
        OpenCrew(
            group_id=row["group_id"],
            name=row["name"],
            about=row["about"],
            usual_days=row["usual_days"] or [],
            usual_times=row["usual_times"] or [],
            court=row["court"],
            google_place_id=row["google_place_id"],
            distance_km=float(row["distance_km"]),
            members=row["members"],
            max_members=row["max_members"],
            full=row["is_full"],
            my_status=row["my_status"],
        )
        for row in rows
    ]


@router.post("/open-crews/search")
def search_open_crews(body: OpenCrewSearch, user: CurrentUserSession) -> list[OpenCrew]:
    """Open crews near a point, nearest first (up to 20)."""
    return _near(user.session, body.lat, body.lng, body.radius_km)


def _require_find(request: Request, session: Session) -> None:
    """Typed searches call Google: only while Find is live, and only with places set up."""
    _places(request)
    if not feature_live(session, FEATURE):
        raise NOT_FOUND


@router.post("/open-crews/places")
def search_places_to_start(
    body: PlaceSearch, request: Request, user: CurrentUserSession
) -> SearchResult:
    """Towns, parks and courts matching what's typed so far, to search from. Nothing is kept."""
    _require_find(request, user.session)
    _count(user.session, "search")
    try:
        found = _places(request).suggest(body.text, str(body.session))
    except PlacesUnavailableError:
        return SearchResult(suggestions=[], unavailable=True)
    return SearchResult(suggestions=[_suggestion(f) for f in found])


@router.post("/open-crews/search/place")
def search_open_crews_from_place(
    body: PlaceStart, request: Request, user: CurrentUserSession
) -> PlaceAnswer:
    """Open crews near a picked place. The place's coordinates are used for this search only:
    not kept, and not sent back."""
    _require_find(request, user.session)
    _count(user.session, "pick")
    try:
        location = _places(request).locate(
            body.place_id, str(body.session) if body.session else None
        )
    except PlacesUnavailableError:
        return PlaceAnswer(outcome="unavailable", crews=[])
    if location is None:
        return PlaceAnswer(outcome="not_found", crews=[])
    return PlaceAnswer(
        outcome="found", crews=_near(user.session, location.lat, location.lng, body.radius_km)
    )


@router.post("/open-crews/{group_id}/join")
def join_open_crew(
    group_id: UUID, user: CurrentUserSession, notifier: CurrentNotifier
) -> JoinResult:
    """Join an open crew at once. Its lead and co-leads are told."""
    session, me = user.session, user.user_id
    outcome = _limited(session, "SELECT app_join_open_crew(:g)", {"g": group_id}, JOINS_LIMITED)
    if outcome == "full":
        raise FULL
    if outcome not in ("joined", "already"):
        # Closed, gone, or a lead removed you: the same answer, so nothing is revealed.
        raise NOT_FOUND
    group = _detail_or_404(session, me, group_id)
    if outcome == "joined":
        leads = [m.user_id for m in group.members if m.role in ("lead", "co_lead")]
        name = session.execute(
            text("SELECT display_name FROM users WHERE id = :me"), {"me": me}
        ).scalar_one()
        first = name.split()[0] if name.split() else name
        notifier.notify(
            session,
            leads,
            "requests",
            Message(
                title=f"{first} joined {group.name}",
                body="They found your crew on Popshot. Say hello!",
                url=f"/groups/{group_id}/members",
                tag=f"joined-{group_id}",
            ),
        )
    return JoinResult(outcome="joined" if outcome == "joined" else "already", group=group)


@router.post("/open-crews/{group_id}/report", status_code=status.HTTP_204_NO_CONTENT)
def report_open_crew(group_id: UUID, body: Report, user: CurrentUserSession) -> Response:
    """Tell Popshot's staff about a listing. Once a day per crew; 3 a day in all."""
    outcome = _limited(
        user.session,
        "SELECT app_report_open_crew(:g, :reason, :note)",
        {"g": group_id, "reason": body.reason, "note": body.note},
        REPORTS_LIMITED,
    )
    if outcome == "closed":
        raise NOT_FOUND
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/groups/{group_id}/open")
def set_open(
    group_id: UUID, body: OpenSettings, user: CurrentUserSession, notifier: CurrentNotifier
) -> GroupDetail:
    """Open or close the crew, and set how many members it takes from the listing."""
    session, me = user.session, user.user_id
    role = _my_membership(session, me, group_id)  # 404 unless you're in the crew
    if not feature_on(session, FEATURE, group_id):
        raise NOT_FOUND
    if role not in ("lead", "co_lead"):
        raise ADMINS_ONLY
    current = (
        session.execute(
            text(
                "SELECT open_to_all, max_members, app_crew_default_on_map(id) AS has_court, "
                "unlisted_at IS NOT NULL AS unlisted FROM groups WHERE id = :g"
            ),
            {"g": group_id},
        )
        .mappings()
        .one()
    )
    if body.open and not current["has_court"]:
        raise NEEDS_COURT
    if body.open and current["unlisted"]:
        raise UNLISTED
    session.execute(
        text(
            "UPDATE groups SET open_to_all = :open, max_members = :cap, "
            "opened_at = CASE WHEN :open AND NOT open_to_all THEN now() ELSE opened_at END "
            "WHERE id = :g"
        ),
        {"open": body.open, "cap": body.max_members, "g": group_id},
    )
    opened = body.open and not current["open_to_all"]
    closed = current["open_to_all"] and not body.open
    if opened or closed or body.max_members != current["max_members"]:
        action = "group.opened" if opened else "group.closed" if closed else "group.cap_changed"
        _log(session, group_id, me, action, group_id)
    group = _detail_or_404(session, me, group_id)
    if (
        opened
        and session.execute(text("SELECT app_claim_open_notice(:g)"), {"g": group_id}).scalar_one()
    ):
        others = [m.user_id for m in group.members if m.status == "active" and m.user_id != me]
        notifier.notify(
            session,
            others,
            "crew",
            Message(
                title=f"{group.name} is now open",
                body="Anyone on Popshot can find the crew and join. You can leave any time.",
                url=f"/groups/{group_id}",
                tag=f"open-{group_id}",
            ),
        )
    return group
