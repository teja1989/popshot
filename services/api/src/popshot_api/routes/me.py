from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.orm import Session

from popshot_api.db import CurrentUserSession
from popshot_api.routes.groups import PersonName

router = APIRouter(prefix="/v1")

# How long you have to change your mind (migration 0023's UNDO_DAYS).
DELETE_AFTER = timedelta(days=7)


class Me(BaseModel):
    id: UUID
    display_name: str
    avatar_url: str | None
    # Where your crew points start: beginner, intermediate, advanced, expert, or unset.
    self_level: str | None = None
    # Shown as "Crew member" on recap cards shared outside the app.
    hide_on_shared_cards: bool = False
    # When you asked to delete your account; it's deleted for good DELETE_AFTER later.
    delete_requested_at: datetime | None = None
    delete_on: datetime | None = None


class EditMe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: PersonName


class SharedCards(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hide_on_shared_cards: bool


def _me(session: Session, user_id: UUID) -> Me:
    # Always filter explicitly. RLS is the backstop, not the filter.
    row = (
        session.execute(
            text(
                "SELECT id, display_name, avatar_url, self_level, hide_on_shared_cards, "
                "delete_requested_at FROM users WHERE id = :id"
            ),
            {"id": user_id},
        )
        .mappings()
        .one()
    )
    requested = row["delete_requested_at"]
    return Me(**row, delete_on=requested + DELETE_AFTER if requested else None)


@router.get("/me")
def me(user: CurrentUserSession) -> Me:
    return _me(user.session, user.user_id)


@router.patch("/me")
def edit_me(body: EditMe, user: CurrentUserSession) -> Me:
    """Change your name. Signing in again doesn't overwrite it with the Google name."""
    user.session.execute(
        text("UPDATE users SET display_name = :name WHERE id = :id"),
        {"name": body.display_name, "id": user.user_id},
    )
    # Your player in each group you're active in shows the same name. Groups you've left
    # keep the name you had there (row-level security limits this to active groups anyway).
    user.session.execute(
        text(
            """
            UPDATE players p SET display_name = :name
            FROM group_members gm
            WHERE p.user_id = :id AND gm.group_id = p.group_id AND gm.user_id = p.user_id
              AND gm.status = 'active'
            """
        ),
        {"name": body.display_name, "id": user.user_id},
    )
    return _me(user.session, user.user_id)


@router.put("/me/shared-cards")
def set_shared_cards(body: SharedCards, user: CurrentUserSession) -> Me:
    """Whether you're named on recap cards shared outside the app."""
    user.session.execute(
        text("UPDATE users SET hide_on_shared_cards = :hide WHERE id = :id"),
        {"hide": body.hide_on_shared_cards, "id": user.user_id},
    )
    return _me(user.session, user.user_id)


@router.post("/me/delete")
def request_deletion(user: CurrentUserSession) -> Me:
    """Ask to delete your account. It's deleted for good in 7 days unless you cancel.

    A crew you lead that has other members needs a new lead first, as when leaving.
    """
    leading = (
        user.session.execute(
            text(
                """
                SELECT g.name FROM group_members me
                JOIN groups g ON g.id = me.group_id AND g.deleted_at IS NULL
                WHERE me.user_id = :me AND me.status = 'active' AND me.role = 'lead'
                  AND EXISTS (
                      SELECT 1 FROM group_members other
                      WHERE other.group_id = me.group_id AND other.user_id <> :me
                        AND other.status = 'active'
                  )
                ORDER BY lower(g.name)
                """
            ),
            {"me": user.user_id},
        )
        .scalars()
        .all()
    )
    if leading:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=(
                f"First make someone else the lead of {_names(list(leading))}. "
                "You can do that on the crew's members page."
            ),
        )
    user.session.execute(
        text(
            "UPDATE users SET delete_requested_at = coalesce(delete_requested_at, now()) "
            "WHERE id = :me"
        ),
        {"me": user.user_id},
    )
    return _me(user.session, user.user_id)


@router.post("/me/delete/cancel")
def cancel_deletion(user: CurrentUserSession) -> Me:
    """Keep your account."""
    user.session.execute(
        text("UPDATE users SET delete_requested_at = NULL WHERE id = :me"), {"me": user.user_id}
    )
    return _me(user.session, user.user_id)


def _names(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} and {names[-1]}"
