"""Crew events (migration 0028): Dink Shuffle and Ride the River, round by round.

Leads and co-leads start an event (while its switch is on for the crew), add or remove
players, start each round, skip a court and finish. Anyone in the crew fills in a court's
score, which becomes an ordinary game (games.insert_match), so recaps, stats, crew points and
Your week include it. A lead or co-lead can change a score afterwards.

Rounds come from popshot_api.events. The database enforces the same rules (row-level
security), so these checks give clear messages; they aren't the only line of defence.
"""

import random
import secrets
from collections import defaultdict
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import Row, text
from sqlalchemy.orm import Session

from popshot_api.db import CurrentUserSession
from popshot_api.events import MAX_PLAYERS, MIN_PLAYERS, Court, EventError, Round, river, shuffle
from popshot_api.rating import LEVEL_START, START
from popshot_api.routes.board import group_ratings
from popshot_api.routes.features import feature_on
from popshot_api.routes.games import (
    _PLAYABLE_IDS,
    GameScore,
    LogGame,
    _require_member,
    insert_match,
    rewrite_match,
)

router = APIRouter(prefix="/v1/groups/{group_id}/events")

Kind = Literal["shuffle", "river"]
Vibe = Literal["social", "competitive"]
Seeding = Literal["random", "crew_points", "level"]
Side = Literal["A", "B"]

MAX_LIVE = 3
FINISHED_SHOWN = 20
KIND_LABEL: dict[str, str] = {"shuffle": "Dink Shuffle", "river": "Ride the River"}

EVENT_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, detail="We couldn't find that event.")
COURT_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, detail="We couldn't find that court.")
LEADS_ONLY = HTTPException(
    status.HTTP_403_FORBIDDEN, detail="Only the crew's leads and co-leads can do that."
)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail=detail)


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


class NewEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Kind
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    vibe: Vibe = "social"
    players: Annotated[list[UUID], Field(min_length=MIN_PLAYERS, max_length=MAX_PLAYERS)]
    courts: Annotated[int, Field(ge=1, le=6)]
    points_to: Literal[11, 15, 21] = 11
    win_by_two: bool = True
    best_of: Literal[1, 3, 5] = 1
    night_id: UUID | None = None
    # Ride the River only: how its starting order is made (never shown).
    seeding: Seeding | None = None


class AddPlayer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_id: UUID


class CourtScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    games: Annotated[list[GameScore], Field(min_length=1, max_length=5)]


class EventPlayer(BaseModel):
    player_id: UUID
    display_name: str
    is_guest: bool
    is_me: bool
    # False once they've left the event.
    here: bool


class CourtOut(BaseModel):
    court: int
    team_a: list[UUID]
    team_b: list[UUID]
    match_id: UUID | None
    games: list[GameScore]
    winner: Side | None
    skipped: bool


class RoundOut(BaseModel):
    number: int
    courts: list[CourtOut]
    sitting_out: list[UUID]


class Standing(BaseModel):
    player_id: UUID
    games: int
    wins: int
    points_for: int
    points_against: int


class MyResults(BaseModel):
    games: int
    wins: int


class EventSummary(BaseModel):
    id: UUID
    kind: Kind
    name: str
    vibe: Vibe
    status: Literal["live", "finished"]
    created_at: datetime
    rounds: int
    players: int


class EventOut(EventSummary):
    points_to: int
    win_by_two: bool
    best_of: int
    courts: int
    night_id: UUID | None
    people: list[EventPlayer]
    round_list: list[RoundOut]
    can_manage: bool
    # A lead can start the next round now: every court of the last one is scored or skipped.
    can_start_round: bool
    # Competitive only: everyone's results in this event. Never sent for a social one.
    standings: list[Standing] | None
    # Your own results in this event, if you're playing in it.
    mine: MyResults | None


# --- Shared helpers ---------------------------------------------------------------------


def _is_admin(session: Session, me: UUID, group_id: UUID) -> bool:
    role = session.execute(
        text(
            "SELECT role FROM group_members WHERE group_id = :g AND user_id = :me "
            "AND status = 'active'"
        ),
        {"g": group_id, "me": me},
    ).scalar_one_or_none()
    return role in ("lead", "co_lead")


