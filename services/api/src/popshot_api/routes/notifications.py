"""Push notifications: turning them on per device, choosing what you get, and sending.

notify() is what other routes call. It looks up the devices to notify inside the request's
transaction (row-level security and app_push_targets decide who may be notified), and sends
after the response, so a slow push service never holds up a request.
"""

from collections.abc import Sequence
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from popshot_api.db import CurrentUserSession
from popshot_api.push import Message, PushSender, Subscription, is_push_endpoint

router = APIRouter(prefix="/v1")

Category = Literal["games", "play_nights", "recaps", "tab", "milestones"]
# The categories people can turn off, in the order the You page lists them. Others are added
# here as the features that send them ship.
OFFERED: tuple[Category, ...] = ("play_nights", "recaps", "games")

Base64Url = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]+={0,2}$", max_length=128)]


class SubscriptionKeys(BaseModel):
    model_config = ConfigDict(extra="ignore")

    p256dh: Base64Url
    auth: Base64Url


class NewSubscription(BaseModel):
    # Browsers add fields such as expirationTime; only these are kept.
    model_config = ConfigDict(extra="ignore")

    endpoint: Annotated[str, Field(max_length=1024)]
    keys: SubscriptionKeys


class Endpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint: Annotated[str, Field(max_length=1024)]


class PushConfig(BaseModel):
    # Null when push isn't set up on this server; the app then hides notification settings.
    public_key: str | None


class NotificationSettings(BaseModel):
    categories: list[Category]
    muted: list[Category]
    devices: int


class MutedBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    muted: list[Category]


def _sender(request: Request) -> PushSender | None:
    sender: PushSender | None = request.app.state.push_sender
    return sender


def _deliver(
    sender: PushSender, engine: Engine, subs: list[Subscription], message: Message
) -> None:
    gone = sender.send(subs, message)
    if gone:
        with engine.begin() as conn:
            for endpoint in gone:
                conn.execute(text("SELECT app_forget_push_endpoint(:e)"), {"e": endpoint})


class Notifier:
    """Sends notifications for a request. Get one with `CurrentNotifier`."""

    def __init__(self, request: Request, background: BackgroundTasks) -> None:
        self._sender = _sender(request)
        self._engine: Engine = request.app.state.engine
        self._background = background

    def notify(
        self, session: Session, users: Sequence[UUID], category: Category, message: Message
    ) -> None:
        """Queue `message` for `users`' devices: only people who share an active group with
        the caller, never the caller, and not anyone who turned `category` off."""
        if self._sender is None or not users:
            return
        rows = session.execute(
            text("SELECT * FROM app_push_targets(CAST(:users AS uuid[]), :category)"),
            {"users": [str(u) for u in users], "category": category},
        ).all()
        self._queue([Subscription(r.endpoint, r.p256dh, r.auth) for r in rows], message)

    def notify_own_devices(self, session: Session, me: UUID, message: Message) -> int:
        rows = session.execute(
            text("SELECT endpoint, p256dh, auth FROM push_subscriptions WHERE user_id = :me"),
            {"me": me},
        ).all()
        self._queue([Subscription(r.endpoint, r.p256dh, r.auth) for r in rows], message)
        return len(rows)

    @property
    def enabled(self) -> bool:
        return self._sender is not None

    def _queue(self, subs: list[Subscription], message: Message) -> None:
        if self._sender is not None and subs:
            self._background.add_task(_deliver, self._sender, self._engine, subs, message)


CurrentNotifier = Annotated[Notifier, Depends(Notifier)]


@router.get("/push/config")
def push_config(request: Request) -> PushConfig:
    sender = _sender(request)
    return PushConfig(public_key=sender.public_key if sender else None)


@router.post("/me/push-subscriptions", status_code=status.HTTP_204_NO_CONTENT)
def save_subscription(body: NewSubscription, user: CurrentUserSession) -> Response:
    """Turn notifications on for this device (or refresh its keys)."""
    if not is_push_endpoint(body.endpoint):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="This browser's push service isn't supported.",
        )
    user.session.execute(
        text("SELECT app_save_push_subscription(:endpoint, :p256dh, :auth)"),
        {"endpoint": body.endpoint, "p256dh": body.keys.p256dh, "auth": body.keys.auth},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/me/push-subscriptions/remove", status_code=status.HTTP_204_NO_CONTENT)
def remove_subscription(body: Endpoint, user: CurrentUserSession) -> Response:
    """Turn notifications off for this device. Only ever removes your own."""
    user.session.execute(
        text("DELETE FROM push_subscriptions WHERE endpoint = :endpoint AND user_id = :me"),
        {"endpoint": body.endpoint, "me": user.user_id},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _settings(session: Session, me: UUID) -> NotificationSettings:
    muted = session.execute(
        text("SELECT muted FROM notification_settings WHERE user_id = :me"), {"me": me}
    ).scalar_one_or_none()
    devices = session.execute(
        text("SELECT count(*) FROM push_subscriptions WHERE user_id = :me"), {"me": me}
    ).scalar_one()
    offered = list(OFFERED)
    return NotificationSettings(
        categories=offered, muted=[c for c in offered if c in (muted or [])], devices=devices
    )


@router.get("/me/notifications")
def get_notifications(user: CurrentUserSession) -> NotificationSettings:
    return _settings(user.session, user.user_id)


@router.put("/me/notifications")
def set_notifications(body: MutedBody, user: CurrentUserSession) -> NotificationSettings:
    user.session.execute(
        text(
            """
            INSERT INTO notification_settings (user_id, muted) VALUES (:me, :muted)
            ON CONFLICT (user_id) DO UPDATE SET muted = excluded.muted, updated_at = now()
            """
        ),
        {"me": user.user_id, "muted": sorted(set(body.muted))},
    )
    return _settings(user.session, user.user_id)


@router.post("/me/push-test", status_code=status.HTTP_202_ACCEPTED)
def push_test(notifier: CurrentNotifier, user: CurrentUserSession) -> Response:
    """Send "notifications are on" to your own devices."""
    if not notifier.enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Notifications aren't set up yet.")
    message = Message(
        title="Notifications are on",
        body="You'll hear from your crew here.",
        url="/you",
        tag="test",
    )
    if notifier.notify_own_devices(user.session, user.user_id, message) == 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Turn on notifications on this device first."
        )
    return Response(status_code=status.HTTP_202_ACCEPTED)
