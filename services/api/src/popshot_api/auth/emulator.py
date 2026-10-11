"""Accepts Firebase Auth emulator ID tokens. Local development only.

The emulator signs nothing: its tokens have algorithm "none" and an empty signature, so anyone
can make one. Settings allow this verifier only with POPSHOT_ENVIRONMENT=local, a demo-*
project (Firebase's offline-only projects) and not on Cloud Run. Everything except the
signature is checked exactly as in production.
"""

from typing import Any

import jwt

from popshot_api.auth.google import CLOCK_SKEW_SECONDS, MAX_TOKEN_BYTES, identity_from_claims
from popshot_api.auth.verifier import InvalidTokenError, VerifiedIdentity

DEMO_PROJECT_PREFIX = "demo-"


class EmulatorTokenVerifier:
    def __init__(self, project_id: str, allowed_providers: frozenset[str]) -> None:
        if not project_id.startswith(DEMO_PROJECT_PREFIX):
            raise ValueError("emulator tokens are only accepted for demo-* projects")
        if not allowed_providers:
            raise ValueError("at least one sign-in provider must be allowed")
        self._project_id = project_id
        self._issuer = f"https://securetoken.google.com/{project_id}"
        self._allowed_providers = allowed_providers

    def verify(self, token: str) -> VerifiedIdentity:
        if not token or len(token.encode()) > MAX_TOKEN_BYTES:
            raise InvalidTokenError("malformed token")
        # An emulator token is exactly header.payload. with an empty signature.
        if token.count(".") != 2 or not token.endswith("."):
            raise InvalidTokenError("not an emulator token")
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise InvalidTokenError("malformed token") from exc
        if header.get("alg") != "none":
            raise InvalidTokenError("not an emulator token")

        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                options={
                    "verify_signature": False,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                    "require": ["exp", "iat", "aud", "iss", "sub", "auth_time"],
                },
                audience=self._project_id,
                issuer=self._issuer,
                leeway=CLOCK_SKEW_SECONDS,
            )
        except jwt.PyJWTError as exc:
            raise InvalidTokenError(type(exc).__name__) from exc

        if claims["aud"] != self._project_id:
            raise InvalidTokenError("unexpected audience")
        return identity_from_claims(claims, self._allowed_providers)
