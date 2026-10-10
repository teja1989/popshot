"""Database access.

Every request that touches data runs in exactly one transaction, and that transaction starts
by setting app.user_id with set_config(..., is_local => true), the function form of SET LOCAL.
The setting ends with the transaction, so it never leaks to the next request on a pooled
connection. Row-level security in Postgres does the rest (ADR 0002).
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from popshot_api.auth.dependencies import CurrentIdentity
from popshot_api.auth.verifier import VerifiedIdentity

APP_ROLE = "popshot_app"
DISPLAY_NAME_MAX = 80
AVATAR_URL_MAX = 2048


class UnsafeDatabaseRoleError(RuntimeError):
    """The API is connected as a role that could get around row-level security."""


def make_engine(url: str) -> Engine:
    return create_engine(
        url,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


# Any role the current user is (directly or indirectly) a member of, that is a superuser,
# can bypass RLS, can create roles, or owns a table, view or function in this database.
_UNSAFE_ROLE_QUERY = text(
    """
    SELECT r.rolname
    FROM pg_roles r
    WHERE pg_has_role(current_user, r.oid, 'MEMBER')
      AND (
        r.rolsuper OR r.rolbypassrls OR r.rolcreaterole
        OR EXISTS (SELECT 1 FROM pg_class c
                   WHERE c.relowner = r.oid
                     AND c.relnamespace NOT IN ('pg_catalog'::regnamespace,
                                                'information_schema'::regnamespace))
        OR EXISTS (SELECT 1 FROM pg_proc p
                   WHERE p.proowner = r.oid
                     AND p.pronamespace NOT IN ('pg_catalog'::regnamespace,
                                                'information_schema'::regnamespace))
      )
    ORDER BY r.rolname
    """
)


def check_database_role(engine: Engine) -> None:
    """Refuse to run unless connected as the unprivileged app role."""
    with engine.connect() as connection:
        current = connection.execute(text("SELECT current_user")).scalar_one()
        unsafe = list(connection.execute(_UNSAFE_ROLE_QUERY).scalars())
    if current != APP_ROLE:
        raise UnsafeDatabaseRoleError(f"connected as {current!r}, expected {APP_ROLE!r}")
    if unsafe:
        raise UnsafeDatabaseRoleError(f"{APP_ROLE} has unsafe privileges via: {unsafe}")


@dataclass(frozen=True, slots=True)
class UserSession:
    session: Session
    user_id: UUID


def _profile(identity: VerifiedIdentity) -> tuple[str, str | None]:
    name = (identity.display_name or "").strip()[:DISPLAY_NAME_MAX] or "Player"
    avatar = identity.picture_url
    if avatar is not None and (len(avatar) > AVATAR_URL_MAX or not avatar.startswith("https://")):
        avatar = None
    return name, avatar


def get_engine(request: Request) -> Engine:
    engine: Engine = request.app.state.engine
    return engine


def user_session(
    identity: CurrentIdentity,
    engine: Annotated[Engine, Depends(get_engine)],
) -> Iterator[UserSession]:
    """One transaction per request, scoped to the signed-in user. Commits on success."""
    name, avatar = _profile(identity)
    with Session(engine) as session, session.begin():
        user_id = session.execute(
            text("SELECT app_resolve_user(:subject, :name, :avatar)"),
            {"subject": identity.subject, "name": name, "avatar": avatar},
        ).scalar_one()
        session.execute(
            text("SELECT set_config('app.user_id', :user_id, true)"),
            {"user_id": str(user_id)},
        )
        yield UserSession(session=session, user_id=user_id)


CurrentUserSession = Annotated[UserSession, Depends(user_session)]