def _require_admin(session: Session, me: UUID, group_id: UUID) -> None:
    _require_member(session, me, group_id)
    if not _is_admin(session, me, group_id):
        raise LEADS_ONLY


def _event(session: Session, group_id: UUID, event_id: UUID, *, lock: bool = False) -> Row[Any]:
    sql = "SELECT * FROM events WHERE id = :e AND group_id = :g"
    row = session.execute(
        text(sql + " FOR UPDATE" if lock else sql), {"e": event_id, "g": group_id}
    ).one_or_none()
    if row is None:
        raise EVENT_NOT_FOUND
    return row


def _require_live(event: Row[Any]) -> None:
    if event.status != "live":
        raise _conflict("This event has finished.")


def _here(session: Session, event_id: UUID) -> list[UUID]:
    """Players in the event now; for Ride the River, in its starting order."""
    return list(
        session.execute(
            text(
                "SELECT player_id FROM event_players WHERE event_id = :e AND left_at IS NULL "
                "ORDER BY start_rank NULLS LAST, joined_at, player_id"
            ),
            {"e": event_id},
        ).scalars()
    )


def _courts(session: Session, event_id: UUID) -> list[Row[Any]]:
    return list(
        session.execute(
            text(
                "SELECT round, court, team_a, team_b, match_id, skipped FROM event_courts "
                "WHERE event_id = :e ORDER BY round, court"
            ),
            {"e": event_id},
        ).all()
    )


def _rounds(session: Session, event_id: UUID) -> list[Row[Any]]:
    return list(
        session.execute(
            text(
                "SELECT number, sitting_out FROM event_rounds WHERE event_id = :e ORDER BY number"
            ),
            {"e": event_id},
        ).all()
    )


def _history(rounds: list[Row[Any]], courts: list[Row[Any]]) -> list[Round]:
    by_round: dict[int, list[Court]] = defaultdict(list)
    for c in courts:
        by_round[c.round].append(Court((c.team_a[0], c.team_a[1]), (c.team_b[0], c.team_b[1])))
    return [
        Round(courts=tuple(by_round[r.number]), sitting_out=tuple(r.sitting_out)) for r in rounds
    ]


def _scores(session: Session, match_ids: list[UUID]) -> dict[UUID, list[GameScore]]:
    if not match_ids:
        return {}
    rows = session.execute(
        text(
            "SELECT match_id, team_a_score, team_b_score FROM match_games "
            "WHERE match_id = ANY(:ids) ORDER BY match_id, game_number"
        ),
        {"ids": match_ids},
    ).all()
    found: dict[UUID, list[GameScore]] = defaultdict(list)
    for r in rows:
        found[r.match_id].append(GameScore(team_a=r.team_a_score, team_b=r.team_b_score))
    return found


def _winner(games: list[GameScore]) -> Side | None:
    if not games:
        return None
    wins_a = sum(1 for g in games if g.team_a > g.team_b)
    return "A" if wins_a * 2 > len(games) else "B"


def _make_round(session: Session, event: Row[Any], number: int) -> None:
    """Make round `number` from who's here now and the rounds so far, and save it."""
    here = _here(session, event.id)
    rounds, courts = _rounds(session, event.id), _courts(session, event.id)
    history = _history(rounds, courts)
    try:
        if event.kind == "shuffle":
            made = shuffle.next_round(here, event.courts, history, event.seed)
        else:
            last = [c for c in courts if c.round == number - 1]
            scores = _scores(session, [c.match_id for c in last if c.match_id])
            winners: dict[int, river.Winner] = {}
            for c in last:
                won = _winner(scores.get(c.match_id, [])) if c.match_id else None
                if won is not None:
                    winners[c.court - 1] = won
            made = river.next_round(
                here, event.courts, history, winners=winners, start=here, seed=event.seed
            )
    except EventError as error:
        raise _conflict(str(error)) from error
    session.execute(
        text(
            "INSERT INTO event_rounds (event_id, group_id, number, sitting_out) "
            "VALUES (:e, :g, :n, :out)"
        ),
        {"e": event.id, "g": event.group_id, "n": number, "out": list(made.sitting_out)},
    )
    session.execute(
        text(
            "INSERT INTO event_courts (event_id, group_id, round, court, team_a, team_b) "
            "VALUES (:e, :g, :n, :c, :a, :b)"
        ),
        [
            {
                "e": event.id,
                "g": event.group_id,
                "n": number,
                "c": i,
                "a": list(court.team_a),
                "b": list(court.team_b),
            }
            for i, court in enumerate(made.courts, start=1)
        ],
    )


