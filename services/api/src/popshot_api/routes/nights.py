"""Play nights: plan one (or a weekly run), answer In / Maybe / Out, see who's coming.

With a spot limit, the first people to say "in" are going and the rest wait in order (see
migration 0007). Changes that move someone off the waitlist, a new night and a cancelled
night send push notifications. Messages carry the venue but no time: the server doesn't
know each reader's time zone, so the app shows the time.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import Row, text
from sqlalchemy.orm import Session

from popshot_api.db import CurrentUserSession
from popshot_api.push import Message
from popshot_api.routes.games import _require_member
from popshot_api.routes.groups import _no_control_characters
from popshot_api.routes.notifications import CurrentNotifier, Notifier

router = APIRouter(prefix="/v1")

Answer = Literal["in", "maybe", "out"]

MAX_WEEKS = 12
# Upcoming nights a group can have at once: plenty, and stops a script filling the table.
MAX_UPCOMING = 40
# Planning far ahead is fine; a typo'd year isn't.
MAX_AHEAD = timedelta(days=366)
# Answers stay open a little past the start, for whoever is running late.
ANSWERS_CLOSE_AFTER = timedelta(hours=2)
# Lists show nights until a few hours after they start.
SHOWN_AFTER_START = timedelta(hours=4)

NIGHT_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, detail="We couldn't find that meetup.")

Venue = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
    AfterValidator(_no_control_characters),
]
Note = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=200),
    AfterValidator(_no_control_characters),
]
Spots = Annotated[int, Field(ge=2, le=64)]


class NewNight(BaseModel):
    model_config = ConfigDict(extra="forbid")

    starts_at: AwareDatetime
    venue: Venue
    note: Note | None = None
    # No limit when left out.
    spots: Spots | None = None
    # 1 for a single night; up to MAX_WEEKS for the same time each week.
    weeks: Annotated[int, Field(ge=1, le=MAX_WEEKS)] = 1


class NightChange(BaseModel):
    """The whole editable night; this one only, not the rest of its series."""

    model_config = ConfigDict(extra="forbid")

    starts_at: AwareDatetime
    venue: Venue
    note: Note | None = None
    spots: Spots | None = None


class RsvpBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: Answer


class Person(BaseModel):
    user_id: UUID
    display_name: str
    avatar_url: str | None


class Night(BaseModel):
    id: UUID
    group_id: UUID
    group_name: str
    series_id: UUID | None
    starts_at: datetime
    venue: str
    note: str | None
    spots: int | None
    created_by_name: str
    cancelled: bool
    # Whether answers are still open.
    open: bool
    can_edit: bool
    going: list[Person]
    waitlist: list[Person]
    maybe: list[Person]
    out: list[Person]
    my_answer: Answer | None
    # 1-based, when you're on the waitlist.
    my_waitlist_position: int | None


@dataclass(frozen=True, slots=True)
class _Rsvp:
    user_id: UUID
    answer: Answer
    in_since: datetime | None


def split_in(rsvps: list[_Rsvp], spots: int | None) -> tuple[list[UUID], list[UUID]]:
    """(going, waitlist) among the people who said "in", in the order they said it."""
    queue = [
        r.user_id
        for r in sorted(
            (r for r in rsvps if r.answer == "in"),
            key=lambda r: (r.in_since, str(r.user_id)),
        )
    ]
    if spots is None:
        return queue, []
    return queue[:spots], queue[spots:]


def _is_admin(session: Session, me: UUID, group_id: UUID) -> bool:
    role = session.execute(
        text(
            "SELECT role FROM group_members WHERE group_id = :g AND user_id = :me "
            "AND status = 'active'"
        ),
        {"g": group_id, "me": me},
    ).scalar_one_or_none()
    return role in ("lead", "co_lead")


def _rsvps(session: Session, night_id: UUID) -> list[_Rsvp]:
    """Answers from people still in the group."""
    rows = session.execute(
        text(
            """
            SELECT r.user_id, r.answer, r.in_since FROM play_night_rsvps r
            JOIN group_members m ON m.group_id = r.group_id AND m.user_id = r.user_id
            WHERE r.night_id = :night AND m.status = 'active'
            """
        ),
        {"night": night_id},
    ).all()
    return [_Rsvp(r.user_id, r.answer, r.in_since) for r in rows]


_NIGHT_SQL = """
    SELECT n.id, n.group_id, g.name AS group_name, n.series_id, n.starts_at, n.venue, n.note,
           n.spots, n.created_by, u.display_name AS created_by_name, n.cancelled_at
    FROM play_nights n
    JOIN groups g ON g.id = n.group_id
    JOIN users u ON u.id = n.created_by
