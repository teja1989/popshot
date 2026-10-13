"""Shared recap links: a card anyone with the link can open, no sign-in needed.

A member shares an outing's recap; the link carries a random token, shown once, and only its
SHA-256 is stored (like invite links). Links last 30 days. Whoever made one, or a lead or
co-lead, can turn the outing's links off.

The card shows first names, scores and awards. It leaves out the venue (it could be
someone's home) and names nobody who chose to stay off shared cards: they show as "Crew
member", and lines about only them are left out. AI words already written for the outing
are used only if they name none of those people and don't mention the venue; the card never
asks the AI to write.

The token travels in the request body, not the path, so it stays out of request logs. An
unknown, malformed, turned-off or expired link is one 404, so a caller can't tell which.
"""

import hashlib
import re
import secrets
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from popshot_api import ai_recap
from popshot_api import recap as recaps
from popshot_api.db import CurrentUserSession, PublicSession
from popshot_api.rating import GameScore, PlayedMatch
from popshot_api.recap_lines import NAMES_SHOWN, Commentary, commentary, first_name
from popshot_api.routes.board import group_matches
from popshot_api.routes.games import _require_member
from popshot_api.routes.recaps import MEETUP_LEAD
from popshot_api.routes.recaps import NOT_FOUND as RECAP_NOT_FOUND

router = APIRouter()

# Live links one person may have in a group at once. Plenty for sharing every outing,
# and stops a script from filling the table.
MAX_LIVE_SHARES = 20
HIDDEN_NAME = "Crew member"

# secrets.token_urlsafe(32): 32 random bytes, 43 URL-safe characters.
TOKEN_BYTES = 32
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")

DEAD_LINK = HTTPException(
    status.HTTP_404_NOT_FOUND, detail="This recap link isn't available any more."
)
TOO_MANY = HTTPException(
    status.HTTP_429_TOO_MANY_REQUESTS,
    detail="You have a lot of shared links on. Turn some off, or try again later.",
)


