"""GoogleIdTokenVerifier against tokens signed with a throwaway key. No network."""

import base64
import hashlib
import hmac
import json
import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

from popshot_api.auth.google import GoogleIdTokenVerifier
from popshot_api.auth.verifier import InvalidTokenError, KeyFetchError

PROJECT = "popshot-test"
KID = "key-1"


def _new_key() -> RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


SIGNING_KEY = _new_key()
OTHER_KEY = _new_key()


class StaticKeys:
    def __init__(self, keys: dict[str, RSAPublicKey]) -> None:
        self.keys = keys

    def key_for(self, kid: str) -> RSAPublicKey:
        try:
            return self.keys[kid]
        except KeyError:
            raise InvalidTokenError("unknown signing key") from None


class DownKeys:
    def key_for(self, kid: str) -> RSAPublicKey:
        raise KeyFetchError("down")


def _claims(**overrides: Any) -> dict[str, Any]:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": f"https://securetoken.google.com/{PROJECT}",
        "aud": PROJECT,
        "sub": "user-123",
        "iat": now - 10,
        "exp": now + 3600,
        "auth_time": now - 60,
        "email": "player@example.com",
        "email_verified": True,
        "name": "Player One",
        "picture": "https://example.com/p.png",
        "firebase": {"sign_in_provider": "google.com", "identities": {}},
    }
    claims.update(overrides)
    return {k: v for k, v in claims.items() if v is not _DROP}


_DROP = object()


def _token(
    claims: dict[str, Any] | None = None,
    key: RSAPrivateKey = SIGNING_KEY,
    kid: str | None = KID,
    alg: str = "RS256",
) -> str:
    headers = {"kid": kid} if kid is not None else {}
    return jwt.encode(claims if claims is not None else _claims(), key, alg, headers=headers)


@pytest.fixture
def verifier() -> GoogleIdTokenVerifier:
    return GoogleIdTokenVerifier(
        PROJECT,
        allowed_providers=frozenset({"google.com"}),
        keys=StaticKeys({KID: SIGNING_KEY.public_key()}),
    )


def _rejects(verifier: GoogleIdTokenVerifier, token: str) -> str:
    with pytest.raises(InvalidTokenError) as exc_info:
        verifier.verify(token)
    return exc_info.value.reason


def test_accepts_a_valid_token(verifier: GoogleIdTokenVerifier) -> None:
    identity = verifier.verify(_token())
    assert identity.subject == "user-123"
    assert identity.email == "player@example.com"
    assert identity.display_name == "Player One"
    assert identity.picture_url == "https://example.com/p.png"


def test_optional_profile_fields(verifier: GoogleIdTokenVerifier) -> None:
    identity = verifier.verify(_token(_claims(name=_DROP, picture="")))
    assert identity.display_name is None
    assert identity.picture_url is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "someone-elses-project"},
        {"aud": [PROJECT, "other"]},
        {"iss": "https://securetoken.google.com/other-project"},
        {"iss": "https://accounts.google.com"},
        {"exp": int(time.time()) - 120},
        {"iat": int(time.time()) + 600},
        {"auth_time": int(time.time()) + 600},
        {"auth_time": "yesterday"},
        {"sub": ""},
        {"sub": "x" * 129},
        {"sub": 123},
        {"email_verified": False},
        {"email_verified": "true"},
        {"email_verified": _DROP},
        {"email": _DROP},
        {"email": ""},
        {"firebase": {"sign_in_provider": "password"}},
        {"firebase": {"sign_in_provider": "anonymous"}},
        {"firebase": _DROP},
        {"exp": _DROP},
        {"iat": _DROP},
        {"auth_time": _DROP},
        {"sub": _DROP},
    ],
    ids=lambda o: ",".join(f"{k}={'<dropped>' if v is _DROP else v}" for k, v in o.items()),
)
def test_rejects_bad_claims(verifier: GoogleIdTokenVerifier, overrides: dict[str, Any]) -> None:
    _rejects(verifier, _token(_claims(**overrides)))


def test_rejects_token_signed_by_another_key(verifier: GoogleIdTokenVerifier) -> None:
    _rejects(verifier, _token(key=OTHER_KEY))


def test_rejects_unknown_or_missing_kid(verifier: GoogleIdTokenVerifier) -> None:
    assert _rejects(verifier, _token(kid="key-2")) == "unknown signing key"
    assert _rejects(verifier, _token(kid=None)) == "missing key id"


def test_rejects_alg_none(verifier: GoogleIdTokenVerifier) -> None:
    header = jwt.utils.base64url_encode(b'{"alg":"none","kid":"key-1"}').decode()
    body = jwt.utils.base64url_encode(json.dumps(_claims()).encode()).decode()
    unsigned = f"{header}.{body}."
    assert _rejects(verifier, unsigned) == "unexpected algorithm"


def test_rejects_hs256_with_public_key_as_secret(verifier: GoogleIdTokenVerifier) -> None:
    """Classic algorithm confusion: HMAC 'signed' with the RSA public key."""
    public_pem = SIGNING_KEY.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","kid":"key-1","typ":"JWT"}').rstrip(b"=")
    body = base64.urlsafe_b64encode(jwt.utils.force_bytes('{"sub":"x"}')).rstrip(b"=")
    sig = hmac.new(public_pem, header + b"." + body, hashlib.sha256).digest()
    forged = b".".join([header, body, base64.urlsafe_b64encode(sig).rstrip(b"=")]).decode()
    assert _rejects(verifier, forged) == "unexpected algorithm"


def test_rejects_tampered_payload(verifier: GoogleIdTokenVerifier) -> None:
    header, _, signature = _token().split(".")
    evil = jwt.utils.base64url_encode(
        jwt.utils.force_bytes('{"sub":"admin","aud":"popshot-test"}')
    ).decode()
    _rejects(verifier, f"{header}.{evil}.{signature}")


@pytest.mark.parametrize("garbage", ["", "not-a-jwt", "a.b.c", "x" * 9000])
def test_rejects_garbage(verifier: GoogleIdTokenVerifier, garbage: str) -> None:
    _rejects(verifier, garbage)


def test_key_outage_surfaces_as_key_fetch_error() -> None:
    verifier = GoogleIdTokenVerifier(PROJECT, frozenset({"google.com"}), keys=DownKeys())
    with pytest.raises(KeyFetchError):
        verifier.verify(_token())


def test_extra_provider_can_be_allowed() -> None:
    verifier = GoogleIdTokenVerifier(
        PROJECT,
        allowed_providers=frozenset({"google.com", "apple.com"}),
        keys=StaticKeys({KID: SIGNING_KEY.public_key()}),
    )
    token = _token(_claims(firebase={"sign_in_provider": "apple.com"}))
    assert verifier.verify(token).subject == "user-123"


def test_requires_at_least_one_provider() -> None:
    with pytest.raises(ValueError, match="provider"):
        GoogleIdTokenVerifier(PROJECT, frozenset(), keys=DownKeys())
