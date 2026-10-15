"""A crew's home court, found with Google Places (popshot_api.places, migration 0035).

Leads and co-leads search, pick one, and name it in their own words. Only the place's Google
ID, its coordinates (refreshed monthly) and the crew's own name are kept.

Every call to Google is counted first (app_place_lookup), which limits each person and
everyone together. "Not found" and "Google is unreachable" are normal answers, not errors: an
error would roll back the request, and with it the record of the lookup the limits count.
While the courts.places switch is off for the crew, these routes don't exist (404).
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from popshot_api.db import CurrentUserSession
from popshot_api.places import Places, PlacesUnavailableError, Suggestion
from popshot_api.routes.features import feature_on
from popshot_api.routes.groups import (
    NOT_FOUND,
    CourtName,
    GroupDetail,
    _detail_or_404,
    _log,
    _my_membership,
    _no_control_characters,
)

router = APIRouter(prefix="/v1/groups")

FEATURE = "courts.places"
TOO_MANY = "PS429"
RESTING = "PS503"

LIMITED = HTTPException(
    status.HTTP_429_TOO_MANY_REQUESTS,
    detail="That's a lot of searching for one hour. Try again in a little while.",
)
RESTING_TODAY = HTTPException(
    status.HTTP_503_SERVICE_UNAVAILABLE,
    detail="Court search is resting until tomorrow. You can still type the court's name.",
)
ADMINS_ONLY = HTTPException(
    status.HTTP_403_FORBIDDEN, detail="Only the crew's lead or a co-lead can do that."
)

SearchText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=80),
    AfterValidator(_no_control_characters),
]
# Google's place IDs: letters, digits, '-' and '_'.
PlaceId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,300}$")]


class PlaceSearch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: SearchText
    # Ties keystrokes and the pick into one Google session, billed as one.
    session: UUID


class PlaceSuggestion(BaseModel):
    place_id: str
    main: str
    secondary: str


class SearchResult(BaseModel):
    suggestions: list[PlaceSuggestion]
    # Google couldn't be reached: say so, and let them type the name instead.
    unavailable: bool = False


class HomePlaceChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    place_id: PlaceId
    session: UUID | None = None
    # The crew's own name for it: Google's name for the place can't be kept.
    label: CourtName


class HomePlaceResult(BaseModel):
    outcome: Literal["saved", "not_found", "unavailable"]
    group: GroupDetail


def _places(request: Request) -> Places:
    places: Places | None = request.app.state.places
    if places is None:
        raise NOT_FOUND
    return places


def _require_admin_with_feature(session: Session, me: UUID, group_id: UUID) -> None:
    role = _my_membership(session, me, group_id)  # 404 unless you're in the crew
    if not feature_on(session, FEATURE, group_id):
        raise NOT_FOUND
    if role not in ("lead", "co_lead"):
        raise ADMINS_ONLY


def _count(session: Session, lookup: Literal["search", "pick"]) -> None:
    try:
        with session.begin_nested():
            session.execute(text("SELECT app_place_lookup(:kind)"), {"kind": lookup})
    except DBAPIError as exc:
        state = getattr(exc.orig, "sqlstate", None)
        if state == TOO_MANY:
            raise LIMITED from None
        if state == RESTING:
            raise RESTING_TODAY from None
        raise


def _suggestion(found: Suggestion) -> PlaceSuggestion:
    return PlaceSuggestion(place_id=found.place_id, main=found.main, secondary=found.secondary)


@router.post("/{group_id}/places/search")
def search_places(
    group_id: UUID, body: PlaceSearch, request: Request, user: CurrentUserSession
) -> SearchResult:
    """Courts and parks matching what's typed so far, up to five. Nothing is kept."""
    places = _places(request)
    _require_admin_with_feature(user.session, user.user_id, group_id)
    _count(user.session, "search")
    try:
        found = places.suggest(body.text, str(body.session))
    except PlacesUnavailableError:
        return SearchResult(suggestions=[], unavailable=True)
    return SearchResult(suggestions=[_suggestion(f) for f in found])


@router.put("/{group_id}/home-place")
def set_home_place(
    group_id: UUID, body: HomePlaceChoice, request: Request, user: CurrentUserSession
) -> HomePlaceResult:
    """Make a place the crew's home court, under the crew's own name for it."""
    places = _places(request)
    session, me = user.session, user.user_id
    _require_admin_with_feature(session, me, group_id)
    _count(session, "pick")
    try:
        location = places.locate(body.place_id, str(body.session) if body.session else None)
    except PlacesUnavailableError:
        return HomePlaceResult(outcome="unavailable", group=_detail_or_404(session, me, group_id))
    if location is None:
        return HomePlaceResult(outcome="not_found", group=_detail_or_404(session, me, group_id))
    place_id = session.execute(
        text("SELECT app_upsert_place(:gid, :lat, :lng)"),
        {"gid": location.place_id, "lat": location.lat, "lng": location.lng},
    ).scalar_one()
    session.execute(
        text("UPDATE groups SET home_place_id = :place, home_place_label = :label WHERE id = :g"),
        {"place": place_id, "label": body.label, "g": group_id},
    )
    _log(session, group_id, me, "group.home_place_set", group_id)
    return HomePlaceResult(outcome="saved", group=_detail_or_404(session, me, group_id))


@router.delete("/{group_id}/home-place")
def clear_home_place(group_id: UUID, user: CurrentUserSession) -> GroupDetail:
    """No home court on the map any more (the place itself goes with the job's tidy-up)."""
    session, me = user.session, user.user_id
    _require_admin_with_feature(session, me, group_id)
    session.execute(
        text("UPDATE groups SET home_place_id = NULL, home_place_label = NULL WHERE id = :g"),
        {"g": group_id},
    )
    _log(session, group_id, me, "group.home_place_cleared", group_id)
    return _detail_or_404(session, me, group_id)
