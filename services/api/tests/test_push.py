import base64
import json
from typing import Any

import pytest
import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import WebPushException

from popshot_api import push
from popshot_api.push import Message, PushSender, Subscription, is_push_endpoint


def pem_key() -> str:
    key = ec.generate_private_key(ec.SECP256R1())
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()


def browser_keys() -> tuple[str, str]:
    """A browser's p256dh (65-byte P-256 point) and auth secret, base64url."""
    point = (
        ec.generate_private_key(ec.SECP256R1())
        .public_key()
        .public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    )
    return _b64(point), _b64(b"0123456789abcdef")


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@pytest.mark.parametrize(
    "url",
    [
        "https://fcm.googleapis.com/fcm/send/abc",
        "https://updates.push.services.mozilla.com/wpush/v2/abc",
        "https://web.push.apple.com/QGx",
        "https://wns2-par02p.notify.windows.com/w/?token=x",
    ],
)
def test_accepts_push_services(url: str) -> None:
    assert is_push_endpoint(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://fcm.googleapis.com/fcm/send/abc",  # not https
        "https://fcm.googleapis.com:8443/x",  # a port
        "https://user@fcm.googleapis.com/x",  # credentials
        "https://evil.example.com/fcm.googleapis.com",
        "https://fcm.googleapis.com.evil.example/x",
        "https://notpush.apple.com/x",  # not a subdomain of push.apple.com
        "https://169.254.169.254/computeMetadata/v1/",
        "https://localhost/x",
        "https://fcm.googleapis.com/x#frag",
        "https://[::1/x",  # malformed
        "https://fcm.googleapis.com/" + "a" * 1100,
        "",
    ],
)
def test_refuses_everything_else(url: str) -> None:
    assert not is_push_endpoint(url)


def test_public_key_matches_the_private_key() -> None:
    sender = PushSender(pem_key(), "https://example.com")
    raw = base64.urlsafe_b64decode(sender.public_key + "=")
    # An uncompressed P-256 point.
    assert len(raw) == 65
    assert raw[0] == 4


class FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.text = ""
        self.headers: dict[str, str] = {}


def test_send_reports_gone_endpoints_and_skips_refused_ones(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, Any]] = []

    def fake_webpush(info: dict[str, Any], **kwargs: Any) -> None:
        sent.append({"endpoint": info["endpoint"], **kwargs})
        if info["endpoint"].endswith("/gone"):
            raise WebPushException("gone", response=FakeResponse(410))
        if info["endpoint"].endswith("/flaky"):
            raise WebPushException("busy", response=FakeResponse(503))

    monkeypatch.setattr(push, "webpush", fake_webpush)
    p256dh, auth = browser_keys()
    sender = PushSender(pem_key(), "https://example.com")
    gone = sender.send(
        [
            Subscription("https://fcm.googleapis.com/fcm/send/ok", p256dh, auth),
            Subscription("https://fcm.googleapis.com/fcm/send/gone", p256dh, auth),
            Subscription("https://fcm.googleapis.com/fcm/send/flaky", p256dh, auth),
            Subscription("https://evil.example.com/x", p256dh, auth),
        ],
        Message(title="Hi", body="There", url="/games", tag="t"),
    )
    assert gone == ["https://fcm.googleapis.com/fcm/send/gone"]
    assert [s["endpoint"].rsplit("/", 1)[1] for s in sent] == ["ok", "gone", "flaky"]
    first = sent[0]
    assert json.loads(first["data"]) == {
        "title": "Hi",
        "body": "There",
        "url": "/games",
        "tag": "t",
    }
    assert first["vapid_claims"] == {"sub": "https://example.com"}
    assert first["requests_session"].max_redirects == 0
    # Each call gets its own claims dict (webpush adds aud and exp to it).
    assert sent[0]["vapid_claims"] is not sent[1]["vapid_claims"]


def test_send_really_encrypts(monkeypatch: pytest.MonkeyPatch) -> None:
    """End to end through pywebpush, with the HTTP request captured instead of sent."""
    captured: dict[str, Any] = {}

    class Session:
        max_redirects = 0

        def post(
            self, url: str, data: bytes, headers: dict[str, str], timeout: float
        ) -> FakeResponse:
            captured.update(url=url, data=data, headers=headers)
            return FakeResponse(201)

    monkeypatch.setattr(requests, "Session", Session)
    p256dh, auth = browser_keys()
    sender = PushSender(pem_key(), "https://example.com")
    assert (
        sender.send(
            [Subscription("https://fcm.googleapis.com/fcm/send/x", p256dh, auth)], Message("A", "B")
        )
        == []
    )
    assert captured["url"] == "https://fcm.googleapis.com/fcm/send/x"
    assert captured["headers"]["content-encoding"] == "aes128gcm"
    assert captured["headers"]["authorization"].startswith("vapid t=")
    # Encrypted: the JSON isn't readable in the body.
    assert b'"title"' not in captured["data"]
