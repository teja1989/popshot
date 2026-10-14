"""Your journey check-ins (migration 0034): the list, and one, written when first opened.

The scheduled job makes a check-in every two weeks you played or reflected; opening it writes
its words from that period's facts (journey_checkin.py) and keeps them. Gemini writes them
when you've said yes and the 'you.journey_ai' switch is on; otherwise, or if anything about
the AI's words isn't right, Popshot's own words. A check-in Popshot wrote because the AI
failed is tried again later, a few times at most. Yours alone, like the rest of the journey.
"""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from popshot_api import journey_ai
from popshot_api.ai_recap import RecapWriter
from popshot_api.db import CurrentUserSession
from popshot_api.journey_checkin import (
    CHAPTER_LABEL,
    Chapter,
    Words,
    build_facts,
    lines_for,
    pick_skills,
)
from popshot_api.recap_lines import first_name
from popshot_api.routes.journey import Pick, require_journey

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/me/journey/checkins")

AI_FEATURE = "you.journey_ai"
LISTED = 26
# Popshot's own words, written because the AI failed, are tried again after this long.
RETRY_AFTER = timedelta(hours=6)

NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, detail="We couldn't find that check-in.")


class CheckinSummary(BaseModel):
    id: UUID
    period_start: datetime
    period_end: datetime
    ready: bool
    chapter: str | None
    headline: str | None
    opened: bool


class Checkin(CheckinSummary):
    lines: list[str]
    try_next: str
    picks: list[Pick]
    # Who wrote the words: Popshot's own lines, or Gemini (kept for us; never labelled in the app).
    written_by: Literal["popshot", "ai"]
    new_chapter: bool


def _summary(row: Any) -> CheckinSummary:
    return CheckinSummary(
        id=row.id,
        period_start=row.period_start,
        period_end=row.period_end,
        ready=row.status == "ready",
        chapter=CHAPTER_LABEL[row.chapter] if row.chapter else None,
        headline=row.headline,
        opened=row.opened_at is not None,
    )


@router.get("")
def list_checkins(user: CurrentUserSession) -> list[CheckinSummary]:
    require_journey(user.session)
    rows = user.session.execute(
        text(
            "SELECT id, period_start, period_end, status, chapter, headline, opened_at "
            "FROM journey_checkins WHERE user_id = :me ORDER BY period_end DESC LIMIT :n"
        ),
        {"me": user.user_id, "n": LISTED},
    ).all()
    return [_summary(row) for row in rows]


def _ai_allowed(request: Request, session: Session, me: UUID) -> RecapWriter | None:
    writer: RecapWriter | None = request.app.state.journey_writer
    if writer is None:
        return None
    consent = session.execute(
        text("SELECT ai_consent FROM journey_settings WHERE user_id = :me"), {"me": me}
    ).scalar_one_or_none()
    on = session.execute(
        text("SELECT app_feature_on_for_me(:key)"), {"key": AI_FEATURE}
    ).scalar_one()
    return writer if consent and on else None


def _crewmates(session: Session, me: UUID) -> set[str]:
    names = session.execute(
        text(
            """
            SELECT DISTINCT p.display_name FROM players p
            JOIN group_members gm ON gm.group_id = p.group_id
                AND gm.user_id = :me AND gm.status = 'active'
            WHERE p.user_id IS DISTINCT FROM :me
            """
        ),
        {"me": me},
    ).scalars()
    return {first_name(n) for n in names}