def _check_players(session: Session, group_id: UUID, ids: list[UUID]) -> None:
    if len(set(ids)) != len(ids):
        raise _unprocessable("Each player can only be in an event once.")
    found = session.execute(text(_PLAYABLE_IDS), {"group_id": group_id, "ids": ids}).scalars()
    if set(found) != set(ids):
        raise _unprocessable("Some of those players aren't in this group.")


def _starting_order(
    session: Session, group_id: UUID, players: list[UUID], seeding: Seeding, seed: int
) -> list[UUID]:
    """Ride the River's starting order, strongest first by the chosen measure; ties at
    random. Guests and anyone without a number start in the middle."""
    # Not for secrets: seeded, so the order can be made again the same way.
    rng = random.Random(seed)  # noqa: S311
    ordered = sorted(players, key=str)
    rng.shuffle(ordered)
    if seeding == "random":
        return ordered
    if seeding == "crew_points":
        rated = group_ratings(session, group_id)
        value = {p: rated[p].rating if p in rated else START for p in players}
    else:
        levels = session.execute(text("SELECT * FROM app_group_levels(:g)"), {"g": group_id}).all()
        known = {
            r.player_id: LEVEL_START[r.self_level] for r in levels if r.self_level in LEVEL_START
        }
        middle = sorted(LEVEL_START.values())[len(LEVEL_START) // 2]
        value = {p: known.get(p, middle) for p in players}
    return sorted(ordered, key=lambda p: -value[p])


# --- Routes -----------------------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED)
def create_event(group_id: UUID, body: NewEvent, user: CurrentUserSession) -> EventOut:
    session, me = user.session, user.user_id
    _require_admin(session, me, group_id)
    if not feature_on(session, f"events.{body.kind}", group_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=f"{KIND_LABEL[body.kind]} isn't switched on for this crew yet.",
        )
    if (body.kind == "river") != (body.seeding is not None):
        raise _unprocessable(
            "Pick how Ride the River starts."
            if body.kind == "river"
            else "Only Ride the River uses a starting order."
        )
    _check_players(session, group_id, body.players)
    if body.night_id is not None:
        night = session.execute(
            text(
                "SELECT 1 FROM play_nights WHERE id = :n AND group_id = :g AND cancelled_at IS NULL"
            ),
            {"n": body.night_id, "g": group_id},
        ).scalar_one_or_none()
        if night is None:
            raise _unprocessable("That meetup isn't in this group.")
    live = session.execute(
        text("SELECT count(*) FROM events WHERE group_id = :g AND status = 'live'"),
        {"g": group_id},
    ).scalar_one()
    if live >= MAX_LIVE:
        raise _conflict(f"A crew can run {MAX_LIVE} events at once. Finish one first.")

    seed = secrets.randbelow(2**31)
    order = (
        _starting_order(session, group_id, body.players, body.seeding, seed)
        if body.seeding is not None
        else body.players
    )
    event_id: UUID = session.execute(
        text(
            """
            INSERT INTO events (group_id, kind, name, vibe, points_to, win_by_two, best_of,
                                courts, night_id, seeding, seed, created_by)
            VALUES (:g, :kind, :name, :vibe, :points_to, :win_by_two, :best_of, :courts,
                    :night, :seeding, :seed, :me)
            RETURNING id
            """
        ),
        {
            "g": group_id,
            "kind": body.kind,
            "name": body.name,
            "vibe": body.vibe,
            "points_to": body.points_to,
            "win_by_two": body.win_by_two,
            "best_of": body.best_of,
            "courts": body.courts,
            "night": body.night_id,
            "seeding": body.seeding,
            "seed": seed,
            "me": me,
        },
    ).scalar_one()
    session.execute(
        text(
            "INSERT INTO event_players (event_id, group_id, player_id, start_rank) "
            "VALUES (:e, :g, :p, :rank)"
        ),
        [
            {
                "e": event_id,
                "g": group_id,
                "p": p,
                "rank": i if body.kind == "river" else None,
            }
            for i, p in enumerate(order, start=1)
        ],
    )
    _make_round(session, _event(session, group_id, event_id), 1)
    return _event_out(session, me, group_id, event_id)


@router.get("")
def list_events(group_id: UUID, user: CurrentUserSession) -> list[EventSummary]:
    _require_member(user.session, user.user_id, group_id)
    rows = user.session.execute(
        text(
            """
            (SELECT e.*, 0 AS bucket FROM events e WHERE e.group_id = :g AND e.status = 'live')
            UNION ALL
            (SELECT e.*, 1 AS bucket FROM events e WHERE e.group_id = :g
                AND e.status = 'finished' ORDER BY e.finished_at DESC LIMIT :shown)
            ORDER BY bucket, created_at DESC
            """
        ),
        {"g": group_id, "shown": FINISHED_SHOWN},
    ).all()
    counts = _counts(user.session, [r.id for r in rows])
    return [
        EventSummary(
            id=r.id,
            kind=r.kind,
            name=r.name,
            vibe=r.vibe,
            status=r.status,
            created_at=r.created_at,
            rounds=counts[r.id][0],
            players=counts[r.id][1],
        )
        for r in rows
    ]


def _counts(session: Session, ids: list[UUID]) -> dict[UUID, tuple[int, int]]:
    """(rounds, players here now) for each event."""
    rows = session.execute(
        text(
            """
            SELECT e.id,
                   (SELECT count(*) FROM event_rounds r WHERE r.event_id = e.id) AS rounds,
                   (SELECT count(*) FROM event_players p
                    WHERE p.event_id = e.id AND p.left_at IS NULL) AS players
            FROM events e WHERE e.id = ANY(:ids)
            """
        ),
        {"ids": ids},
    ).all()
    return {r.id: (r.rounds, r.players) for r in rows}


@router.get("/{event_id}")
def get_event(group_id: UUID, event_id: UUID, user: CurrentUserSession) -> EventOut:
    _require_member(user.session, user.user_id, group_id)
    return _event_out(user.session, user.user_id, group_id, event_id)


def _event_out(session: Session, me: UUID, group_id: UUID, event_id: UUID) -> EventOut:
    e = _event(session, group_id, event_id)
    people = session.execute(
        text(
            """
            SELECT ep.player_id, p.display_name, p.user_id IS NULL AS is_guest,
                   p.user_id IS NOT DISTINCT FROM :me AS is_me, ep.left_at IS NULL AS here
            FROM event_players ep JOIN players p ON p.id = ep.player_id
            WHERE ep.event_id = :e
            ORDER BY lower(p.display_name), p.id
            """
        ),
        {"e": event_id, "me": me},
    ).all()
    rounds, courts = _rounds(session, event_id), _courts(session, event_id)
    scores = _scores(session, [c.match_id for c in courts if c.match_id])
    by_round: dict[int, list[CourtOut]] = defaultdict(list)
    for c in courts:
        games = scores.get(c.match_id, []) if c.match_id else []
        by_round[c.round].append(
            CourtOut(
                court=c.court,
                team_a=list(c.team_a),
                team_b=list(c.team_b),
                match_id=c.match_id,
                games=games,
                winner=_winner(games),
                skipped=c.skipped,
            )
        )
    round_list = [
        RoundOut(number=r.number, courts=by_round[r.number], sitting_out=list(r.sitting_out))
        for r in rounds
    ]
    manage = _is_admin(session, me, group_id)
    last_done = bool(round_list) and all(
        c.match_id is not None or c.skipped for c in round_list[-1].courts
    )
    table = _standings(round_list)
    my_player = next((p.player_id for p in people if p.is_me), None)
    mine = None
    if my_player is not None:
        row = next((s for s in table if s.player_id == my_player), None)
        mine = MyResults(games=row.games if row else 0, wins=row.wins if row else 0)
    return EventOut(
        id=e.id,
        kind=e.kind,
        name=e.name,
        vibe=e.vibe,
        status=e.status,
        created_at=e.created_at,
        rounds=len(round_list),
        players=sum(1 for p in people if p.here),
        points_to=e.points_to,
        win_by_two=e.win_by_two,
        best_of=e.best_of,
        courts=e.courts,
        night_id=e.night_id,
        people=[
            EventPlayer(
                player_id=p.player_id,
                display_name=p.display_name,
                is_guest=p.is_guest,
                is_me=p.is_me,
                here=p.here,
            )
            for p in people
        ],
        round_list=round_list,
        can_manage=manage,
        can_start_round=manage and e.status == "live" and last_done,
        standings=table if e.vibe == "competitive" else None,
        mine=mine,
    )


def _standings(rounds: list[RoundOut]) -> list[Standing]:
    """Results within the event: games, wins, points for and against. Most wins first, then
    point difference; ties keep a stable order."""
    rows: dict[UUID, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    for r in rounds:
        for c in r.courts:
            if c.winner is None:
                continue
            a = sum(g.team_a for g in c.games)
            b = sum(g.team_b for g in c.games)
            for team, won, scored, conceded in (
                (c.team_a, c.winner == "A", a, b),
                (c.team_b, c.winner == "B", b, a),
            ):
                for p in team:
                    rows[p][0] += 1
                    rows[p][1] += int(won)
                    rows[p][2] += scored
                    rows[p][3] += conceded
    table = [
        Standing(player_id=p, games=v[0], wins=v[1], points_for=v[2], points_against=v[3])
        for p, v in rows.items()
    ]
    table.sort(key=lambda s: (-s.wins, -(s.points_for - s.points_against), str(s.player_id)))
    return table


@router.post("/{event_id}/players", status_code=status.HTTP_204_NO_CONTENT)
def add_player(
    group_id: UUID, event_id: UUID, body: AddPlayer, user: CurrentUserSession
) -> Response:
    """Someone arrives: they're in from the next round. Someone who'd left comes back."""
    session = user.session
    _require_admin(session, user.user_id, group_id)
    e = _event(session, group_id, event_id, lock=True)
    _require_live(e)
    _check_players(session, group_id, [body.player_id])
    here = _here(session, event_id)
    if body.player_id in here:
        raise _conflict("They're already playing in this event.")
    if len(here) >= MAX_PLAYERS:
        raise _conflict(f"An event can have up to {MAX_PLAYERS} players.")
    session.execute(
        text(
            """
            INSERT INTO event_players (event_id, group_id, player_id, start_rank)
            VALUES (:e, :g, :p, NULL)
            ON CONFLICT (event_id, player_id) DO UPDATE SET left_at = NULL
            """
        ),
        {"e": event_id, "g": group_id, "p": body.player_id},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{event_id}/players/{player_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
def remove_player(
    group_id: UUID, event_id: UUID, player_id: UUID, user: CurrentUserSession
) -> Response:
    """Someone leaves: they're out from the next round. Their games stay."""
    session = user.session
    _require_admin(session, user.user_id, group_id)
    e = _event(session, group_id, event_id, lock=True)
    _require_live(e)
    left = session.execute(
        text(
            "UPDATE event_players SET left_at = now() "
            "WHERE event_id = :e AND player_id = :p AND left_at IS NULL RETURNING 1"
        ),
        {"e": event_id, "p": player_id},
    ).scalar_one_or_none()
    if left is None:
        raise _conflict("They aren't playing in this event.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{event_id}/rounds/{number}/courts/{court}")
def score_court(  # noqa: PLR0913 - each input is needed
    group_id: UUID,
    event_id: UUID,
    number: int,
    court: int,
    *,
    body: CourtScore,
    user: CurrentUserSession,
) -> EventOut:
    """Fill in a court's score (anyone in the crew), or change it (leads and co-leads)."""
    session, me = user.session, user.user_id
    _require_member(session, me, group_id)
    e = _event(session, group_id, event_id)
    admin = _is_admin(session, me, group_id)
    found = session.execute(
        text(
            "SELECT team_a, team_b, match_id, skipped FROM event_courts "
            "WHERE event_id = :e AND round = :n AND court = :c"
        ),
        {"e": event_id, "n": number, "c": court},
    ).one_or_none()
    if found is None:
        raise COURT_NOT_FOUND
    if found.match_id is not None and not admin:
        raise _conflict("This court already has a score. Ask a lead to change it.")
    if found.match_id is None:
        _require_live(e)
        if found.skipped and not admin:
            raise _conflict("This court was skipped.")
    # Two phones scoring at once: app_score_court locks the court, and the second gets a
    # conflict, which rolls its game back.
    game = LogGame(
        format="doubles",
        points_to=e.points_to,
        win_by_two=e.win_by_two,
        best_of=e.best_of,
        team_a=list(found.team_a),
        team_b=list(found.team_b),
        games=body.games,
    )
    if found.match_id is None:
        match_id = insert_match(session, me, group_id, game, event_id=event_id)
        outcome = session.execute(
            text("SELECT app_score_court(:e, CAST(:n AS smallint), CAST(:c AS smallint), :m)"),
            {"e": event_id, "n": number, "c": court, "m": match_id},
        ).scalar_one()
        if outcome != "done":
            # Someone else filled it in first (or it was skipped meanwhile): undo ours.
            raise _conflict("Someone just entered this score. Have a look.")
    else:
        kept = session.execute(
            text("SELECT played_at FROM matches WHERE id = :m FOR UPDATE"),
            {"m": found.match_id},
        ).scalar_one()
        rewrite_match(session, me, group_id, found.match_id, game, kept=kept)
    return _event_out(session, me, group_id, event_id)


@router.post("/{event_id}/rounds/{number}/courts/{court}/skip")
def skip_court(
    group_id: UUID, event_id: UUID, number: int, court: int, user: CurrentUserSession
) -> EventOut:
    """A court that couldn't finish: no game, and the next round can start without it."""
    session, me = user.session, user.user_id
    _require_admin(session, me, group_id)
    _require_live(_event(session, group_id, event_id))
    skipped = session.execute(
        text(
            "UPDATE event_courts SET skipped = true "
            "WHERE event_id = :e AND round = :n AND court = :c AND match_id IS NULL RETURNING 1"
        ),
        {"e": event_id, "n": number, "c": court},
    ).scalar_one_or_none()
    if skipped is None:
        raise _conflict("Only a court with no score can be skipped.")
    return _event_out(session, me, group_id, event_id)


@router.post("/{event_id}/rounds", status_code=status.HTTP_201_CREATED)
def next_round(group_id: UUID, event_id: UUID, user: CurrentUserSession) -> EventOut:
    """Start the next round, once every court of this one is scored or skipped."""
    session, me = user.session, user.user_id
    _require_admin(session, me, group_id)
    # Locked, so two taps at once make one round.
    e = _event(session, group_id, event_id, lock=True)
    _require_live(e)
    last = session.execute(
        text("SELECT max(number) FROM event_rounds WHERE event_id = :e"), {"e": event_id}
    ).scalar_one()
    waiting = session.execute(
        text(
            "SELECT count(*) FROM event_courts WHERE event_id = :e AND round = :n "
            "AND match_id IS NULL AND NOT skipped"
        ),
        {"e": event_id, "n": last},
    ).scalar_one()
    if waiting:
        raise _conflict("Score or skip every court before starting the next round.")
    _make_round(session, e, last + 1)
    return _event_out(session, me, group_id, event_id)


@router.post("/{event_id}/finish")
def finish_event(group_id: UUID, event_id: UUID, user: CurrentUserSession) -> EventOut:
    session, me = user.session, user.user_id
    _require_admin(session, me, group_id)
    e = _event(session, group_id, event_id, lock=True)
    _require_live(e)
    session.execute(
        text("UPDATE events SET status = 'finished', finished_at = :now WHERE id = :e"),
        {"e": event_id, "now": datetime.now(UTC)},
    )
    return _event_out(session, me, group_id, event_id)
