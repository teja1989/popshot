"""A crew's saved courts (migration 0036, ADR 0007): up to 5, one of them the default.

Leads and co-leads add a court by typing its name, or by picking it from a Google Maps search
(routes/places.py) and naming it. Picking from Google is counted against the same limits as
any Google lookup and needs the courts.places switch; typed courts don't. A court's Google
place can't change: remove it and add the new one.
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from popshot_api.courts import (
    MAX_COURTS,
    CourtRefusedError,
    add_court,
    list_courts,
    make_default,
    remove_court,
    settle,
)
from popshot_api.db import CurrentUserSession
from popshot_api.places import PlacesUnavailableError
from popshot_api.routes.features import feature_on
from popshot_api.routes.groups import (
    NOT_FOUND,
    CourtName,
    GroupDetail,
    _detail_or_404,
    _log,
    _my_membership,
)
from popshot_api.routes.places import ADMINS_ONLY, PlaceId, _count, _places, upsert_place
from popshot_api.routes.places import FEATURE as PLACES_FEATURE

router = APIRouter(prefix="/v1/groups")

REFUSED = {
    "full": HTTPException(status.HTTP_409_CONFLICT, detail="A crew can save up to 5 courts."),
    "saved": HTTPException(status.HTTP_409_CONFLICT, detail="That court is already saved."),
}
NO_SUCH_COURT = HTTPException(status.HTTP_404_NOT_FOUND, detail="We couldn't find that court.")


class NewCourt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The crew's own name for it: Google's name for a place can't be kept.
    label: CourtName
    # From a Google Maps search; leave out for a court typed by name.
    place_id: PlaceId | None = None
    # The search's Google session, which the pick ends.
    session: UUID | None = None


class CourtChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: CourtName | None = None
    # Make it the default (to change the default, make another court the default).
    is_default: Literal[True] | None = None


class CourtResult(BaseModel):
    # For a Google court: 'not_found' or 'unavailable' when Google couldn't place it.
    outcome: Literal["saved", "not_found", "unavailable"]
    group: GroupDetail


def _require_admin(user: CurrentUserSession, group_id: UUID) -> None:
    if _my_membership(user.session, user.user_id, group_id) not in ("lead", "co_lead"):
        raise ADMINS_ONLY


@router.post("/{group_id}/courts")
def add(group_id: UUID, body: NewCourt, request: Request, user: CurrentUserSession) -> CourtResult:
    """Save a court, typed or from Google. The crew's first court becomes its default."""
    session, me = user.session, user.user_id
    _require_admin(user, group_id)
    place = None
    if body.place_id is not None:
        places = _places(request)
        if not feature_on(session, PLACES_FEATURE, group_id):
            raise NOT_FOUND
        # Refuse what's sure to be refused before asking Google: a refusal after the lookup
        # would undo its count along with the request.
        saved = list_courts(session, group_id)
        if len(saved) >= MAX_COURTS:
            raise REFUSED["full"]
        if any(c.google_place_id == body.place_id for c in saved):
            raise REFUSED["saved"]
        # Counted first, and "not found" or "unavailable" are answers, not errors: an error
        # would undo the count (see routes/places.py).
        _count(session, "pick")
        try:
            location = places.locate(body.place_id, str(body.session) if body.session else None)
        except PlacesUnavailableError:
            return CourtResult(outcome="unavailable", group=_detail_or_404(session, me, group_id))
        if location is None:
            return CourtResult(outcome="not_found", group=_detail_or_404(session, me, group_id))
        place = upsert_place(session, location)
    try:
        court = add_court(session, group_id, me, body.label, place)
    except CourtRefusedError as refused:
        raise REFUSED[refused.reason] from None
    _log(session, group_id, me, "group.court_added", court)
    return CourtResult(outcome="saved", group=_detail_or_404(session, me, group_id))


@router.patch("/{group_id}/courts/{court_id}")
def change(
    group_id: UUID, court_id: UUID, body: CourtChange, user: CurrentUserSession
) -> GroupDetail:
    """Rename a court, or make it the default."""
    session, me = user.session, user.user_id
    _require_admin(user, group_id)
    found = session.execute(
        text("SELECT 1 FROM crew_courts WHERE group_id = :g AND id = :c"),
        {"g": group_id, "c": court_id},
    ).first()
    if found is None:
        raise NO_SUCH_COURT
    if body.label is not None:
        session.execute(
            text("UPDATE crew_courts SET label = :label, updated_at = now() WHERE id = :c"),
            {"label": body.label, "c": court_id},
        )
    if body.is_default:
        make_default(session, group_id, court_id)
        settle(session)
    _log(session, group_id, me, "group.court_changed", court_id)
    return _detail_or_404(session, me, group_id)


@router.delete("/{group_id}/courts/{court_id}")
def remove(group_id: UUID, court_id: UUID, user: CurrentUserSession) -> GroupDetail:
    """Remove a court. Meetups planned there keep their venue's name."""
    session, me = user.session, user.user_id
    _require_admin(user, group_id)
    if not remove_court(session, group_id, court_id):
        raise NO_SUCH_COURT
    settle(session)
    _log(session, group_id, me, "group.court_removed", court_id)
    return _detail_or_404(session, me, group_id)
