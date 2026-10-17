"""Recaps: a crew's days of games, newest first, and each one's awards and commentary.

Worked out from the games on each read, like the stats: nothing new is stored. A day needs
recap.MIN_GAMES games for a recap. Members only, the same as every other group route.
"""

from collections.abc import Iterable, Sequence
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


Nights = Sequence[tuple[datetime, str]]


def venue_for(nights: Nights, outing: recaps.Outing) -> str | None:
    """The meetup this outing was, if one was planned for then: the nearest to its first game
    that starts up to MEETUP_LEAD before it, and no later than its last."""
    near = [
        (abs(starts_at - outing.start), venue)
        for starts_at, venue in nights
        if outing.start - MEETUP_LEAD <= starts_at <= outing.end
    ]
    return min(near, key=lambda n: n[0])[1] if near else None


def _nights(session: Session, group_id: UUID, outings: Sequence[recaps.Outing]) -> Nights:
    """The crew's meetups that could belong to any of `outings`, in one query."""
    if not outings:
        return []
    rows = session.execute(
        text(
            "SELECT starts_at, venue FROM play_nights WHERE group_id = :g "
            "AND cancelled_at IS NULL AND starts_at BETWEEN :earliest AND :latest"
        ),
        {
            "g": group_id,
            "earliest": min(o.start for o in outings) - MEETUP_LEAD,
            "latest": max(o.end for o in outings),
        },
    )
    return [(row.starts_at, row.venue) for row in rows]


@dataclass(frozen=True, slots=True)
class _Crew:
    session: Session
    group_id: UUID
    name: str
    time_zone: str
    players: dict[UUID, PlayerRef]

    @classmethod
    def load(cls, session: Session, group_id: UUID) -> "_Crew":
        row = session.execute(
            text("SELECT name, time_zone FROM groups WHERE id = :g"), {"g": group_id}
        ).one()
        return cls(session, group_id, row.name, row.time_zone, _players(session, group_id))

    def outings(self) -> list[recaps.Outing]:
        return recaps.outings(
            group_matches(self.session, self.group_id), self.group_id, self.time_zone
        )


def _alphabetical(people: Iterable[PlayerRef]) -> list[PlayerRef]:
    return sorted(people, key=lambda p: (p.display_name.casefold(), str(p.player_id)))


def _build(  # noqa: PLR0913
    crew: _Crew,
    outing: recaps.Outing,
    earlier: list[recaps.Outing],
    nights: Nights,
    writer: ai_recap.RecapWriter | None = None,
    *,
    ask: bool = False,
    stored: dict[UUID, ai_recap.Stored] | None = None,
) -> RecapOut:
    """With `ask`, the AI may write words now; otherwise only `stored` words are used."""
    names = crew.players
    found = recaps.recap(outing, earlier)
    venue = venue_for(nights, outing)
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
                (stored or {}).get(outing.key), model=writer.model, facts=facts
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
    crew = _Crew.load(session, group_id)
    newest = recaps.with_recaps(crew.outings())[::-1][:LISTED]
    nights = _nights(session, group_id, [o for o, _ in newest])
    writer = _writer(session, request, group_id)
    stored = ai_recap.stored_many(session, group_id, [o.key for o, _ in newest]) if writer else {}
    return [
        RecapSummary(**_build(crew, o, earlier, nights, writer, stored=stored).model_dump())
        for o, earlier in newest
    ]


@router.get("/{key}")
def get_recap(group_id: UUID, key: UUID, user: CurrentUserSession, request: Request) -> RecapOut:
    session = user.session
    _require_member(session, user.user_id, group_id)
    crew = _Crew.load(session, group_id)
    found = recaps.find(crew.outings(), key)
    if found is None:
        raise NOT_FOUND
    outing, earlier = found
    # Only opening a recap asks the AI; the list shows words already written.
    writer = _writer(session, request, group_id)
    nights = _nights(session, group_id, [outing])
    return _build(crew, outing, earlier, nights, writer, ask=True)
