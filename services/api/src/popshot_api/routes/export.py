"""Download your data: everything Popshot holds about you, as one JSON file.

It runs as you, so row-level security decides what's in it, the same as what the app shows
you: your profile and settings, your crews, the games you played (with your crewmates' names
as you see them), your meetup answers, focus, game notes, your journey (story versions,
learning notes), invites and blocks, and where you first came from. Crews you've left aren't
readable any more, so only your membership row of those is included.

Your email isn't here: Google sign-in (Firebase) holds it, not Popshot's database.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from popshot_api.db import CurrentUserSession

router = APIRouter(prefix="/v1")

FORMAT_VERSION = 1


def _rows(session: Session, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in session.execute(text(sql), params).mappings()]


_PROFILE = """
    SELECT id, display_name, avatar_url, self_level, invite_code, hide_on_shared_cards,
           delete_requested_at, created_at
    FROM users WHERE id = :me
"""
_CREWS = """
    SELECT gm.group_id, g.name AS crew, gm.role, gm.status, gm.created_at AS joined_at,
           gm.left_at
    FROM group_members gm
    LEFT JOIN groups g ON g.id = gm.group_id
    WHERE gm.user_id = :me
    ORDER BY gm.created_at
"""
# Your games: who was on each side (as the app shows them) and the scores.
_GAMES = """
    SELECT m.id, g.name AS crew, m.played_at, m.format, m.points_to, m.win_by_two,
           me.team AS your_team,
           (SELECT array_agg(p.display_name ORDER BY p.display_name)
            FROM match_players mp JOIN players p ON p.id = mp.player_id
            WHERE mp.match_id = m.id AND mp.team = 'A') AS team_a,
           (SELECT array_agg(p.display_name ORDER BY p.display_name)
            FROM match_players mp JOIN players p ON p.id = mp.player_id
            WHERE mp.match_id = m.id AND mp.team = 'B') AS team_b,
           (SELECT json_agg(json_build_array(mg.team_a_score, mg.team_b_score)
                            ORDER BY mg.game_number)
            FROM match_games mg WHERE mg.match_id = m.id) AS scores
    FROM players mine
    JOIN match_players me ON me.player_id = mine.id
    JOIN matches m ON m.id = me.match_id
    JOIN groups g ON g.id = m.group_id
    WHERE mine.user_id = :me
    ORDER BY m.played_at
"""
_MEETUPS = """
    SELECT g.name AS crew, n.starts_at, n.venue, r.answer, r.updated_at
    FROM play_night_rsvps r
    JOIN play_nights n ON n.id = r.night_id
    JOIN groups g ON g.id = n.group_id
    WHERE r.user_id = :me
    ORDER BY n.starts_at
"""
_FOCUS = "SELECT strengths, improve, updated_at FROM user_focus WHERE user_id = :me"
_NOTES = """
    SELECT match_id, went_well, to_improve, created_at, updated_at
    FROM match_reflections WHERE user_id = :me ORDER BY created_at
"""
# Your journey (0032): every version of your story, your learning notes, your settings.
_STORIES = """
    SELECT created_at, origin, strengths, gaps, goal, tag_strengths, tag_gaps, tags_source
    FROM journey_entries WHERE user_id = :me ORDER BY created_at
"""
_LEARNING_NOTES = """
    SELECT noted_on, body, skill, created_at
    FROM journey_notes WHERE user_id = :me ORDER BY created_at
"""
_JOURNEY_SETTINGS = (
    "SELECT ai_consent, onboarding, started_at FROM journey_settings WHERE user_id = :me"
)
_CHECKINS = """
    SELECT period_start, period_end, chapter, headline, lines, try_next, written_by, written_at
    FROM journey_checkins WHERE user_id = :me ORDER BY period_end
"""
_NOTIFICATIONS = """
    SELECT (SELECT muted FROM notification_settings WHERE user_id = :me) AS muted,
           (SELECT count(*) FROM push_subscriptions WHERE user_id = :me) AS devices
"""


@router.get("/me/export")
def export_my_data(user: CurrentUserSession) -> JSONResponse:
    session, params = user.session, {"me": user.user_id}
    now = datetime.now(UTC)
    data: dict[str, Any] = {
        "format": FORMAT_VERSION,
        "exported_at": now,
        "note": (
            "Everything Popshot holds about you. Your email is kept by Google sign-in, "
            "not in this file."
        ),
        "profile": _rows(session, _PROFILE, params)[0],
        "crews": _rows(session, _CREWS, params),
        "games": _rows(session, _GAMES, params),
        "meetups": _rows(session, _MEETUPS, params),
        "focus": next(iter(_rows(session, _FOCUS, params)), None),
        "game_notes": _rows(session, _NOTES, params),
        "notifications": _rows(session, _NOTIFICATIONS, params)[0],
        "journey": {
            "stories": _rows(session, _STORIES, params),
            "learning_notes": _rows(session, _LEARNING_NOTES, params),
            "settings": next(iter(_rows(session, _JOURNEY_SETTINGS, params)), None),
            "checkins": _rows(session, _CHECKINS, params),
        },
        "invites": _rows(session, "SELECT * FROM app_my_direct_invites()", params),
        "blocked_crews": _rows(session, "SELECT * FROM app_my_invite_blocks()", params),
        # When you searched for or picked a court in the last two days (migration 0035): kept
        # only to limit how often anyone can ask Google.
        "court_searches": _rows(
            session,
            "SELECT kind, at FROM place_lookups WHERE user_id = :me ORDER BY at",
            params,
        ),
        # Open crews' listings you reported (migration 0036).
        "crew_reports": _rows(
            session,
            "SELECT group_id, reason, note, created_at, resolution FROM crew_reports "
            "WHERE reporter_id = :me ORDER BY created_at",
            params,
        ),
        # Where you first came from, if Popshot knows (migration 0024).
        "signup_source": session.execute(text("SELECT app_my_signup_source()")).scalar_one(),
    }
    filename = f"popshot-data-{now:%Y-%m-%d}.json"
    return JSONResponse(
        content=_jsonable(data),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _jsonable(value: Any) -> Any:
    """Dates and IDs as strings, so the file is plain JSON."""
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None or isinstance(value, bool | int | float | str):
        return value
    return str(value)
