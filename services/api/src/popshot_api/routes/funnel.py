"""Where people come from (migration 0024): a sign-up's source, and anonymous visit counts.

Both are only ever read on the admin service (routes/admin_funnel.py), plus each person's
own source in their data download (routes/export.py). Nothing here returns them.
"""

from typing import Literal

from fastapi import APIRouter, status
from pydantic import BaseModel
from sqlalchemy import text

from popshot_api.db import CounterSession, CurrentUserSession

router = APIRouter(prefix="/v1")

# Kept in step with SOURCES and PAGES in migration 0024 (a test checks).
SignupSource = Literal[
    "direct",
    "recap",
    "invite",
    "code",
    "reddit",
    "facebook",
    "nextdoor",
    "poster",
    "court",
    "partner",
    "other",
]
VisitPage = Literal["home", "recap", "recap_try", "invite"]


class SourceIn(BaseModel):
    source: SignupSource


class SourceRecorded(BaseModel):
    # False when it wasn't kept: the account isn't new, or already has a source.
    recorded: bool


@router.post("/me/source")
def record_source(body: SourceIn, user: CurrentUserSession) -> SourceRecorded:
    """Where the caller came from, sent once by the web app after sign-up."""
    recorded = user.session.execute(
        text("SELECT app_set_signup_source(:s)"), {"s": body.source}
    ).scalar_one()
    return SourceRecorded(recorded=bool(recorded))


class Visit(BaseModel):
    page: VisitPage
    source: SignupSource


@router.post("/public/visits", status_code=status.HTTP_204_NO_CONTENT)
def count_visit(body: Visit, session: CounterSession) -> None:
    """Add one to today's count for a page and source. Called by the web server, which
    rate-limits browsers; the API is only reachable from the web service."""
    session.execute(text("SELECT app_count_visit(:p, :s)"), {"p": body.page, "s": body.source})