"""


def _load(session: Session, me: UUID, rows: Sequence[Row[Any]], now: datetime) -> list[Night]:
    if not rows:
        return []
    night_ids = [r.id for r in rows]
    people = {
        p.id: Person(user_id=p.id, display_name=p.display_name, avatar_url=p.avatar_url)
        for p in session.execute(
            text(
                """
                SELECT DISTINCT u.id, u.display_name, u.avatar_url FROM play_night_rsvps r
                JOIN users u ON u.id = r.user_id WHERE r.night_id = ANY(:ids)
                """
            ),
            {"ids": night_ids},
        )
    }
    admin_of: dict[UUID, bool] = {}
    nights: list[Night] = []
    for r in rows:
        rsvps = _rsvps(session, r.id)
        going, waitlist = split_in(rsvps, r.spots)
        by_answer = {a: [x.user_id for x in rsvps if x.answer == a] for a in ("maybe", "out")}
        mine = next((x.answer for x in rsvps if x.user_id == me), None)
        if r.group_id not in admin_of:
            admin_of[r.group_id] = _is_admin(session, me, r.group_id)

        nights.append(
            Night(
                id=r.id,
                group_id=r.group_id,
                group_name=r.group_name,
                series_id=r.series_id,
                starts_at=r.starts_at,
                venue=r.venue,
                note=r.note,
                spots=r.spots,
                created_by_name=r.created_by_name,
                cancelled=r.cancelled_at is not None,
                open=r.cancelled_at is None and now < r.starts_at + ANSWERS_CLOSE_AFTER,
                can_edit=r.created_by == me or admin_of[r.group_id],
                going=_named(people, going),
                waitlist=_named(people, waitlist),
                maybe=sorted(
                    _named(people, by_answer["maybe"]), key=lambda p: p.display_name.lower()
                ),
                out=sorted(_named(people, by_answer["out"]), key=lambda p: p.display_name.lower()),
                my_answer=mine,
                my_waitlist_position=waitlist.index(me) + 1 if me in waitlist else None,
            )
        )
    return nights


def _named(people: dict[UUID, Person], ids: list[UUID]) -> list[Person]:
    return [people[i] for i in ids if i in people]


def _one(session: Session, me: UUID, group_id: UUID, night_id: UUID) -> Night:
    rows = session.execute(
        text(_NIGHT_SQL + " WHERE n.id = :night AND n.group_id = :group"),
        {"night": night_id, "group": group_id},
    ).all()
    nights = _load(session, me, rows, datetime.now(UTC))
    if not nights:
        raise NIGHT_NOT_FOUND
    return nights[0]


def _members_except(session: Session, group_id: UUID, me: UUID) -> list[UUID]:
    return list(
        session.execute(
            text(
                "SELECT user_id FROM group_members WHERE group_id = :g AND status = 'active' "
                "AND user_id <> :me"
            ),
            {"g": group_id, "me": me},
        ).scalars()
    )


def _tell_promoted(session: Session, notifier: Notifier, before: list[UUID], night: Night) -> None:
    """Whoever is going now but wasn't before got a spot from the waitlist."""
    moved_up = [p.user_id for p in night.going if p.user_id not in before]
    notifier.notify(
        session,
        moved_up,
        "play_nights",
        Message(
            title="You're in: a spot opened up",
            body=f"You're off the waitlist for {night.venue}.",
            url=f"/groups/{night.group_id}/nights/{night.id}",
            tag=f"night-{night.id}",
        ),
    )


def _check_time(starts_at: datetime, now: datetime) -> None:
    if starts_at < now - timedelta(hours=1):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Pick a time that hasn't passed."
        )
    if starts_at > now + MAX_AHEAD:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Pick a date within the next year."
        )


