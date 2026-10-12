"""Recaps: a crew's outings, newest first, and each one's awards and commentary.

Worked out from the games on each read, like the stats: nothing new is stored. Members
only, the same as every other group route.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from popshot_api import recap as recaps
from popshot_api.db import CurrentUserSession
from popshot_api.recap_lines import commentary
from popshot_api.routes.board import group_matches
from popshot_api.routes.games import _require_member
from popshot_api.routes.stats import PlayerRef, _players

router = APIRouter(prefix="/v1/groups/{group_id}/recaps")

LISTED = 10
# A meetup belongs to an outing if it starts up to this long before the first game.
MEETUP_LEAD = timedelta(hours=3)

NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, detail="We couldn't find that recap.")


class AwardOut(BaseModel):
    kind: recaps.AwardKind
    players: list[PlayerRef]
    value: int


class PlayerGames(BaseModel):
    player: PlayerRef
    games: int


class RecapSummary(BaseModel):
    key: UUID
    start: datetime
    end: datetime
    games: int
    players: int
    venue: str | None
    headline: str


class RecapOut(RecapSummary):
    lines: list[str]
    newcomers: list[PlayerRef]
    awards: list[AwardOut]
    # Everyone who played, most games first.
    played: list[PlayerGames]
    match_ids: list[UUID]


def _crew_name(session: Session, group_id: UUID) -> str:
    return str(
        session.execute(text("SELECT name FROM groups WHERE id = :g"), {"g": group_id}).scalar_one()
    )


def _venue(session: Session, group_id: UUID, outing: recaps.Outing) -> str | None:
    """The meetup this outing was, if one was planned for then."""
    found = session.execute(
        text(
            """
            SELECT venue FROM play_nights
            WHERE group_id = :g AND cancelled_at IS NULL
              AND starts_at BETWEEN :earliest AND :latest
            ORDER BY abs(extract(epoch FROM starts_at - :start))
            LIMIT 1
            """
        ),
        {
            "g": group_id,
            "earliest": outing.start - MEETUP_LEAD,
            "latest": outing.end,
            "start": outing.start,
        },
    ).scalar_one_or_none()
    return str(found) if found is not None else None


@dataclass(frozen=True, slots=True)
class _Crew:
    session: Session
    group_id: UUID
    name: str
    players: dict[UUID, PlayerRef]

    @classmethod
    def load(cls, session: Session, group_id: UUID) -> "_Crew":
        return cls(session, group_id, _crew_name(session, group_id), _players(session, group_id))


def _alphabetical(people: Iterable[PlayerRef]) -> list[PlayerRef]:
    return sorted(people, key=lambda p: (p.display_name.casefold(), str(p.player_id)))


def _build(crew: _Crew, outing: recaps.Outing, earlier: list[recaps.Outing]) -> RecapOut:
    names = crew.players
    found = recaps.recap(outing, earlier)
    venue = _venue(crew.session, crew.group_id, outing)
    said = commentary(
        found, {pid: ref.display_name for pid, ref in names.items()}, crew.name, venue
    )
    return RecapOut(
        key=outing.key,
        start=outing.start,
        end=outing.end,
        games=len(outing.matches),
        players=len(found.players),
        venue=venue,
        headline=said.headline,
        lines=list(said.lines),
        newcomers=_alphabetical(names[pid] for pid in found.newcomers),
        awards=[
            AwardOut(
                kind=a.kind, players=_alphabetical(names[pid] for pid in a.players), value=a.value
            )
            for a in found.awards
        ],
        played=[PlayerGames(player=names[pid], games=n) for pid, n in found.players],
        match_ids=[m.id for m in outing.matches],
    )


@router.get("")
def list_recaps(group_id: UUID, user: CurrentUserSession) -> list[RecapSummary]:
    session = user.session
    _require_member(session, user.user_id, group_id)
    all_outings = recaps.outings(group_matches(session, group_id))
    crew = _Crew.load(session, group_id)
    newest = list(enumerate(all_outings))[::-1][:LISTED]
    return [RecapSummary(**_build(crew, o, all_outings[:i]).model_dump()) for i, o in newest]


@router.get("/{key}")
def get_recap(group_id: UUID, key: UUID, user: CurrentUserSession) -> RecapOut:
    session = user.session
    _require_member(session, user.user_id, group_id)
    found = recaps.find(recaps.outings(group_matches(session, group_id)), key)
    if found is None:
        raise NOT_FOUND
    outing, earlier = found
    return _build(_Crew.load(session, group_id), outing, earlier)
