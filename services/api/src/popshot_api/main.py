"""App factory. Run with: uvicorn --factory popshot_api.main:create_app"""

from fastapi import FastAPI

from popshot_api.auth.google import GoogleIdTokenVerifier
from popshot_api.auth.verifier import TokenVerifier
from popshot_api.log_config import configure_logging
from popshot_api.middleware import RequestContextMiddleware
from popshot_api.routes import health, me
from popshot_api.settings import Settings


def create_app(
    settings: Settings | None = None,
    token_verifier: TokenVerifier | None = None,
) -> FastAPI:
    settings = settings if settings is not None else Settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Popshot API",
        docs_url="/docs" if settings.expose_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.expose_docs else None,
    )
    app.state.settings = settings
    app.state.token_verifier = (
        token_verifier
        if token_verifier is not None
        else GoogleIdTokenVerifier(
            project_id=settings.firebase_project_id,
            allowed_providers=settings.allowed_sign_in_providers,
        )
    )
    app.add_middleware(RequestContextMiddleware)
    app.include_router(health.router)
    app.include_router(me.router)
    return app
