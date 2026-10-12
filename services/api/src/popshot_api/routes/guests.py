"""A crew's guests: players added by name who haven't signed up.

Everyone in the crew sees the guests and how many games each has played. A lead or co-lead
can rename a guest (row-level security allows no one else, migration 0021) or remove one
who isn't in any game, say a typo; a guest with games stays, so no game ever changes.
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from popshot_api.db import CurrentUserSession
from popshot_api.routes.games import _NAME_TAKEN, _require_member
from popshot_api.routes.groups import PersonName
from popshot_api.routes.invites import _audit, _require_admin

router = APIRouter(prefix="/v1/groups/{group_id}/guests")

GUEST_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, detail="We couldn't find that guest.")
IN_GAMES = HTTPException(
    status.HTTP_409_CONFLICT,
    detail="This guest is in games, so they stay. You can rename them instead.",
)


class Guest(BaseModel):
    id: UUID
    display_name: str
    games: int


class RenameGuest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: PersonName


class Removed(BaseModel):
    outcome: Literal["removed"]


_GUESTS = """
    SELECT p.id, p.display_name,
           (SELECT count(*) FROM match_players mp WHERE mp.player_id = p.id) AS games
    FROM players p
    WHERE p.group_id = :g AND p.user_id IS NULL
    ORDER BY lower(p.display_name), p.id
"""


@router.get("")
def list_guests(group_id: UUID, user: CurrentUserSession) -> list[Guest]:
    _require_member(user.session, user.user_id, group_id)
    rows = user.session.execute(text(_GUESTS), {"g": group_id}).mappings()
    return [Guest(**row) for row in rows]


@router.patch("/{guest_id}")
def rename_guest(
    group_id: UUID, guest_id: UUID, body: RenameGuest, user: CurrentUserSession
) -> Guest:
    session = user.session
    _require_admin(session, user.user_id, group_id)
    clash = session.execute(
        text(_NAME_TAKEN), {"group_id": group_id, "name": body.display_name}
    ).scalar_one_or_none()
    current = session.execute(
        text(
            "SELECT display_name FROM players WHERE id = :p AND group_id = :g AND user_id IS NULL"
        ),
        {"p": guest_id, "g": group_id},
    ).scalar_one_or_none()
    if current is None:
        raise GUEST_NOT_FOUND
    # A clash with the guest's own name (a change of case, say) is fine.
    if clash is not None and current.lower() != body.display_name.lower():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"There's already a player called {body.display_name}.",
        )
    session.execute(
        text("UPDATE players SET display_name = :name WHERE id = :p AND group_id = :g"),
        {"name": body.display_name, "p": guest_id, "g": group_id},
    )
    _audit(session, group_id, user.user_id, "player.guest_renamed", guest_id)
    row = session.execute(text(_GUESTS), {"g": group_id}).mappings()
    return next(Guest(**r) for r in row if r["id"] == guest_id)


@router.delete("/{guest_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_guest(group_id: UUID, guest_id: UUID, user: CurrentUserSession) -> Response:
    session = user.session
    _require_admin(session, user.user_id, group_id)
    in_group = session.execute(
        text("SELECT 1 FROM players WHERE id = :p AND group_id = :g AND user_id IS NULL"),
        {"p": guest_id, "g": group_id},
    ).scalar_one_or_none()
    if in_group is None:
        raise GUEST_NOT_FOUND
    outcome = session.execute(text("SELECT app_remove_guest(:p)"), {"p": guest_id}).scalar_one()
    if outcome == "in_games":
        raise IN_GAMES
    if outcome != "removed":
        raise GUEST_NOT_FOUND
    return Response(status_code=status.HTTP_204_NO_CONTENT)
