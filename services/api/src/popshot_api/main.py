"""App factory. Run with: uvicorn --factory popshot_api.main:create_app"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI
from sqlalchemy import Engine
from starlette.concurrency import run_in_threadpool

from popshot_api.auth.emulator import EmulatorTokenVerifier
from popshot_api.auth.google import GoogleIdTokenVerifier
from popshot_api.auth.verifier import TokenVerifier
from popshot_api.db import check_database_role, make_engine
from popshot_api.log_config import configure_logging
from popshot_api.middleware import RequestContextMiddleware
from popshot_api.push import PushSender
from popshot_api.routes import (
    board,
    calendar,
    focus,
    games,
    groups,
    health,
    invites,
    me,
    nights,
    notifications,
    recaps,
    stats,
)
from popshot_api.settings import Settings


def _push_sender_for(settings: Settings) -> PushSender | None:
    if settings.push_vapid_private_key is None:
        return None
    return PushSender(settings.push_vapid_private_key.get_secret_value(), settings.push_subject)


def base_app(
    settings: Settings | None,
    token_verifier: TokenVerifier | None,
    engine: Engine | None,
    *,
    verify_database_role: bool,
    admin: bool,
) -> FastAPI:
    """What the API and the admin service share: settings, the database engine (with its
    role check at startup), token verification, request logging and /healthz."""
    settings = settings if settings is not None else Settings()
    configure_logging(settings.log_level)
    engine = (
        engine
        if engine is not None
        else make_engine(
            settings.database_url.get_secret_value(), iam_auth=settings.database_iam_auth
        )
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            if verify_database_role:
                await run_in_threadpool(partial(check_database_role, engine, admin=admin))
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title="Popshot admin" if admin else "Popshot API",
        docs_url="/docs" if settings.expose_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.expose_docs else None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.token_verifier = (
        token_verifier if token_verifier is not None else _token_verifier_for(settings)
    )
    app.add_middleware(RequestContextMiddleware)
    app.include_router(health.router)
    return app


def create_app(
    settings: Settings | None = None,
    token_verifier: TokenVerifier | None = None,
    engine: Engine | None = None,
    *,
    verify_database_role: bool = True,
    push_sender: PushSender | None = None,
) -> FastAPI:
    """Build the API. `verify_database_role` exists for tests that don't use a database;
    it isn't reachable from configuration, so a deployed API always checks its role.
    The admin pages are a separate service (popshot_api.admin_main)."""
    app = base_app(
        settings,
        token_verifier,
        engine,
        verify_database_role=verify_database_role,
        admin=False,
    )
    settings = app.state.settings
    app.state.push_sender = push_sender if push_sender is not None else _push_sender_for(settings)
    app.include_router(me.router)
    app.include_router(groups.router)
    app.include_router(invites.router)
    app.include_router(games.router)
    app.include_router(focus.router)
    app.include_router(board.router)
    app.include_router(stats.router)
    app.include_router(notifications.router)
    app.include_router(nights.router)
    app.include_router(calendar.router)
    app.include_router(recaps.router)
    return app


def _token_verifier_for(settings: Settings) -> TokenVerifier:
    if settings.auth_emulator:
        # Settings already refused this outside local development.
        return EmulatorTokenVerifier(
            project_id=settings.firebase_project_id,
            allowed_providers=settings.allowed_sign_in_providers,
        )
    return GoogleIdTokenVerifier(
        project_id=settings.firebase_project_id,
        allowed_providers=settings.allowed_sign_in_providers,
    )
