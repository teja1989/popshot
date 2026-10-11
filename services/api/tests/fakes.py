"""Test doubles. Lives under tests/ so it can never ship in the app."""

from popshot_api.accounts import Account, LookupUnavailableError
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


class FakeAccountLookup:
    """Sign-in accounts by subject; `unavailable` makes every lookup fail."""

    def __init__(self) -> None:
        self.accounts: dict[str, Account] = {}
        self.unavailable = False

    def add(self, subject: str, email: str) -> None:
        self.accounts[subject] = Account(subject, email, disabled=False, last_sign_in=None)

    def by_subject(self, subject: str) -> Account | None:
        if self.unavailable:
            raise LookupUnavailableError("unavailable (fake)")
        return self.accounts.get(subject)

    def by_email(self, email: str) -> Account | None:
        if self.unavailable:
            raise LookupUnavailableError("unavailable (fake)")
        return next((a for a in self.accounts.values() if a.email == email.lower()), None)
