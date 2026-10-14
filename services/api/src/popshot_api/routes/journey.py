"""Your journey: your story in your own words, learning notes, and journey settings.

Everything here is yours alone: the API reads only your rows and row-level security limits
all three tables to their owner (migration 0032). Behind the 'you.journey' switch, which is
asked about per person (app_feature_on_for_me); while it's off these routes don't exist (404).

Each save of your story adds a new version; old versions are kept, never changed, so a
check-in can say what changed. Skill tags come from you, or from your focus lists when you
don't pick any. (A later step adds the AI reading your words, if you allow it.)
"""

from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import text
from sqlalchemy.orm import Session

from popshot_api.db import CurrentUserSession
from popshot_api.focus import OFFERED_IDS
from popshot_api.journey_checkin import EVERY as CHECKIN_EVERY

router = APIRouter(prefix="/v1/me/journey")

FEATURE = "you.journey"
MAX_TAGS = 4
# How many versions of your story the app shows; all are kept, and all are in your export.
HISTORY = 20
NOTES_SHOWN = 30
# Per rolling 24 hours, so a stuck button or a script can't fill the tables.
STORY_SAVES_PER_DAY = 20
NOTES_PER_DAY = 10

NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found.")


def _plain(value: str) -> str:
    """Trimmed, with no control characters except line breaks and tabs."""
    if any(ord(c) < 32 and c not in "\n\t" for c in value) or "\x7f" in value:
        raise ValueError("Please use plain text.")
    return value.strip()


def _filled(value: str) -> str:
    if not value:
        raise ValueError("Write a few words first.")
    return value


def _tags(ids: list[str]) -> list[str]:
    unknown = [i for i in ids if i not in OFFERED_IDS]
    if unknown:
        raise ValueError(f"Unknown skills: {', '.join(sorted(set(unknown)))}")
    if len(set(ids)) != len(ids):
        raise ValueError("Each skill can only be picked once.")
    return ids


def _skill(value: str | None) -> str | None:
    if value is not None and value not in OFFERED_IDS:
        raise ValueError("Unknown skill.")
    return value


Tags = Annotated[list[Annotated[str, Field(max_length=40)]], Field(max_length=MAX_TAGS)]


class EditStory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: Annotated[str, Field(max_length=800), AfterValidator(_plain)] = ""
    strengths: Annotated[str, Field(max_length=500), AfterValidator(_plain)] = ""
    gaps: Annotated[str, Field(max_length=500), AfterValidator(_plain)] = ""
    goal: Annotated[str, Field(max_length=300), AfterValidator(_plain)] = ""
    # Leave both out to take them from your focus lists.
    tag_strengths: Annotated[Tags, AfterValidator(_tags)] | None = None
    tag_gaps: Annotated[Tags, AfterValidator(_tags)] | None = None


class Story(BaseModel):
    id: UUID
    created_at: datetime
    origin: str
    strengths: str
    gaps: str
    goal: str
    tag_strengths: list[str]
    tag_gaps: list[str]
    tags_source: Literal["player", "rules", "ai"]


class Settings(BaseModel):
    ai_consent: bool
    onboarding: Literal["new", "skipped", "done"]


class EditSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Strict: only a real true or false counts as your answer.
    ai_consent: StrictBool | None = None
    onboarding: Literal["skipped", "done"] | None = None


class Note(BaseModel):
    id: UUID
    noted_on: date
    body: str
    skill: str | None
    created_at: datetime


class NewNote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: Annotated[
        str, Field(min_length=1, max_length=200), AfterValidator(_plain), AfterValidator(_filled)
    ]
    skill: Annotated[str | None, AfterValidator(_skill)] = None
    # Your local date; the server allows a day either side of its own.
    noted_on: date | None = None


class Journey(BaseModel):
    story: Story | None
    # Earlier versions, newest first, not including the current one.
    history: list[Story]
    settings: Settings
    notes: list[Note]
    # Days you've played (and reflected on) a game, saved a learning note or worked on your
    # story. Only ever goes up.
    learning_days: int
    # When your next check-in can come: two weeks after your last one, or after you started.
    # It comes if you've played or reflected on a game by then (migration 0034).
    next_checkin_after: datetime | None = None


def require_journey(session: Session) -> None:
    on: bool = session.execute(
        text("SELECT app_feature_on_for_me(:key)"), {"key": FEATURE}
    ).scalar_one()
    if not on:
        raise NOT_FOUND


