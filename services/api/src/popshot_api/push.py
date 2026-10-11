"""Web Push: sending notifications to browsers and installed apps.

A subscription is a URL on the browser maker's push service plus the browser's keys. The
server POSTs an encrypted message to that URL, signed with our VAPID key (RFC 8292).

Because the server makes requests to URLs that clients give it, only the known push
services' hosts are accepted, both when a subscription is saved and when sending, and
redirects are refused. Messages carry a title, a line of text and a link inside the app;
never scores or amounts, since they show on lock screens.
"""

import base64
import json
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlsplit

import requests
import structlog
from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid02
from pywebpush import WebPushException, webpush

log = structlog.get_logger("popshot_api.push")

# Hosts of the browsers' push services: Chrome and Android (FCM), Firefox, Safari (Apple),
# Edge (Windows). Exact hosts, or any subdomain of the suffixes.
PUSH_HOSTS = frozenset({"fcm.googleapis.com", "updates.push.services.mozilla.com"})
PUSH_HOST_SUFFIXES = (".push.apple.com", ".notify.windows.com")

# How long a push service keeps trying to deliver while the device is offline.
TTL_SECONDS = 12 * 60 * 60
TIMEOUT_SECONDS = 5
# Same cap as the database.
MAX_ENDPOINT = 1024


def is_push_endpoint(url: str) -> bool:
    """True for an https URL on a known push service, with no port, user or fragment."""
    if len(url) > MAX_ENDPOINT:
        return False
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return False
    host = (parts.hostname or "").lower()
    return (
        parts.scheme == "https"
        and port is None
        and parts.username is None
        and parts.password is None
        and not parts.fragment
        and (host in PUSH_HOSTS or host.endswith(PUSH_HOST_SUFFIXES))
    )


@dataclass(frozen=True, slots=True)
class Subscription:
    endpoint: str
    p256dh: str
    auth: str


@dataclass(frozen=True, slots=True)
class Message:
    title: str
    body: str
    # A path inside the app, opened when the notification is tapped.
    url: str = "/"
    # Notifications with the same tag replace each other on the device.
    tag: str | None = None

    def payload(self) -> str:
        return json.dumps(
            {"title": self.title, "body": self.body, "url": self.url, "tag": self.tag},
            separators=(",", ":"),
        )


class PushSender:
    """Signs and sends messages. Built once at startup from the VAPID private key (PEM)."""

    def __init__(self, private_key_pem: str, subject: str) -> None:
        self._vapid = Vapid02.from_pem(private_key_pem.encode("ascii"))
        self._subject = subject
        raw = self._vapid.public_key.public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        # What browsers need to subscribe (applicationServerKey).
        self.public_key = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    def send(self, subscriptions: Iterable[Subscription], message: Message) -> list[str]:
        """Send to each subscription. Returns the endpoints the push service says are gone."""
        gone: list[str] = []
        session = requests.Session()
        session.max_redirects = 0
        for sub in subscriptions:
            if not is_push_endpoint(sub.endpoint):
                log.warning("push.refused_endpoint")
                continue
            try:
                webpush(
                    {"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
                    data=message.payload(),
                    vapid_private_key=self._vapid,
                    # A fresh dict each time: webpush fills in aud and exp.
                    vapid_claims={"sub": self._subject},
                    ttl=TTL_SECONDS,
                    timeout=TIMEOUT_SECONDS,
                    requests_session=session,
                )
            except WebPushException as error:
                status = error.response.status_code if error.response is not None else None
                if status in (404, 410):  # unsubscribed or expired
                    gone.append(sub.endpoint)
                else:
                    log.warning("push.failed", status=status)
            except requests.RequestException as error:
                log.warning("push.failed", error=type(error).__name__)
        return gone
