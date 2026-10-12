"""A group's calendar: its games and play nights between two times, for the Games tab.

The browser asks for whole days in its own time zone (a week, or a month's grid of up to six
weeks) and lays them out; this only filters by time. Games and nights come back in the same
shapes as their own lists, so the day view can show the same cards.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import AwareDatetime, BaseModel
from sqlalchemy import text

from popshot_api.db import CurrentUserSession
from popshot_api.routes.games import Match, _matches, _require_member
from popshot_api.routes.nights import _NIGHT_SQL, Night, _load

router = APIRouter(prefix="/v1")

# A month's grid is at most six weeks; a little over allows for a time-zone change inside it.
MAX_SPAN = timedelta(days=43)


class Calendar(BaseModel):
    # Newest first, like the games list.
    games: list[Match]
    # Soonest first, cancelled ones included (shown as cancelled).
    nights: list[Night]


@router.get("/groups/{group_id}/calendar")
def calendar(
    group_id: UUID,
    user: CurrentUserSession,
    start: Annotated[AwareDatetime, Query()],
    end: Annotated[AwareDatetime, Query()],
) -> Calendar:
    if end <= start:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="The end must be after the start."
        )
    if end - start > MAX_SPAN:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Ask for at most six weeks at a time."
        )
    session, me = user.session, user.user_id
    _require_member(session, me, group_id)
    games = _matches(session, me, group_id, window=(start, end))
    rows = session.execute(
        text(
            _NIGHT_SQL + " WHERE n.group_id = :g AND n.starts_at >= :start AND n.starts_at < :end"
            " ORDER BY n.starts_at"
        ),
        {"g": group_id, "start": start, "end": end},
    ).all()
    return Calendar(games=games, nights=_load(session, me, rows, datetime.now(UTC)))