def _stories(user: CurrentUserSession, limit: int) -> list[Story]:
    rows = user.session.execute(
        text(
            """
            SELECT id, created_at, origin, strengths, gaps, goal, tag_strengths, tag_gaps,
                   tags_source
            FROM journey_entries WHERE user_id = :me
            ORDER BY created_at DESC, id LIMIT :limit
            """
        ),
        {"me": user.user_id, "limit": limit},
    ).mappings()
    return [Story.model_validate(dict(row)) for row in rows]


def _settings(user: CurrentUserSession) -> Settings:
    row = user.session.execute(
        text("SELECT ai_consent, onboarding FROM journey_settings WHERE user_id = :me"),
        {"me": user.user_id},
    ).one_or_none()
    if row is None:
        return Settings(ai_consent=False, onboarding="new")
    return Settings(ai_consent=row.ai_consent, onboarding=row.onboarding)


def _notes(user: CurrentUserSession) -> list[Note]:
    rows = user.session.execute(
        text(
            "SELECT id, noted_on, body, skill, created_at FROM journey_notes "
            "WHERE user_id = :me ORDER BY noted_on DESC, created_at DESC LIMIT :limit"
        ),
        {"me": user.user_id, "limit": NOTES_SHOWN},
    ).mappings()
    return [Note.model_validate(dict(row)) for row in rows]


def _learning_days(user: CurrentUserSession) -> int:
    days: int = user.session.execute(
        text(
            """
            SELECT count(*) FROM (
                SELECT noted_on AS day FROM journey_notes WHERE user_id = :me
                UNION
                SELECT (created_at AT TIME ZONE 'UTC')::date FROM journey_entries
                WHERE user_id = :me
                UNION
                SELECT (r.created_at AT TIME ZONE 'UTC')::date FROM match_reflections r
                WHERE r.user_id = :me
                  AND cardinality(r.went_well) + cardinality(r.to_improve) > 0
            ) AS days
            """
        ),
        {"me": user.user_id},
    ).scalar_one()
    return days


def _next_checkin(user: CurrentUserSession) -> datetime | None:
    since: datetime | None = user.session.execute(
        text(
            "SELECT coalesce((SELECT max(period_end) FROM journey_checkins WHERE user_id = :me), "
            "(SELECT started_at FROM journey_settings WHERE user_id = :me))"
        ),
        {"me": user.user_id},
    ).scalar_one()
    return since + CHECKIN_EVERY if since else None


def _journey(user: CurrentUserSession) -> Journey:
    stories = _stories(user, HISTORY + 1)
    return Journey(
        story=stories[0] if stories else None,
        history=stories[1:],
        settings=_settings(user),
        notes=_notes(user),
        learning_days=_learning_days(user),
        next_checkin_after=_next_checkin(user),
    )


# Saves in the last 24 hours, by table.
_RECENT = {
    "journey_entries": text(
        "SELECT count(*) FROM journey_entries "
        "WHERE user_id = :me AND created_at > now() - interval '24 hours'"
    ),
    "journey_notes": text(
        "SELECT count(*) FROM journey_notes "
        "WHERE user_id = :me AND created_at > now() - interval '24 hours'"
    ),
}


def _recent(user: CurrentUserSession, table: str) -> int:
    count: int = user.session.execute(_RECENT[table], {"me": user.user_id}).scalar_one()
    return count


def _too_many(what: str) -> HTTPException:
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"That's a lot of {what} for one day. Try again tomorrow.",
    )


@router.get("")
def get_journey(user: CurrentUserSession) -> Journey:
    require_journey(user.session)
    # The first look starts your journey: check-ins count from here (migration 0034).
    user.session.execute(
        text("INSERT INTO journey_settings (user_id) VALUES (:me) ON CONFLICT DO NOTHING"),
        {"me": user.user_id},
    )
    return _journey(user)


