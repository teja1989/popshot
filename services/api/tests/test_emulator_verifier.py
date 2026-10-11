"""EmulatorTokenVerifier: unsigned emulator tokens, every other check as in production."""

import base64
import json
import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from popshot_api.auth.emulator import EmulatorTokenVerifier
from popshot_api.auth.verifier import InvalidTokenError

PROJECT = "demo-popshot"
_DROP = object()


def _b64(data: dict[str, Any]) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")


def _claims(**overrides: Any) -> dict[str, Any]:
    # The shape the Firebase Auth emulator (firebase-tools 15.31.0) issues for Google sign-in.
    now = int(time.time())
    claims: dict[str, Any] = {
        "name": "Alice Local",
        "email": "alice@example.com",
        "email_verified": True,
        "auth_time": now - 5,
        "user_id": "pa3xICXWrvvNJlNzIcqIHg0dK98C",
        "firebase": {
            "identities": {"email": ["alice@example.com"], "google.com": ["alice-123"]},
            "sign_in_provider": "google.com",
        },
        "iat": now - 5,
        "exp": now + 3600,
        "aud": PROJECT,
        "iss": f"https://securetoken.google.com/{PROJECT}",
        "sub": "pa3xICXWrvvNJlNzIcqIHg0dK98C",
    }
    claims.update(overrides)
    return {k: v for k, v in claims.items() if v is not _DROP}


def _emulator_token(
    claims: dict[str, Any] | None = None, header: dict[str, Any] | None = None
) -> str:
    header = header if header is not None else {"alg": "none", "typ": "JWT"}
    return f"{_b64(header)}.{_b64(claims if claims is not None else _claims())}."


@pytest.fixture
def verifier() -> EmulatorTokenVerifier:
    return EmulatorTokenVerifier(PROJECT, frozenset({"google.com"}))


def test_accepts_an_emulator_token(verifier: EmulatorTokenVerifier) -> None:
    identity = verifier.verify(_emulator_token())
    assert identity.subject == "pa3xICXWrvvNJlNzIcqIHg0dK98C"
    assert identity.email == "alice@example.com"
    assert identity.display_name == "Alice Local"
    assert identity.picture_url is None


def test_only_demo_projects() -> None:
    with pytest.raises(ValueError, match="demo"):
        EmulatorTokenVerifier("popshot-511218", frozenset({"google.com"}))


def test_rejects_signed_tokens(verifier: EmulatorTokenVerifier) -> None:
    # A real (signed) token is never accepted here, so the two verifiers can't be mixed up.
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    signed = jwt.encode(_claims(), key, "RS256", headers={"kid": "k"})
    with pytest.raises(InvalidTokenError):
        verifier.verify(signed)


@pytest.mark.parametrize(
    "header",
    [{"alg": "HS256", "typ": "JWT"}, {"alg": "RS256"}, {"alg": "None"}, {"typ": "JWT"}],
)
def test_rejects_other_algorithms(verifier: EmulatorTokenVerifier, header: dict[str, Any]) -> None:
    with pytest.raises(InvalidTokenError):
        verifier.verify(_emulator_token(header=header))


def test_rejects_a_non_empty_signature(verifier: EmulatorTokenVerifier) -> None:
    with pytest.raises(InvalidTokenError):
        verifier.verify(_emulator_token() + "c2ln")


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "demo-other"},
        {"aud": [PROJECT, "demo-other"]},
        {"iss": "https://securetoken.google.com/demo-other"},
        {"exp": int(time.time()) - 3600},
        {"iat": int(time.time()) + 3600},
        {"auth_time": int(time.time()) + 3600},
        {"exp": _DROP},
        {"sub": _DROP},
        {"sub": ""},
        {"email_verified": False},
        {"email_verified": "true"},
        {"email": _DROP},
        {"firebase": {"sign_in_provider": "password"}},
        {"firebase": _DROP},
    ],
)
def test_checks_claims_like_production(
    verifier: EmulatorTokenVerifier, overrides: dict[str, Any]
) -> None:
    with pytest.raises(InvalidTokenError):
        verifier.verify(_emulator_token(_claims(**overrides)))


@pytest.mark.parametrize("token", ["", "x", "a.b", "a.b.c.", "not-base64.!!.", "." * 3])
def test_rejects_malformed(verifier: EmulatorTokenVerifier, token: str) -> None:
    with pytest.raises(InvalidTokenError):
        verifier.verify(token)


def test_rejects_oversized(verifier: EmulatorTokenVerifier) -> None:
    with pytest.raises(InvalidTokenError):
        verifier.verify(_emulator_token(_claims(name="x" * 9000)))