@router.post("/groups/{group_id}/nights", status_code=status.HTTP_201_CREATED)
def plan_night(
    group_id: UUID, body: NewNight, user: CurrentUserSession, notifier: CurrentNotifier
) -> list[Night]:
    """Plan a night, or the same night for `weeks` weeks. Any member can."""
    session, me = user.session, user.user_id
    _require_member(session, me, group_id)
    now = datetime.now(UTC)
    _check_time(body.starts_at, now)
    upcoming = session.execute(
        text(
            "SELECT count(*) FROM play_nights WHERE group_id = :g AND cancelled_at IS NULL "
            "AND starts_at > now()"
        ),
        {"g": group_id},
    ).scalar_one()
    if upcoming + body.weeks > MAX_UPCOMING:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"A group can have up to {MAX_UPCOMING} upcoming meetups.",
        )
    series = (
        session.execute(text("SELECT gen_random_uuid()")).scalar_one() if body.weeks > 1 else None
    )
    ids = [
        session.execute(
            text(
                """
                INSERT INTO play_nights (group_id, series_id, starts_at, venue, note, spots,
                                         created_by)
                VALUES (:g, :series, :starts_at, :venue, :note, :spots, :me)
                RETURNING id
                """
            ),
            {
                "g": group_id,
                "series": series,
                # Same local time each week: add whole weeks to the instant the browser sent.
                "starts_at": body.starts_at + timedelta(weeks=week),
                "venue": body.venue,
                "note": body.note or None,
                "spots": body.spots,
                "me": me,
            },
        ).scalar_one()
        for week in range(body.weeks)
    ]
    # The person planning it is going.
    for night_id in ids:
        session.execute(
            text(
                "INSERT INTO play_night_rsvps (night_id, group_id, user_id, answer, in_since) "
                "VALUES (:n, :g, :me, 'in', now())"
            ),
            {"n": night_id, "g": group_id, "me": me},
        )
    rows = session.execute(
        text(_NIGHT_SQL + " WHERE n.id = ANY(:ids) ORDER BY n.starts_at"), {"ids": ids}
    ).all()
    nights = _load(session, me, rows, now)
    first = nights[0]
    planner = first.going[0].display_name if first.going else "Someone"
    notifier.notify(
        session,
        _members_except(session, group_id, me),
        "play_nights",
        Message(
            title=f"{planner} planned a meetup"
            + (f" (weekly, {body.weeks} weeks)" if body.weeks > 1 else ""),
            body=f"At {first.venue}. Tap to say if you're in.",
            url=f"/groups/{group_id}/nights/{first.id}",
            tag=f"night-{first.id}",
        ),
    )
    return nights


@router.get("/groups/{group_id}/nights")
def group_nights(group_id: UUID, user: CurrentUserSession) -> list[Night]:
    """Upcoming nights (and ones that started in the last few hours), soonest first."""
    session, me = user.session, user.user_id
    _require_member(session, me, group_id)
    now = datetime.now(UTC)
    rows = session.execute(
        text(_NIGHT_SQL + " WHERE n.group_id = :g AND n.starts_at > :since ORDER BY n.starts_at"),
        {"g": group_id, "since": now - SHOWN_AFTER_START},
    ).all()
    return _load(session, me, rows, now)


@router.get("/me/nights")
def my_next_nights(user: CurrentUserSession) -> list[Night]:
    """The next few nights across your groups, for Home. Cancelled ones aren't shown."""
    session, me = user.session, user.user_id
    now = datetime.now(UTC)
    rows = session.execute(
        text(
            _NIGHT_SQL
            + """
            JOIN group_members m ON m.group_id = n.group_id AND m.user_id = :me
                 AND m.status = 'active'
            WHERE n.cancelled_at IS NULL AND n.starts_at > :since
            ORDER BY n.starts_at LIMIT 3
            """
        ),
        {"me": me, "since": now - SHOWN_AFTER_START},
    ).all()
    return _load(session, me, rows, now)


