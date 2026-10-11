"""The scheduled job, run every 15 minutes by Cloud Scheduler: play-night reminders, and
deleting groups whose 30 days to be restored have passed.

It logs in as its own database user (a member of popshot_jobs), which can only call the
functions migration 0008 grants it. Reminders are marked sent before they go out, so a
crash mid-run can lose a reminder but never sends one twice.

Usage: python -m popshot_api.ops.tick
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import structlog
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Engine, Row, text

from popshot_api.db import make_engine
from popshot_api.log_config import configure_logging
from popshot_api.push import Message, PushSender, Subscription

log = structlog.get_logger("popshot_api.tick")

Kind = Literal["day", "soon"]
SOON = timedelta(hours=2)


class JobSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POPSHOT_", frozen=True)

    jobs_database_url: SecretStr
    database_iam_auth: bool = False
    push_vapid_private_key: SecretStr | None = None
    push_subject: str = Field(default="https://localhost", pattern=r"^https://[^\s]+$")


@dataclass(frozen=True, slots=True)
class Summary:
    purged_groups: int
    reminded_nights: int
    notifications: int


def _about(starts_at: datetime, now: datetime) -> str:
    hours = max(1, round((starts_at - now) / timedelta(hours=1)))
    return f"in about {hours} hour{'s' if hours != 1 else ''}"


def _messages(kind: Kind, night: Row[Any], now: datetime) -> tuple[Message, Message]:
    """(for people who said in, for people who haven't answered)."""
    url = f"/groups/{night.group_id}/nights/{night.night_id}"
    tag = f"night-{night.night_id}"
    when = _about(night.starts_at, now)
    going = Message(
        title=f"Play night {when}",
        body=f"At {night.venue}. You're in."
        if kind == "day"
        else f"At {night.venue}. See you on court!",
        url=url,
        tag=tag,
    )
    unanswered = Message(
        title="Are you in?",
        body=f"Play night at {night.venue} {when}. Tap to answer.",
        url=url,
        tag=tag,
    )
    return going, unanswered


def run(engine: Engine, sender: PushSender | None, now: datetime | None = None) -> Summary:
    now = now or datetime.now(UTC)
    with engine.begin() as conn:
        purged = int(conn.execute(text("SELECT app_purge_deleted_groups()")).scalar_one())

    reminded = 0
    sent = 0
    gone: list[str] = []
    # 'soon' first: a night planned at short notice gets one reminder, not two.
    for kind in ("soon", "day"):
        with engine.begin() as conn:
            due = conn.execute(
                text("SELECT * FROM app_jobs_due_reminders(:kind)"), {"kind": kind}
            ).all()
        for night in due:
            with engine.begin() as conn:
                conn.execute(
                    text("SELECT app_jobs_mark_reminded(:night, :kind)"),
                    {"night": night.night_id, "kind": kind},
                )
                if kind == "day" and night.starts_at <= now + SOON:
                    # Too close for "the day before": the 2-hour reminder covers it.
                    continue
                targets = conn.execute(
                    text("SELECT * FROM app_jobs_reminder_targets(:night, :kind)"),
                    {"night": night.night_id, "kind": kind},
                ).all()
            reminded += 1
            if sender is None or not targets:
                continue
            going, unanswered = _messages(kind, night, now)
            for message, answered in ((going, True), (unanswered, False)):
                subs = [
                    Subscription(t.endpoint, t.p256dh, t.auth)
                    for t in targets
                    if t.answered is answered
                ]
                if subs:
                    gone += sender.send(subs, message)
                    sent += len(subs)

    if gone:
        with engine.begin() as conn:
            for endpoint in gone:
                conn.execute(text("SELECT app_forget_push_endpoint(:e)"), {"e": endpoint})
    summary = Summary(purged_groups=purged, reminded_nights=reminded, notifications=sent)
    log.info(
        "tick.done",
        purged_groups=summary.purged_groups,
        reminded_nights=summary.reminded_nights,
        notifications=summary.notifications,
    )
    return summary


def main() -> int:
    settings = JobSettings()  # from the environment
    configure_logging("INFO")
    engine = make_engine(
        settings.jobs_database_url.get_secret_value(), iam_auth=settings.database_iam_auth
    )
    sender = (
        PushSender(settings.push_vapid_private_key.get_secret_value(), settings.push_subject)
        if settings.push_vapid_private_key
        else None
    )
    try:
        run(engine, sender)
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