def _digest(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


class NewShare(BaseModel):
    # Shown once. The server keeps only its hash.
    token: str
    expires_at: datetime


class ShareStatus(BaseModel):
    # Links to this recap that are on, and how many of them you can turn off.
    live: int
    yours_to_turn_off: int


class TurnedOff(BaseModel):
    turned_off: int


class ShareToken(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: Annotated[str, Field(max_length=64)]


class SharedNames(BaseModel):
    # First names that may be shown, and how many more people there were.
    names: list[str]
    more: int


class SharedAward(SharedNames):
    kind: recaps.AwardKind
    value: int


class SharedPlayer(BaseModel):
    name: str
    games: int


class SharedMatch(BaseModel):
    team_a: list[str]
    team_b: list[str]
    # [team A's points, team B's points] for each game.
    games: list[tuple[int, int]]


class SharedRecap(BaseModel):
    crew: str
    start: datetime
    end: datetime
    games: int
    players: int
    headline: str
    lines: list[str]
    written_by: Literal["popshot", "ai"]
    newcomers: SharedNames
    awards: list[SharedAward]
    played: list[SharedPlayer]
    matches: list[SharedMatch]
    expires_at: datetime


def _outing_or_404(session: Session, group_id: UUID, key: UUID) -> None:
    if recaps.find(recaps.outings(group_matches(session, group_id)), key) is None:
        raise RECAP_NOT_FOUND


_STATUS = text(
    """
    SELECT count(*) AS live,
           count(*) FILTER (WHERE created_by = :me OR app_is_admin(group_id)) AS mine
    FROM recap_shares
    WHERE group_id = :g AND outing_key = :k AND revoked_at IS NULL AND expires_at > now()
    """
)


@router.get("/v1/groups/{group_id}/recaps/{key}/share")
def share_status(group_id: UUID, key: UUID, user: CurrentUserSession) -> ShareStatus:
    session = user.session
    _require_member(session, user.user_id, group_id)
    row = session.execute(_STATUS, {"g": group_id, "k": key, "me": user.user_id}).one()
    return ShareStatus(live=row.live, yours_to_turn_off=row.mine)


@router.post("/v1/groups/{group_id}/recaps/{key}/share", status_code=status.HTTP_201_CREATED)
def share_recap(group_id: UUID, key: UUID, user: CurrentUserSession) -> NewShare:
    session = user.session
    _require_member(session, user.user_id, group_id)
    _outing_or_404(session, group_id, key)
    live = session.execute(
        text(
            "SELECT count(*) FROM recap_shares WHERE group_id = :g AND created_by = :me "
            "AND revoked_at IS NULL AND expires_at > now()"
        ),
        {"g": group_id, "me": user.user_id},
    ).scalar_one()
    if live >= MAX_LIVE_SHARES:
        raise TOO_MANY
    token = secrets.token_urlsafe(TOKEN_BYTES)
    expires_at = session.execute(
        text(
            "INSERT INTO recap_shares (token_hash, group_id, outing_key, created_by) "
            "VALUES (:h, :g, :k, :me) RETURNING expires_at"
        ),
        {"h": _digest(token), "g": group_id, "k": key, "me": user.user_id},
    ).scalar_one()
    return NewShare(token=token, expires_at=expires_at)


@router.delete("/v1/groups/{group_id}/recaps/{key}/share")
def turn_off_shares(group_id: UUID, key: UUID, user: CurrentUserSession) -> TurnedOff:
    """Turns off this recap's links you made; a lead or co-lead turns off everyone's."""
    session = user.session
    _require_member(session, user.user_id, group_id)
    # Row-level security limits this to the links you may turn off.
    turned_off = session.execute(
        text(
            "UPDATE recap_shares SET revoked_at = now() "
            "WHERE group_id = :g AND outing_key = :k AND revoked_at IS NULL RETURNING 1"
        ),
        {"g": group_id, "k": key},
    ).all()
    return TurnedOff(turned_off=len(turned_off))


# The public card.


def _shared_matches(session: Session, digest: bytes) -> list[PlayedMatch]:
    rows = session.execute(text("SELECT * FROM app_public_share_matches(:h)"), {"h": digest}).all()
    return [
        PlayedMatch(
            id=row.id,
            played_at=row.played_at,
            team_a=row.team_a or [],
            team_b=row.team_b or [],
            games=[GameScore(a, b) for a, b in row.games or []],
        )
        for row in rows
        if row.team_a and row.team_b
    ]


def _venue(nights: Sequence[tuple[datetime, str]], outing: recaps.Outing) -> str | None:
    """Same rule as routes/recaps._venue, from the rows already read."""
    near = [
        (abs(starts_at - outing.start), venue)
        for starts_at, venue in nights
        if outing.start - MEETUP_LEAD <= starts_at <= outing.end
    ]
    return min(near, key=lambda n: n[0])[1] if near else None


def _ai_words(  # noqa: PLR0913
    session: Session,
    request: Request,
    *,
    digest: bytes,
    facts: Mapping[str, Any],
    hidden_names: set[str],
    venue: str | None,
) -> Commentary | None:
    writer: ai_recap.RecapWriter | None = request.app.state.recap_writer
    # The switch (recaps.ai, migration 0027) hides AI words on shared links too.
    if (
        writer is None
        or not session.execute(
            text("SELECT app_share_feature_on(:h, 'recaps.ai')"), {"h": digest}
        ).scalar_one()
    ):
        return None
    row = session.execute(
        text("SELECT * FROM app_public_share_text(:h)"), {"h": digest}
    ).one_or_none()
    if row is None:
        return None
    # Only words written for exactly these facts (as ai_recap.kept).
    if row.status != "written" or row.facts_hash != ai_recap.facts_hash(facts, writer.model):
        return None
    said = Commentary(headline=row.headline, lines=tuple(row.lines))
    words = " ".join([said.headline, *said.lines])
    if hidden_names & set(ai_recap.WORD.findall(words)):
        return None
    if venue and venue.casefold() in words.casefold():
        return None
    return said


def _names(ids: Sequence[UUID], shown: dict[UUID, str]) -> SharedNames:
    names = [shown[pid] for pid in ids if pid in shown][:NAMES_SHOWN]
    return SharedNames(names=names, more=len(ids) - len(names))


@router.post("/v1/public/recap")
def shared_recap(body: ShareToken, session: PublicSession, request: Request) -> SharedRecap:
    if not _TOKEN.fullmatch(body.token):
        raise DEAD_LINK
    digest = _digest(body.token)
    share = session.execute(text("SELECT * FROM app_public_share(:h)"), {"h": digest}).one_or_none()
    if share is None:
        raise DEAD_LINK
    found = recaps.find(recaps.outings(_shared_matches(session, digest)), share.outing_key)
    if found is None:
        raise DEAD_LINK
    outing, earlier = found
    people = session.execute(
        text("SELECT * FROM app_public_share_players(:h)"), {"h": digest}
    ).all()
    display = {p.player_id: p.display_name for p in people}
    hidden = {p.player_id for p in people if p.hidden}
    shown = {pid: first_name(name) for pid, name in display.items() if pid not in hidden}
    nights = [
        (n.starts_at, n.venue)
        for n in session.execute(text("SELECT * FROM app_public_share_nights(:h)"), {"h": digest})
    ]
    venue = _venue(nights, outing)

    result = recaps.recap(outing, earlier)
    said = _ai_words(
        session,
        request,
        digest=digest,
        facts=ai_recap.facts_for(result, display, share.crew, venue),
        hidden_names={first_name(display[pid]) for pid in hidden},
        venue=venue,
    )
    written_by: Literal["popshot", "ai"] = "ai"
    if said is None:
        said = commentary(result, display, share.crew, None, hidden)
        written_by = "popshot"

    def name(pid: UUID) -> str:
        return shown.get(pid, HIDDEN_NAME)

    return SharedRecap(
        crew=share.crew,
        start=outing.start,
        end=outing.end,
        games=len(outing.matches),
        players=len(result.players),
        headline=said.headline,
        lines=list(said.lines),
        written_by=written_by,
        newcomers=_names(result.newcomers, shown),
        awards=[
            SharedAward(kind=a.kind, value=a.value, **_names(a.players, shown).model_dump())
            for a in result.awards
        ],
        played=[SharedPlayer(name=name(pid), games=n) for pid, n in result.players],
        matches=[
            SharedMatch(
                team_a=[name(p) for p in m.team_a],
                team_b=[name(p) for p in m.team_b],
                games=[(g.team_a, g.team_b) for g in m.games],
            )
            for m in outing.matches
        ],
        expires_at=share.expires_at,
    )