def _digest(facts: dict[str, Any], model: str) -> str:
    blob = json.dumps(
        {"v": journey_ai.PROMPT_VERSION, "model": model, "facts": facts},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(blob.encode()).hexdigest()


def _picks(session: Session, me: UUID, skills: list[str]) -> list[Pick]:
    if not skills:
        return []
    level = session.execute(
        text("SELECT self_level FROM users WHERE id = :me"), {"me": me}
    ).scalar_one_or_none()
    rows = session.execute(
        text("SELECT * FROM app_published_content(:skills, :level)"),
        {"skills": skills, "level": level},
    ).mappings()
    return [Pick.model_validate(dict(r)) for r in rows][:3]


def _chapter_before(user: CurrentUserSession, row: Any) -> Chapter | None:
    """The chapter of the check-in before this one, if any."""
    chapter: Chapter | None = user.session.execute(
        text(
            "SELECT chapter FROM journey_checkins WHERE user_id = :me AND status = 'ready' "
            "AND period_end < :end ORDER BY period_end DESC LIMIT 1"
        ),
        {"me": user.user_id, "end": row.period_end},
    ).scalar_one_or_none()
    return chapter


def _write(
    request: Request, user: CurrentUserSession, row: Any
) -> tuple[Words, str, str | None, Chapter, list[Pick], int]:
    """(words, who wrote them, model, chapter, picks, attempts used)."""
    session, me = user.session, user.user_id
    facts = build_facts(session, me, row.period_start, row.period_end, _chapter_before(user, row))
    chapter: Chapter = facts["chapter_id"]
    picks = _picks(session, me, pick_skills(facts))
    writer = _ai_allowed(request, session, me)
    attempts = row.attempts
    if writer is not None and attempts < journey_ai.MAX_ATTEMPTS:
        attempts += 1
        given = journey_ai.ai_facts(facts)
        try:
            words = journey_ai.check(writer.write(given), given, _crewmates(session, me))
        except Exception as exc:  # noqa: BLE001  (any failure falls back to Popshot's words)
            log.warning("journey.ai_failed", error=type(exc).__name__)
            words = None
        else:
            if words is None:
                log.warning("journey.ai_rejected")
        if words is not None:
            return words, "ai", writer.model, chapter, picks, attempts
    return lines_for(facts), "popshot", None, chapter, picks, attempts


def _picks_by_id(session: Session, ids: list[UUID]) -> list[Pick]:
    """Kept picks that are still published, in their order."""
    if not ids:
        return []
    rows = session.execute(
        text("SELECT * FROM app_published_content('{}', NULL)"),
    ).mappings()
    found = {r["id"]: Pick.model_validate(dict(r)) for r in rows}
    return [found[i] for i in ids if i in found]


@router.get("/{checkin_id}")
def open_checkin(checkin_id: UUID, request: Request, user: CurrentUserSession) -> Checkin:
    require_journey(user.session)
    session, me = user.session, user.user_id
    row = session.execute(
        text("SELECT * FROM journey_checkins WHERE id = :id AND user_id = :me FOR UPDATE"),
        {"id": checkin_id, "me": me},
    ).one_or_none()
    if row is None:
        raise NOT_FOUND
    now = datetime.now(UTC)
    retry = (
        row.status == "ready"
        and row.written_by == "popshot"
        and row.attempts > 0
        and row.attempts < journey_ai.MAX_ATTEMPTS
        and row.written_at < now - RETRY_AFTER
        and _ai_allowed(request, session, me) is not None
    )
    if row.status == "pending" or retry:
        words, by, model, chapter, picks, attempts = _write(request, user, row)
        session.execute(
            text(
                """
                UPDATE journey_checkins SET status = 'ready', chapter = :chapter,
                    headline = :headline, lines = :lines, try_next = :try_next, picks = :picks,
                    written_by = :by, model = :model, attempts = :attempts, written_at = now(),
                    opened_at = coalesce(opened_at, now())
                WHERE id = :id AND user_id = :me
                """
            ),
            {
                "id": checkin_id,
                "me": me,
                "chapter": chapter,
                "headline": words.headline,
                "lines": list(words.lines),
                "try_next": words.try_next,
                "picks": [p.id for p in picks],
                "by": by,
                "model": model,
                "attempts": attempts,
            },
        )
        row = session.execute(
            text("SELECT * FROM journey_checkins WHERE id = :id"), {"id": checkin_id}
        ).one()
    else:
        picks = _picks_by_id(session, list(row.picks))
        if row.opened_at is None:
            session.execute(
                text("UPDATE journey_checkins SET opened_at = now() WHERE id = :id"),
                {"id": checkin_id},
            )
    before = _chapter_before(user, row)
    return Checkin(
        **_summary(row).model_dump(exclude={"opened"}),
        opened=True,
        lines=list(row.lines),
        try_next=row.try_next,
        picks=picks,
        written_by=row.written_by,
        new_chapter=before is not None and before != row.chapter,
    )
