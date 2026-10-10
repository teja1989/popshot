"""Test doubles. Lives under tests/ so it can never ship in the app."""

from popshot_api.auth.verifier import InvalidTokenError, KeyFetchError, VerifiedIdentity


class FakeTokenVerifier:
    """Accepts only the tokens it was given. No network, no crypto."""

    def __init__(self, identities: dict[str, VerifiedIdentity] | None = None) -> None:
        self.identities = dict(identities or {})
        self.keys_unavailable = False

    def verify(self, token: str) -> VerifiedIdentity:
        if self.keys_unavailable:
            raise KeyFetchError("keys unavailable (fake)")
        try:
            return self.identities[token]
        except KeyError:
            raise InvalidTokenError("unknown token (fake)") from None
