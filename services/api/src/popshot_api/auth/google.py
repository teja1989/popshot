"""Verifies Google Identity Platform (Firebase Authentication) ID tokens.

Checks, in order: token size, header algorithm and key ID, RS256 signature against Google's
published keys, issuer, audience, expiry, issued-at and auth_time not in the future, subject,
sign-in provider, and email_verified.
"""

import time
from typing import Any, Protocol

import jwt
from jwt import PyJWKClient, PyJWKClientConnectionError, PyJWKClientError

from popshot_api.auth.verifier import InvalidTokenError, KeyFetchError, VerifiedIdentity

FIREBASE_JWKS_URL = (
    "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"
)
ALGORITHM = "RS256"
# Firebase ID tokens are around 1 KB. Anything far larger isn't one; don't parse it.
MAX_TOKEN_BYTES = 8192
MAX_SUBJECT_LENGTH = 128
CLOCK_SKEW_SECONDS = 30


class SigningKeySource(Protocol):
    def key_for(self, kid: str) -> Any:
        """Return the public key for this key ID, or raise InvalidTokenError / KeyFetchError."""
        ...


class GoogleSigningKeys:
    """Google's public signing keys, cached for an hour.

    An unknown key ID forces at most one refetch per cooldown window, so a flood of tokens
    with made-up key IDs can't turn into a flood of requests to Google.
    """

    def __init__(self, url: str = FIREBASE_JWKS_URL) -> None:
        self._client = PyJWKClient(
            url, cache_jwk_set=True, lifespan=3600, cooldown_duration=60, timeout=5
        )

    def key_for(self, kid: str) -> Any:
        try:
            return self._client.get_signing_key(kid).key
        except PyJWKClientConnectionError as exc:
            raise KeyFetchError("could not fetch Google signing keys") from exc
        except PyJWKClientError as exc:
            raise InvalidTokenError("unknown signing key") from exc


class GoogleIdTokenVerifier:
    def __init__(
        self,
        project_id: str,
        allowed_providers: frozenset[str],
        keys: SigningKeySource | None = None,
    ) -> None:
        if not allowed_providers:
            raise ValueError("at least one sign-in provider must be allowed")
        self._project_id = project_id
        self._issuer = f"https://securetoken.google.com/{project_id}"
        self._allowed_providers = allowed_providers
        self._keys = keys if keys is not None else GoogleSigningKeys()

    def verify(self, token: str) -> VerifiedIdentity:
        if not token or len(token.encode()) > MAX_TOKEN_BYTES:
            raise InvalidTokenError("malformed token")
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise InvalidTokenError("malformed token") from exc

        if header.get("alg") != ALGORITHM:
            raise InvalidTokenError("unexpected algorithm")
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise InvalidTokenError("missing key id")

        key = self._keys.key_for(kid)
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                key,
                algorithms=[ALGORITHM],
                audience=self._project_id,
                issuer=self._issuer,
                leeway=CLOCK_SKEW_SECONDS,
                options={"require": ["exp", "iat", "aud", "iss", "sub", "auth_time"]},
            )
        except jwt.PyJWTError as exc:
            raise InvalidTokenError(type(exc).__name__) from exc

        # PyJWT accepts a list that contains our audience; Firebase only ever sends a string.
        if claims["aud"] != self._project_id:
            raise InvalidTokenError("unexpected audience")
        return identity_from_claims(claims, self._allowed_providers)


def identity_from_claims(
    claims: dict[str, Any], allowed_providers: frozenset[str]
) -> VerifiedIdentity:
    """Checks shared by every verifier, run after signature, issuer, audience and expiry."""
    auth_time = claims["auth_time"]
    if not isinstance(auth_time, int) or isinstance(auth_time, bool):
        raise InvalidTokenError("invalid auth_time")
    if auth_time > time.time() + CLOCK_SKEW_SECONDS:
        raise InvalidTokenError("auth_time in the future")

    subject = claims["sub"]
    if not isinstance(subject, str) or not 0 < len(subject) <= MAX_SUBJECT_LENGTH:
        raise InvalidTokenError("invalid subject")

    firebase = claims.get("firebase")
    provider = firebase.get("sign_in_provider") if isinstance(firebase, dict) else None
    if provider not in allowed_providers:
        raise InvalidTokenError("sign-in provider not allowed")

    # Must be the JSON boolean true, not a truthy string.
    if claims.get("email_verified") is not True:
        raise InvalidTokenError("email not verified")
    email = claims.get("email")
    if not isinstance(email, str) or not email:
        raise InvalidTokenError("missing email")

    name = claims.get("name")
    picture = claims.get("picture")
    return VerifiedIdentity(
        subject=subject,
        email=email,
        display_name=name if isinstance(name, str) and name else None,
        picture_url=picture if isinstance(picture, str) and picture else None,
        auth_time=auth_time,
    )
