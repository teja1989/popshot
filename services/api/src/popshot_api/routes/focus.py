"""Your private focus areas and post-game reflections.

Only you can read or change these: the API filters by you, and row-level security limits
both tables to their owner (migration 0003). Nothing here is shown to anyone else.
"""

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import AfterValidator, BaseModel, ConfigDict, Field
from sqlalchemy import text

from popshot_api.db import CurrentUserSession
from popshot_api.focus import (
    FOCUS_OPTIONS,
    MAX_IMPROVE,
    MAX_PER_REFLECTION,
    MAX_STRENGTHS,
    OFFERED_IDS,
    SUGGEST_MIN,
    SUGGEST_WINDOW,
)
from popshot_api.routes.groups import NOT_FOUND

router = APIRouter(prefix="/v1")

# Reflections can be added or changed up to this long after a game was played.
REFLECT_WINDOW = timedelta(days=30)


def _known_and_unique(ids: list[str]) -> list[str]:
    unknown = [i for i in ids if i not in OFFERED_IDS]
    if unknown:
        raise ValueError(f"Unknown options: {', '.join(sorted(set(unknown)))}")
    if len(set(ids)) != len(ids):
        raise ValueError("Each option can only be picked once.")
    return ids


FocusId = Annotated[str, Field(max_length=40)]
Strengths = Annotated[
    list[FocusId], Field(max_length=MAX_STRENGTHS), AfterValidator(_known_and_unique)
]
Improve = Annotated[list[FocusId], Field(max_length=MAX_IMPROVE), AfterValidator(_known_and_unique)]
Picks = Annotated[
    list[FocusId], Field(max_length=MAX_PER_REFLECTION), AfterValidator(_known_and_unique)
]


class Option(BaseModel):
    id: str
    label: str
    area: str


class Suggestion(BaseModel):
    option_id: str
    # Which profile list it would join.
    kind: Literal["strength", "improve"]
    count: int
    out_of: int


class Focus(BaseModel):
    strengths: list[str]
    improve: list[str]
    suggestions: list[Suggestion]


class EditFocus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strengths: Strengths
    improve: Improve


class Reflection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Both empty means you skipped this game.
    went_well: Picks
    to_improve: Picks


def _no_overlap(first: list[str], second: list[str], message: str) -> None:
    if set(first) & set(second):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=message)


@router.get("/focus-options")
def focus_options() -> list[Option]:
    return [Option(id=o.id, label=o.label, area=o.area) for o in FOCUS_OPTIONS if not o.retired]


def _suggestions(
    user: CurrentUserSession, strengths: list[str], improve: list[str]
) -> list[Suggestion]:
    """Options you keep picking in reflections that aren't on that profile list yet."""
    rows = user.session.execute(
        text(
            """
            SELECT r.went_well, r.to_improve
            FROM match_reflections r
            JOIN matches m ON m.id = r.match_id
            WHERE r.user_id = :me AND cardinality(r.went_well) + cardinality(r.to_improve) > 0
            ORDER BY m.played_at DESC, r.match_id
            LIMIT :window
            """
        ),
        {"me": user.user_id, "window": SUGGEST_WINDOW},
    ).all()
    went_well = Counter(i for row in rows for i in row.went_well if i in OFFERED_IDS)
    to_improve = Counter(i for row in rows for i in row.to_improve if i in OFFERED_IDS)
    found = [
        Suggestion(option_id=i, kind="strength", count=n, out_of=len(rows))
        for i, n in went_well.items()
        if n >= SUGGEST_MIN and i not in strengths
    ] + [
        Suggestion(option_id=i, kind="improve", count=n, out_of=len(rows))
        for i, n in to_improve.items()
        if n >= SUGGEST_MIN and i not in improve
    ]
    order = {o.id: n for n, o in enumerate(FOCUS_OPTIONS)}
    # Most frequent first; strengths before areas to improve; then the list order.
    return sorted(found, key=lambda s: (-s.count, s.kind != "strength", order[s.option_id]))


def _focus(user: CurrentUserSession) -> Focus:
    row = user.session.execute(
        text("SELECT strengths, improve FROM user_focus WHERE user_id = :me"),
        {"me": user.user_id},
    ).one_or_none()
    strengths: list[str] = list(row.strengths) if row else []
    improve: list[str] = list(row.improve) if row else []
    return Focus(
        strengths=strengths,
        improve=improve,
        suggestions=_suggestions(user, strengths, improve),
    )


@router.get("/me/focus")
def get_focus(user: CurrentUserSession) -> Focus:
    return _focus(user)


@router.put("/me/focus")
def put_focus(body: EditFocus, user: CurrentUserSession) -> Focus:
    _no_overlap(
        body.strengths,
        body.improve,
        "An option can be a strength or an area to improve, not both.",
    )
    user.session.execute(
        text(
            """
            INSERT INTO user_focus (user_id, strengths, improve)
            VALUES (:me, :strengths, :improve)
            ON CONFLICT (user_id) DO UPDATE
            SET strengths = EXCLUDED.strengths, improve = EXCLUDED.improve, updated_at = now()
            """
        ),
        {"me": user.user_id, "strengths": body.strengths, "improve": body.improve},
    )
    return _focus(user)


@router.put("/groups/{group_id}/matches/{match_id}/reflection")
def reflect(
    group_id: UUID, match_id: UUID, body: Reflection, user: CurrentUserSession
) -> Reflection:
    """Save (or change) your reflection on a game you played. Both lists empty = skipped."""
    session, me = user.session, user.user_id
    match = session.execute(
        text(
            """
            SELECT m.played_at,
                   EXISTS (SELECT 1 FROM match_players mp JOIN players p ON p.id = mp.player_id
                           WHERE mp.match_id = m.id AND p.user_id = :me) AS played
            FROM matches m
            JOIN group_members gm
              ON gm.group_id = m.group_id AND gm.user_id = :me AND gm.status = 'active'
            WHERE m.id = :match_id AND m.group_id = :group_id
            """
        ),
        {"me": me, "match_id": match_id, "group_id": group_id},
    ).one_or_none()
    if match is None:
        raise NOT_FOUND
    if not match.played:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="You can only reflect on games you played in."
        )
    if match.played_at < datetime.now(UTC) - REFLECT_WINDOW:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Reflections can be added up to 30 days after a game.",
        )
    _no_overlap(
        body.went_well,
        body.to_improve,
        "Pick an option for what went well or what to improve, not both.",
    )
    session.execute(
        text(
            """
            INSERT INTO match_reflections (match_id, group_id, user_id, went_well, to_improve)
            VALUES (:match_id, :group_id, :me, :went_well, :to_improve)
            ON CONFLICT (match_id, user_id) DO UPDATE
            SET went_well = EXCLUDED.went_well, to_improve = EXCLUDED.to_improve,
                updated_at = now()
            """
        ),
        {
            "match_id": match_id,
            "group_id": group_id,
            "me": me,
            "went_well": body.went_well,
            "to_improve": body.to_improve,
        },
    )
    return body
