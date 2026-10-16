"""Searching Google Places for a crew's courts (popshot_api.places, migrations 0035 and 0036).

Leads and co-leads search here, then save the court they pick under their own name for it
(routes/courts.py). Only the place's Google ID and its coordinates (refreshed monthly) are kept.

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
from popshot_api.places import Location, Places, PlacesUnavailableError, Suggestion
from popshot_api.routes.features import feature_on
from popshot_api.routes.groups import (
    NOT_FOUND,
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


def upsert_place(session: Session, location: Location) -> UUID:
    """The place's row, with fresh coordinates."""
    place_id: UUID = session.execute(
        text("SELECT app_upsert_place(:gid, :lat, :lng)"),
        {"gid": location.place_id, "lat": location.lat, "lng": location.lng},
    ).scalar_one()
    return place_id


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