@router.get("/groups/{group_id}/nights/{night_id}")
def get_night(group_id: UUID, night_id: UUID, user: CurrentUserSession) -> Night:
    _require_member(user.session, user.user_id, group_id)
    return _one(user.session, user.user_id, group_id, night_id)


@router.put("/groups/{group_id}/nights/{night_id}/rsvp")
def answer(
    group_id: UUID,
    night_id: UUID,
    body: RsvpBody,
    user: CurrentUserSession,
    notifier: CurrentNotifier,
) -> Night:
    session, me = user.session, user.user_id
    _require_member(session, me, group_id)
    night = _one(session, me, group_id, night_id)
    if not night.open:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="This meetup was cancelled."
            if night.cancelled
            else "Answers for this meetup have closed.",
        )
    before = [p.user_id for p in night.going]
    # Saying "in" again keeps your place; switching to "in" puts you at the back.
    session.execute(
        text(
            """
            INSERT INTO play_night_rsvps (night_id, group_id, user_id, answer, in_since)
            VALUES (:n, :g, :me, CAST(:answer AS rsvp_answer),
                    CASE WHEN :answer = 'in' THEN now() END)
            ON CONFLICT (night_id, user_id) DO UPDATE SET
                answer = excluded.answer,
                in_since = CASE
                    WHEN excluded.answer <> 'in' THEN NULL
                    WHEN play_night_rsvps.answer = 'in' THEN play_night_rsvps.in_since
                    ELSE now()
                END,
                updated_at = now()
            """
        ),
        {"n": night_id, "g": group_id, "me": me, "answer": body.answer},
    )
    after = _one(session, me, group_id, night_id)
    _tell_promoted(session, notifier, [*before, me], after)
    return after


def _editable(session: Session, me: UUID, group_id: UUID, night_id: UUID) -> Night:
    _require_member(session, me, group_id)
    night = _one(session, me, group_id, night_id)
    if not night.can_edit:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Only whoever planned it, the lead or a co-lead can change this meetup.",
        )
    if night.cancelled:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This meetup was cancelled.")
    return night


@router.patch("/groups/{group_id}/nights/{night_id}")
def change_night(
    group_id: UUID,
    night_id: UUID,
    body: NightChange,
    user: CurrentUserSession,
    notifier: CurrentNotifier,
) -> Night:
    session, me = user.session, user.user_id
    night = _editable(session, me, group_id, night_id)
    _check_time(body.starts_at, datetime.now(UTC))
    session.execute(
        text(
            """
            UPDATE play_nights SET starts_at = :starts_at, venue = :venue, note = :note,
                   spots = :spots, updated_at = now(),
                   -- A new time means new reminders.
                   reminded_day_at = CASE WHEN starts_at = :starts_at THEN reminded_day_at END,
                   reminded_soon_at = CASE WHEN starts_at = :starts_at THEN reminded_soon_at END
            WHERE id = :n AND group_id = :g
            """
        ),
        {
            "n": night_id,
            "g": group_id,
            "starts_at": body.starts_at,
            "venue": body.venue,
            "note": body.note or None,
            "spots": body.spots,
        },
    )
    after = _one(session, me, group_id, night_id)
    # More spots can move people up.
    _tell_promoted(session, notifier, [p.user_id for p in night.going], after)
    return after


@router.post("/groups/{group_id}/nights/{night_id}/cancel")
def cancel_night(
    group_id: UUID, night_id: UUID, user: CurrentUserSession, notifier: CurrentNotifier
) -> Night:
    session, me = user.session, user.user_id
    night = _editable(session, me, group_id, night_id)
    session.execute(
        text(
            "UPDATE play_nights SET cancelled_at = now(), updated_at = now() "
            "WHERE id = :n AND group_id = :g"
        ),
        {"n": night_id, "g": group_id},
    )
    coming = [p.user_id for p in [*night.going, *night.waitlist, *night.maybe]]
    notifier.notify(
        session,
        coming,
        "play_nights",
        Message(
            title="Meetup cancelled",
            body=f"The meetup at {night.venue} is off.",
            url=f"/groups/{group_id}/nights/{night_id}",
            tag=f"night-{night_id}",
        ),
    )
    return _one(session, me, group_id, night_id)
