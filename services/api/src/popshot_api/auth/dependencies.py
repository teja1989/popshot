"""FastAPI dependency that turns the Authorization header into a verified identity.

On Cloud Run the web service authenticates itself with X-Serverless-Authorization, which
leaves the Authorization header free to carry the user's ID token.
"""

from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from popshot_api.auth.verifier import (
    InvalidTokenError,
    KeyFetchError,
    TokenVerifier,
    VerifiedIdentity,
)

log = structlog.get_logger(__name__)
_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Sign in to continue.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_token_verifier(request: Request) -> TokenVerifier:
    verifier: TokenVerifier = request.app.state.token_verifier
    return verifier


# Sync on purpose: fetching signing keys does blocking I/O, so FastAPI runs this in a thread.
def current_identity(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
) -> VerifiedIdentity:
    if credentials is None:
        raise _UNAUTHORIZED
    try:
        return verifier.verify(credentials.credentials)
    except InvalidTokenError as exc:
        log.info("auth.rejected", reason=exc.reason)
        raise _UNAUTHORIZED from None
    except KeyFetchError:
        log.warning("auth.keys_unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sign-in can't be checked right now. Try again shortly.",
        ) from None


CurrentIdentity = Annotated[VerifiedIdentity, Depends(current_identity)]
