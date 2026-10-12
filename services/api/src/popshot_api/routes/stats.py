"""Head-to-head and fun stats: yours on the You page, the crew's highlights on the Board.

See popshot_api.stats for what counts as a close game, a skunk, an upset, a best partner
and a nemesis. Like crew points, everything is worked out from the games on each read.
"""

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from popshot_api import stats
from popshot_api.db import CurrentUserSession
from popshot_api.rating import START
from popshot_api.routes.board import group_matches, group_ratings
from popshot_api.routes.games import _require_member

router = APIRouter(prefix="/v1/groups/{group_id}")

# Windows the You page offers, in days (no value means all time).
WINDOWS = frozenset({30, 90})


class PlayerRef(BaseModel):
    player_id: UUID
    display_name: str
    is_guest: bool


class RecordOut(BaseModel):
    player: PlayerRef
    played: int
    won: int


class UpsetOut(BaseModel):
    match_id: UUID
    played_at: datetime
    winners: list[PlayerRef]
    losers: list[PlayerRef]
    gap: float


class Streak(BaseModel):
    result: Literal["W", "L"]
    length: int


class TimelinePointOut(BaseModel):
    played_at: datetime
    doubles: bool
    won: bool
    rating: float


class MyStats(BaseModel):
    # The window everything below covers, in days; None for all time. Best partner and
    # nemesis always cover all time, since they need MIN_PAIRING matches.
    days: int | None
    matches: int
    wins: int
    current_streak: Streak | None
    longest_win_streak: int
    close_won: int
    close_lost: int
    skunks_given: int
    skunks_taken: int
    upset_wins: int
    biggest_upset: UpsetOut | None
    best_partner: RecordOut | None
    nemesis: RecordOut | None
    # Everyone you've played against, most matches first.
    head_to_head: list[RecordOut]
    # Your matches in the window, oldest first, with your crew points after each.
    timeline: list[TimelinePointOut]
    # Crew points going into the window, and now (both all-time ratings).
    rating_start: float | None
    rating_now: float | None
    min_pairing: int = stats.MIN_PAIRING


class StreakHighlight(BaseModel):
    player: PlayerRef
    length: int


class GamesHighlight(BaseModel):
    player: PlayerRef
    matches: int


class WeeksHighlight(BaseModel):
    player: PlayerRef
    weeks: int


class PartnershipHighlight(BaseModel):
    players: list[PlayerRef]
    played: int
    won: int


class Highlights(BaseModel):
    longest_win_streak: StreakHighlight | None
    most_games: GamesHighlight | None
    biggest_upset: UpsetOut | None
    # Who has played every week lately, the crew's best partnership, and who's new.
    weeks_running: list[WeeksHighlight] = []
    best_partnership: PartnershipHighlight | None = None
    newcomers: list[PlayerRef] = []
    window_days: int = stats.HIGHLIGHT_WINDOW.days


def _players(session: Session, group_id: UUID) -> dict[UUID, PlayerRef]:
    rows = session.execute(
        text(
            "SELECT id, display_name, user_id IS NULL AS is_guest FROM players "
            "WHERE group_id = :group_id"
        ),
        {"group_id": group_id},
    ).all()
    return {
        r.id: PlayerRef(player_id=r.id, display_name=r.display_name, is_guest=r.is_guest)
        for r in rows
    }


def _upset_out(upset: stats.Upset | None, names: dict[UUID, PlayerRef]) -> UpsetOut | None:
    if upset is None:
        return None
    return UpsetOut(
        match_id=upset.match_id,
        played_at=upset.played_at,
        winners=[names[p] for p in upset.winners if p in names],
        losers=[names[p] for p in upset.losers if p in names],
        gap=upset.gap,
    )


def _record_out(
    item: tuple[UUID, stats.Record] | None, names: dict[UUID, PlayerRef]
) -> RecordOut | None:
    if item is None or item[0] not in names:
        return None
    return RecordOut(player=names[item[0]], played=item[1].played, won=item[1].won)


