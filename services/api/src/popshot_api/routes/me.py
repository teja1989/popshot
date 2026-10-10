from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from popshot_api.db import CurrentUserSession

router = APIRouter(prefix="/v1")


class Me(BaseModel):
    id: UUID
    display_name: str
    avatar_url: str | None


@router.get("/me")
def me(user: CurrentUserSession) -> Me:
    # Always filter explicitly. RLS is the backstop, not the filter.
    row = (
        user.session.execute(
            text("SELECT id, display_name, avatar_url FROM users WHERE id = :id"),
            {"id": user.user_id},
        )
        .mappings()
        .one()
    )
    return Me(**row)
