"""The admin service. Run with: uvicorn --factory popshot_api.admin_main:create_admin_app

Only /v1/admin (and /healthz). It's its own Cloud Run service with its own service account
and database login, the only one in popshot_admin, so the admin functions and account
lookups can't be reached from the main API at all. Who may use it is still decided per
request (routes/admin.py: the allowlist and a recent sign-in).
"""

from fastapi import FastAPI
from sqlalchemy import Engine

from popshot_api.accounts import IdentityPlatformLookup, NoAccountLookup
from popshot_api.auth.verifier import TokenVerifier
from popshot_api.main import base_app
from popshot_api.routes import (
    admin,
    admin_actions,
    admin_content,
    admin_features,
    admin_funnel,
    admin_lookup,
)
from popshot_api.settings import Settings


def create_admin_app(
    settings: Settings | None = None,
    token_verifier: TokenVerifier | None = None,
    engine: Engine | None = None,
    *,
    verify_database_role: bool = True,
) -> FastAPI:
    app = base_app(
        settings,
        token_verifier,
        engine,
        verify_database_role=verify_database_role,
        admin=True,
    )
    # Tests swap in a fake by setting app.state.account_lookup.
    app.state.account_lookup = (
        IdentityPlatformLookup(app.state.settings.firebase_project_id)
        if app.state.settings.account_lookup
        else NoAccountLookup()
    )
    app.include_router(admin.router)
    app.include_router(admin_lookup.router)
    app.include_router(admin_actions.router)
    app.include_router(admin_funnel.router)
    app.include_router(admin_features.router)
    app.include_router(admin_features.changes)
    app.include_router(admin_content.router)
    app.include_router(admin_content.changes)
    return app