@router.get("/stats/me")
def my_stats(group_id: UUID, user: CurrentUserSession, days: int | None = None) -> MyStats:
    """Your stats in the group, over the last `days` (30 or 90) or all time if not given."""
    if days is not None and days not in WINDOWS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="days must be 30 or 90.")
    session = user.session
    _require_member(session, user.user_id, group_id)
    me = session.execute(
        text("SELECT id FROM players WHERE group_id = :group_id AND user_id = :me"),
        {"group_id": group_id, "me": user.user_id},
    ).scalar_one()
    # Crew points need every game, whatever the window.
    matches = group_matches(session, group_id)
    pregame: dict[UUID, tuple[float, float]] = {}
    starts: dict[UUID, float] = {}
    rated = group_ratings(session, group_id, matches, pregame, starts)
    since = datetime.now(UTC) - timedelta(days=days) if days else None
    window = [m for m in matches if since is None or m.played_at > since]

    all_time = stats.personal(matches, me, pregame)
    mine = stats.personal(window, me, pregame) if since else all_time
    names = _players(session, group_id)
    head_to_head = [
        RecordOut(player=names[pid], played=r.played, won=r.won)
        for pid, r in sorted(
            mine.opponents.items(),
            key=lambda item: (-item[1].played, names[item[0]].display_name.lower()),
        )
        if pid in names
    ]
    mine_rated = rated.get(me)
    points = (
        [p for p in stats.timeline(matches, me, mine_rated) if since is None or p.played_at > since]
        if mine_rated
        else []
    )
    start = starts.get(me, START)
    rating_start: float | None = None
    if mine_rated:
        rating_start = round(stats.rating_before(mine_rated, start, since) if since else start, 2)
    streak = all_time.current_streak
    return MyStats(
        days=days,
        matches=mine.matches,
        wins=mine.wins,
        current_streak=Streak(result=streak[0], length=streak[1]) if streak else None,
        longest_win_streak=mine.longest_win_streak,
        close_won=mine.close_won,
        close_lost=mine.close_lost,
        skunks_given=mine.skunks_given,
        skunks_taken=mine.skunks_taken,
        upset_wins=mine.upset_wins,
        biggest_upset=_upset_out(mine.biggest_upset, names),
        best_partner=_record_out(stats.best_partner(all_time.partners), names),
        nemesis=_record_out(stats.nemesis(all_time.opponents), names),
        head_to_head=head_to_head,
        timeline=[
            TimelinePointOut(
                played_at=p.played_at, doubles=p.doubles, won=p.won, rating=round(p.rating, 2)
            )
            for p in points
        ],
        rating_start=rating_start,
        rating_now=round(mine_rated.rating, 2) if mine_rated else None,
    )


@router.get("/highlights")
def highlights(group_id: UUID, user: CurrentUserSession) -> Highlights:
    session = user.session
    _require_member(session, user.user_id, group_id)
    matches = group_matches(session, group_id)
    pregame: dict[UUID, tuple[float, float]] = {}
    rated = group_ratings(session, group_id, matches, pregame)
    # Listed like the Board: guests, and members still in the group.
    listed = set(
        session.execute(
            text(
                """
                SELECT p.id FROM players p
                LEFT JOIN group_members gm ON gm.group_id = p.group_id AND gm.user_id = p.user_id
                WHERE p.group_id = :group_id AND (p.user_id IS NULL OR gm.status = 'active')
                """
            ),
            {"group_id": group_id},
        ).scalars()
    )
    found = stats.highlights(matches, rated, pregame, listed, datetime.now(UTC))
    names = _players(session, group_id)
    return Highlights(
        longest_win_streak=StreakHighlight(player=names[found.streak[0]], length=found.streak[1])
        if found.streak
        else None,
        most_games=GamesHighlight(player=names[found.most_games[0]], matches=found.most_games[1])
        if found.most_games
        else None,
        biggest_upset=_upset_out(found.biggest_upset, names),
        weeks_running=[
            WeeksHighlight(player=names[pid], weeks=weeks) for pid, weeks in found.weeks_running
        ],
        best_partnership=PartnershipHighlight(
            players=[names[found.best_partnership[0]], names[found.best_partnership[1]]],
            played=found.best_partnership[2].played,
            won=found.best_partnership[2].won,
        )
        if found.best_partnership
        else None,
        newcomers=[names[pid] for pid in found.newcomers],
    )
