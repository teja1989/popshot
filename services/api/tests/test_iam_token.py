from typing import Any

import pytest

from popshot_api.db import MetadataAccessToken


def test_caches_until_close_to_expiry() -> None:
    now = [1000.0]
    responses = iter(
        [
            {"access_token": "first", "expires_in": 3599},
            {"access_token": "second", "expires_in": 3599},
        ]
    )
    calls: list[int] = []

    def fetch() -> dict[str, Any]:
        calls.append(1)
        return next(responses)

    token = MetadataAccessToken(fetch, clock=lambda: now[0])
    assert token() == "first"
    now[0] += 3000
    assert token() == "first"
    now[0] += 400  # within five minutes of expiry
    assert token() == "second"
    assert len(calls) == 2


def test_bad_metadata_response_raises() -> None:
    token = MetadataAccessToken(lambda: {"nope": True})
    with pytest.raises(KeyError):
        token()
