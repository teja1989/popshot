from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.orm import Session

from popshot_api.db import CurrentUserSession
from popshot_api.routes.groups import PersonName

router = APIRouter(prefix="/v1")


class Me(BaseModel):
    id: UUID
    display_name: str
    avatar_url: str | None
    # Where your crew points start: beginner, intermediate, advanced, expert, or unset.
    self_level: str | None = None


class EditMe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: PersonName


def _me(session: Session, user_id: UUID) -> Me:
    # Always filter explicitly. RLS is the backstop, not the filter.
    row = (
        session.execute(
            text("SELECT id, display_name, avatar_url, self_level FROM users WHERE id = :id"),
            {"id": user_id},
        )
        .mappings()
        .one()
    )
    return Me(**row)


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
