"""Feature switches (migration 0027): what's on in your crews, read fresh on every request.

The app hides or shows things from GET /v1/me/features; the server decides for real, with
feature_on (or, for event functions to come, app_feature_on inside the database function).
"""

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from popshot_api.db import CurrentUserSession

router = APIRouter(prefix="/v1")


def feature_on(session: Session, key: str, group_id: UUID) -> bool:
    """Is `key` on for this crew? False unless the signed-in person is an active member."""
    on: bool = session.execute(
        text("SELECT app_feature_on(:key, :group)"), {"key": key, "group": group_id}
    ).scalar_one()
    return on


class MyFeatures(BaseModel):
    # What's on in each of your crews.
    crews: dict[UUID, list[str]]
    # What's on in at least one of them: for things that aren't about one crew (a menu tab).
    everywhere: list[str]
    # Switches in the 'you' area, which are per person, not per crew (migration 0032).
    you: list[str]
    # Live anywhere, in your crews or not (migration 0039): for what anyone can browse, like
    # Find. Keys only, never which crews.
    live: list[str] = []


@router.get("/me/features")
def my_features(user: CurrentUserSession) -> MyFeatures:
    rows = user.session.execute(text("SELECT group_id, feature FROM app_my_features()")).all()
    crews: dict[UUID, list[str]] = {}
    for row in rows:
        crews.setdefault(row.group_id, []).append(row.feature)
    you = list(
        user.session.execute(text("SELECT feature FROM app_my_personal_features()")).scalars()
    )
    live = list(user.session.execute(text("SELECT app_live_features()")).scalars())
    return MyFeatures(
        crews=crews, everywhere=sorted({row.feature for row in rows}), you=you, live=live
    )


def feature_live(session: Session, key: str) -> bool:
    """Is `key` on for everyone, or for at least one crew (migration 0039)?"""
    return key in session.execute(text("SELECT app_live_features()")).scalars().all()
