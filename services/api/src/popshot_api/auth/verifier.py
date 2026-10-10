"""The token verification interface. Production uses Google; tests use a fake."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class VerifiedIdentity:
    """Claims we trust after a token has passed every check."""

    subject: str
    email: str
    display_name: str | None
    picture_url: str | None


class InvalidTokenError(Exception):
    """The token was rejected. `reason` is safe to log and never contains the token."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class KeyFetchError(Exception):
    """Signing keys couldn't be fetched, so no token can be checked right now."""


class TokenVerifier(Protocol):
    def verify(self, token: str) -> VerifiedIdentity:
        """Return the identity, or raise InvalidTokenError / KeyFetchError."""
        ...
