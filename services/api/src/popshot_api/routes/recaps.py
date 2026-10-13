"""Recaps: a crew's outings, newest first, and each one's awards and commentary.

Worked out from the games on each read, like the stats: nothing new is stored. Members
only, the same as every other group route.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from popshot_api import ai_recap
from popshot_api import recap as recaps
from popshot_api.db import CurrentUserSession
from popshot_api.recap_lines import commentary, first_name
from popshot_api.routes.board import group_matches
from popshot_api.routes.features import feature_on
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
    # Who wrote the headline and lines: Popshot's own commentator, or the AI (shown as such).
    written_by: Literal["popshot", "ai"] = "popshot"
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


def _build(
    crew: _Crew,
    outing: recaps.Outing,
    earlier: list[recaps.Outing],
    writer: ai_recap.RecapWriter | None = None,
    *,
    ask: bool = False,
) -> RecapOut:
    names = crew.players
    found = recaps.recap(outing, earlier)
    venue = _venue(crew.session, crew.group_id, outing)
    display = {pid: ref.display_name for pid, ref in names.items()}
    said = commentary(found, display, crew.name, venue)
    written_by: Literal["popshot", "ai"] = "popshot"
    if writer is not None:
        facts = ai_recap.facts_for(found, display, crew.name, venue)
        by_ai = (
            ai_recap.ai_commentary(
                crew.session,
                writer=writer,
                group_id=crew.group_id,
                recap=found,
                facts=facts,
                crew_first_names={first_name(name) for name in display.values()},
                now=datetime.now(UTC),
            )
            if ask
            else ai_recap.already_written(
                crew.session, model=writer.model, group_id=crew.group_id, recap=found, facts=facts
            )
        )
        if by_ai is not None:
            said, written_by = by_ai, "ai"
    return RecapOut(
        key=outing.key,
        start=outing.start,
        end=outing.end,
        games=len(outing.matches),
        players=len(found.players),
        venue=venue,
        headline=said.headline,
        lines=list(said.lines),
        written_by=written_by,
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


def _writer(session: Session, request: Request, group_id: UUID) -> ai_recap.RecapWriter | None:
    """The AI writer, if this service has one and recaps.ai is on for the crew (0027)."""
    writer: ai_recap.RecapWriter | None = request.app.state.recap_writer
    if writer is None or not feature_on(session, "recaps.ai", group_id):
        return None
    return writer


@router.get("")
def list_recaps(group_id: UUID, user: CurrentUserSession, request: Request) -> list[RecapSummary]:
    session = user.session
    _require_member(session, user.user_id, group_id)
    all_outings = recaps.outings(group_matches(session, group_id))
    crew = _Crew.load(session, group_id)
    newest = list(enumerate(all_outings))[::-1][:LISTED]
    writer = _writer(session, request, group_id)
    return [
        RecapSummary(**_build(crew, o, all_outings[:i], writer).model_dump()) for i, o in newest
    ]


@router.get("/{key}")
def get_recap(group_id: UUID, key: UUID, user: CurrentUserSession, request: Request) -> RecapOut:
    session = user.session
    _require_member(session, user.user_id, group_id)
    found = recaps.find(recaps.outings(group_matches(session, group_id)), key)
    if found is None:
        raise NOT_FOUND
    outing, earlier = found
    # Only opening a recap asks the AI; the list shows words already written.
    writer = _writer(session, request, group_id)
    return _build(_Crew.load(session, group_id), outing, earlier, writer, ask=True)
