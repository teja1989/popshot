"""Database access.

Every request that touches data runs in exactly one transaction, and that transaction starts
by setting app.user_id with set_config(..., is_local => true), the function form of SET LOCAL.
The setting ends with the transaction, so it never leaks to the next request on a pooled
connection. Row-level security in Postgres does the rest (ADR 0002).
"""

import json
import threading
import time
import urllib.request
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session

from popshot_api.auth.dependencies import CurrentIdentity
from popshot_api.auth.verifier import VerifiedIdentity

APP_ROLE = "popshot_app"
OWNER_ROLE = "popshot_owner"
DISPLAY_NAME_MAX = 80
AVATAR_URL_MAX = 2048


class UnsafeDatabaseRoleError(RuntimeError):
    """The API is connected as a role that could get around row-level security."""


_METADATA_ACCESS_URL = (
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
)
_TOKEN_REFRESH_MARGIN = 300


class MetadataAccessToken:
    """OAuth access token for this service account, from the metadata server.

    Cloud SQL IAM database authentication accepts it as the password. Tokens last about an
    hour; a new connection gets a fresh one, and established connections stay valid.
    """

    def __init__(
        self,
        fetch: Callable[[], dict[str, Any]] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fetch = fetch or self._from_metadata_server
        self._clock = clock
        self._lock = threading.Lock()
        self._token: str | None = None
        self._expires_at = 0.0

    @staticmethod
    def _from_metadata_server() -> dict[str, Any]:
        request = urllib.request.Request(
            _METADATA_ACCESS_URL, headers={"Metadata-Flavor": "Google"}
        )
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
            data: dict[str, Any] = json.load(response)
        return data

    def __call__(self) -> str:
        with self._lock:
            if self._token is None or self._clock() > self._expires_at - _TOKEN_REFRESH_MARGIN:
                data = self._fetch()
                self._token = str(data["access_token"])
                self._expires_at = self._clock() + float(data["expires_in"])
            return self._token


def use_iam_token_as_password(engine: Engine, token: Callable[[], str]) -> None:
    @event.listens_for(engine, "do_connect")
    def _set_password(
        _dialect: object, _record: object, _cargs: object, cparams: dict[str, Any]
    ) -> None:
        cparams["password"] = token()


def make_engine(url: str, *, iam_auth: bool = False) -> Engine:
    engine = create_engine(
        url,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        pool_recycle=1800,
    )
    if iam_auth:
        use_iam_token_as_password(engine, MetadataAccessToken())
    return engine


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


_MEMBERSHIP_QUERY = text(
    """
    SELECT current_user AS name,
           pg_has_role(current_user, :app, 'USAGE') AS is_app,
           pg_has_role(current_user, :owner, 'MEMBER') AS is_owner
    """
)


def check_database_role(engine: Engine) -> None:
    """Refuse to run unless the login user gets its rights only from popshot_app."""
    with engine.connect() as connection:
        me = connection.execute(_MEMBERSHIP_QUERY, {"app": APP_ROLE, "owner": OWNER_ROLE}).one()
        unsafe = list(connection.execute(_UNSAFE_ROLE_QUERY).scalars())
    if not me.is_app:
        raise UnsafeDatabaseRoleError(f"{me.name!r} doesn't inherit {APP_ROLE!r}")
    if me.is_owner:
        raise UnsafeDatabaseRoleError(f"{me.name!r} is a member of {OWNER_ROLE!r}")
    if unsafe:
        raise UnsafeDatabaseRoleError(f"{me.name!r} has unsafe privileges via: {unsafe}")


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
        # Usage metrics (migration 0009): who used the app on which day, nothing more.
        session.execute(
            text(
                "INSERT INTO user_activity (user_id, day) VALUES (:user_id, current_date) "
                "ON CONFLICT DO NOTHING"
            ),
            {"user_id": user_id},
        )
        yield UserSession(session=session, user_id=user_id)


# scope="function": the transaction commits before the response is sent. With FastAPI's
# default ("request") it would commit after, so a client could act on a success before the
# change was visible to its next request, or be told it succeeded when the commit failed.
CurrentUserSession = Annotated[UserSession, Depends(user_session, scope="function")]
