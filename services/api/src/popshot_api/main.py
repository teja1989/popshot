"""App factory. Run with: uvicorn --factory popshot_api.main:create_app"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import Engine
from starlette.concurrency import run_in_threadpool

from popshot_api.auth.emulator import EmulatorTokenVerifier
from popshot_api.auth.google import GoogleIdTokenVerifier
from popshot_api.auth.verifier import TokenVerifier
from popshot_api.db import check_database_role, make_engine
from popshot_api.log_config import configure_logging
from popshot_api.middleware import RequestContextMiddleware
from popshot_api.routes import games, groups, health, invites, me
from popshot_api.settings import Settings


def create_app(
    settings: Settings | None = None,
    token_verifier: TokenVerifier | None = None,
    engine: Engine | None = None,
    *,
    verify_database_role: bool = True,
) -> FastAPI:
    """Build the app. `verify_database_role` exists for tests that don't use a database;
    it isn't reachable from configuration, so a deployed API always checks its role."""
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
                await run_in_threadpool(check_database_role, engine)
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title="Popshot API",
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
    app.include_router(me.router)
    app.include_router(groups.router)
    app.include_router(invites.router)
    app.include_router(games.router)
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
