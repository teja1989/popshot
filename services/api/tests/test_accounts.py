"""popshot_api.accounts against a fake HTTP call: what's asked, and what comes back."""

import urllib.error
from datetime import UTC, datetime
from typing import Any

import pytest

from popshot_api.accounts import (
    IdentityPlatformLookup,
    LookupUnavailableError,
    NoAccountLookup,
)


class FakePost:
    def __init__(self, reply: dict[str, Any] | Exception) -> None:
        self.reply = reply
        self.calls: list[tuple[str, dict[str, Any], str]] = []

    def __call__(self, url: str, body: dict[str, Any], token: str) -> dict[str, Any]:
        self.calls.append((url, body, token))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def lookup(post: FakePost) -> IdentityPlatformLookup:
    return IdentityPlatformLookup("ps-prod-1234", token=lambda: "sa-token", post=post)


def test_by_subject_asks_for_that_account_and_reads_the_reply() -> None:
    post = FakePost(
        {
            "users": [
                {
                    "localId": "uid-1",
                    "email": "casey@example.com",
                    "disabled": False,
                    "lastLoginAt": "1760000000000",
                }
            ]
        }
    )
    account = lookup(post).by_subject("uid-1")
    assert post.calls == [
        (
            "https://identitytoolkit.googleapis.com/v1/projects/ps-prod-1234/accounts:lookup",
            {"localId": ["uid-1"]},
            "sa-token",
        )
    ]
    assert account is not None
    assert (account.subject, account.email, account.disabled) == (
        "uid-1",
        "casey@example.com",
        False,
    )
    assert account.last_sign_in == datetime.fromtimestamp(1_760_000_000, tz=UTC)


def test_by_email() -> None:
    post = FakePost({"users": [{"localId": "uid-2", "disabled": True}]})
    account = lookup(post).by_email("sam@example.com")
    assert post.calls[0][1] == {"email": ["sam@example.com"]}
    assert account is not None
    assert (account.email, account.disabled, account.last_sign_in) == (None, True, None)


def test_no_such_account() -> None:
    assert lookup(FakePost({})).by_subject("nobody") is None


@pytest.mark.parametrize(
    "failure",
    [urllib.error.URLError("down"), TimeoutError(), ValueError("not json")],
)
def test_failures_say_unavailable(failure: Exception) -> None:
    with pytest.raises(LookupUnavailableError):
        lookup(FakePost(failure)).by_subject("uid-1")


def test_lookup_off() -> None:
    with pytest.raises(LookupUnavailableError):
        NoAccountLookup().by_email("casey@example.com")
