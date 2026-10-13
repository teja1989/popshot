"""Looks up sign-in accounts (email, last sign-in) from Firebase, for the admin pages only.

Popshot's database doesn't store emails. When an admin opens a person, or searches by an
exact email, the API asks Identity Platform's accounts:lookup with its own service account
(it needs roles/firebaseauth.viewer). Nothing it returns is stored.

Off unless POPSHOT_ACCOUNT_LOOKUP is set (it is in prod): locally there's no service
account, and the admin pages say emails aren't available.
"""

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import structlog

from popshot_api.db import MetadataAccessToken

log = structlog.get_logger(__name__)

LOOKUP_URL = "https://identitytoolkit.googleapis.com/v1/projects/{project}/accounts:lookup"
TIMEOUT_SECONDS = 5


@dataclass(frozen=True, slots=True)
class Account:
    subject: str
    email: str | None
    disabled: bool
    last_sign_in: datetime | None


class LookupUnavailableError(Exception):
    """Accounts can't be looked up here (not configured) or right now (Google failed)."""


class AccountLookup(Protocol):
    def by_subject(self, subject: str) -> Account | None: ...

    def by_email(self, email: str) -> Account | None: ...


class NoAccountLookup:
    def by_subject(self, subject: str) -> Account | None:
        del subject
        raise LookupUnavailableError("account lookup is off")

    def by_email(self, email: str) -> Account | None:
        del email
        raise LookupUnavailableError("account lookup is off")


def _from_millis(value: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=UTC)
    except (TypeError, ValueError):
        return None


class IdentityPlatformLookup:
    def __init__(
        self,
        project_id: str,
        token: Callable[[], str] | None = None,
        post: Callable[[str, dict[str, Any], str], dict[str, Any]] | None = None,
    ) -> None:
        self._url = LOOKUP_URL.format(project=project_id)
        self._token = token or MetadataAccessToken()
        self._post = post or self._http_post

    @staticmethod
    def _http_post(url: str, body: dict[str, Any], token: str) -> dict[str, Any]:
        request = urllib.request.Request(  # noqa: S310 (a fixed https URL)
            url,
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
            data: dict[str, Any] = json.load(response)
        return data

    def _lookup(self, body: dict[str, Any]) -> Account | None:
        try:
            data = self._post(self._url, body, self._token())
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as exc:
            log.warning("accounts.lookup_failed", error=type(exc).__name__)
            raise LookupUnavailableError("lookup failed") from exc
        users = data.get("users") or []
        if not users:
            return None
        user = users[0]
        email = user.get("email")
        return Account(
            subject=str(user["localId"]),
            email=email if isinstance(email, str) else None,
            disabled=user.get("disabled") is True,
            last_sign_in=_from_millis(user.get("lastLoginAt")),
        )

    def by_subject(self, subject: str) -> Account | None:
        return self._lookup({"localId": [subject]})

    def by_email(self, email: str) -> Account | None:
        return self._lookup({"email": [email]})


DELETE_URL = "https://identitytoolkit.googleapis.com/v1/projects/{project}/accounts:delete"


class AccountDeleteError(Exception):
    """The sign-in couldn't be deleted just now; try again on the next run."""


class IdentityPlatformDeleter:
    """Deletes a person's Firebase sign-in (and with it their email), for the scheduled job
    when an account is deleted. Needs firebaseauth.users.delete, which only the job's
    service account has (a custom role in Terraform)."""

    def __init__(
        self,
        project_id: str,
        token: Callable[[], str] | None = None,
        post: Callable[[str, dict[str, Any], str], dict[str, Any]] | None = None,
    ) -> None:
        self._url = DELETE_URL.format(project=project_id)
        self._token = token or MetadataAccessToken()
        self._post = post or IdentityPlatformLookup._http_post

    def delete(self, subject: str) -> None:
        try:
            self._post(self._url, {"localId": subject}, self._token())
        except urllib.error.HTTPError as exc:
            # Already gone (say, a run that crashed after deleting it) is done.
            if exc.code == 400 and b"USER_NOT_FOUND" in exc.read():
                return
            log.warning("accounts.delete_failed", status=exc.code)
            raise AccountDeleteError("delete failed") from exc
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            log.warning("accounts.delete_failed", error=type(exc).__name__)
            raise AccountDeleteError("delete failed") from exc