@router.put("/story")
def save_story(body: EditStory, user: CurrentUserSession) -> Journey:
    """Save a new version of your story. Old versions are kept as they were."""
    require_journey(user.session)
    if not (body.origin or body.strengths or body.gaps or body.goal):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Write a little about your game first."
        )
    if _recent(user, "journey_entries") >= STORY_SAVES_PER_DAY:
        raise _too_many("saves")
    if body.tag_strengths is None and body.tag_gaps is None:
        # Not chosen: from your focus lists.
        focus = user.session.execute(
            text("SELECT strengths, improve FROM user_focus WHERE user_id = :me"),
            {"me": user.user_id},
        ).one_or_none()
        strengths = [i for i in (focus.strengths if focus else []) if i in OFFERED_IDS]
        gaps = [i for i in (focus.improve if focus else []) if i in OFFERED_IDS]
        tag_strengths, tag_gaps, source = strengths[:MAX_TAGS], gaps[:MAX_TAGS], "rules"
    else:
        tag_strengths, tag_gaps = body.tag_strengths or [], body.tag_gaps or []
        source = "player"
        if set(tag_strengths) & set(tag_gaps):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="A skill can be a strength or something to work on, not both.",
            )
    user.session.execute(
        text(
            """
            INSERT INTO journey_entries
                (user_id, origin, strengths, gaps, goal, tag_strengths, tag_gaps, tags_source)
            VALUES (:me, :origin, :strengths, :gaps, :goal, :tag_strengths, :tag_gaps, :source)
            """
        ),
        {
            "me": user.user_id,
            "origin": body.origin,
            "strengths": body.strengths,
            "gaps": body.gaps,
            "goal": body.goal,
            "tag_strengths": tag_strengths,
            "tag_gaps": tag_gaps,
            "source": source,
        },
    )
    _upsert_settings(user, onboarding="done")
    return _journey(user)


def _upsert_settings(
    user: CurrentUserSession, *, ai_consent: bool | None = None, onboarding: str | None = None
) -> None:
    user.session.execute(
        text(
            """
            INSERT INTO journey_settings (user_id, ai_consent, onboarding)
            VALUES (:me, coalesce(:consent, false), coalesce(:onboarding, 'new'))
            ON CONFLICT (user_id) DO UPDATE SET
                ai_consent = coalesce(:consent, journey_settings.ai_consent),
                onboarding = coalesce(:onboarding, journey_settings.onboarding),
                updated_at = now()
            """
        ),
        {"me": user.user_id, "consent": ai_consent, "onboarding": onboarding},
    )


@router.put("/settings")
def save_settings(body: EditSettings, user: CurrentUserSession) -> Settings:
    require_journey(user.session)
    _upsert_settings(user, ai_consent=body.ai_consent, onboarding=body.onboarding)
    return _settings(user)


@router.post("/notes", status_code=status.HTTP_201_CREATED)
def add_note(body: NewNote, user: CurrentUserSession) -> Note:
    require_journey(user.session)
    today = datetime.now(UTC).date()
    noted_on = body.noted_on or today
    if abs(noted_on - today) > timedelta(days=1):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="A note is for today.")
    if _recent(user, "journey_notes") >= NOTES_PER_DAY:
        raise _too_many("notes")
    row = (
        user.session.execute(
            text(
                """
            INSERT INTO journey_notes (user_id, noted_on, body, skill)
            VALUES (:me, :noted_on, :body, :skill)
            RETURNING id, noted_on, body, skill, created_at
            """
            ),
            {"me": user.user_id, "noted_on": noted_on, "body": body.body, "skill": body.skill},
        )
        .mappings()
        .one()
    )
    return Note.model_validate(dict(row))


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: UUID, user: CurrentUserSession) -> Response:
    require_journey(user.session)
    deleted = user.session.execute(
        text("DELETE FROM journey_notes WHERE id = :id AND user_id = :me RETURNING id"),
        {"id": note_id, "me": user.user_id},
    ).first()
    if deleted is None:
        raise NOT_FOUND
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class Pick(BaseModel):
    id: UUID
    kind: Literal["video", "article"]
    url: str
    title: str
    source: str
    skills: list[str]
    minutes: int | None


PICKS_SHOWN = 3


@router.get("/picks")
def picks(
    user: CurrentUserSession,
    skills: Annotated[list[str], Query(max_length=8)] = [],  # noqa: B006 - FastAPI copies it
) -> list[Pick]:
    """Published library items (migration 0033) for these skills (all, if none), that suit
    your level, the closest match first."""
    require_journey(user.session)
    wanted = [s for s in dict.fromkeys(skills) if s in OFFERED_IDS]
    if skills and not wanted:
        return []
    level = user.session.execute(
        text("SELECT self_level FROM users WHERE id = :me"), {"me": user.user_id}
    ).scalar_one_or_none()
    rows = user.session.execute(
        text("SELECT * FROM app_published_content(:skills, :level)"),
        {"skills": wanted, "level": level},
    ).mappings()
    return [Pick.model_validate(dict(row)) for row in rows][:PICKS_SHOWN]
