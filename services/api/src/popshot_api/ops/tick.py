"""The scheduled job, run every 15 minutes by Cloud Scheduler: play-night reminders,
"your recap is ready" for the people who played (an hour or more after an outing's last
game), deleting groups whose 30 days to be restored have passed, deleting usage activity
older than 13 months, and deleting accounts whose 7 days to change their mind have passed
(their Firebase sign-in first, then their data: migration 0023).

It logs in as its own database user (a member of popshot_jobs), which can only call the
functions migration 0008 grants it. Reminders are marked sent before they go out, so a
crash mid-run can lose a reminder but never sends one twice.

Usage: python -m popshot_api.ops.tick
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol
from uuid import UUID

import structlog
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Engine, Row, text

from popshot_api.accounts import AccountDeleteError, IdentityPlatformDeleter
from popshot_api.db import make_engine
from popshot_api.log_config import configure_logging
from popshot_api.push import Message, PushSender, Subscription
from popshot_api.rating import PlayedMatch
from popshot_api.recap import OUTING_GAP, Outing, outings

log = structlog.get_logger("popshot_api.tick")

Kind = Literal["day", "soon"]
SOON = timedelta(hours=2)
# Recaps: announced once an outing has been over this long, and not after this long.
RECAP_AFTER = timedelta(hours=1)
RECAP_WITHIN = timedelta(hours=6)
# How far back to read games when looking for outings to announce.
RECAP_LOOKBACK = timedelta(hours=24)


class JobSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POPSHOT_", frozen=True)

    jobs_database_url: SecretStr
    database_iam_auth: bool = False
    push_vapid_private_key: SecretStr | None = None
    push_subject: str = Field(default="https://localhost", pattern=r"^https://[^\s]+$")
    # Where deleted accounts' Firebase sign-ins are deleted. Unset (local development): their
    # data is still deleted, and the log says the sign-in wasn't.
    firebase_project_id: str | None = None


@dataclass(frozen=True, slots=True)
class Summary:
    purged_groups: int
    purged_activity_days: int
    reminded_nights: int
    announced_recaps: int
    notifications: int
    deleted_accounts: int = 0
    purged_visit_days: int = 0


def _about(starts_at: datetime, now: datetime) -> str:
    hours = max(1, round((starts_at - now) / timedelta(hours=1)))
    return f"in about {hours} hour{'s' if hours != 1 else ''}"


def _messages(kind: Kind, night: Row[Any], now: datetime) -> tuple[Message, Message]:
    """(for people who said in, for people who haven't answered)."""
    url = f"/groups/{night.group_id}/nights/{night.night_id}"
    tag = f"night-{night.night_id}"
    when = _about(night.starts_at, now)
    going = Message(
        title=f"Meetup {when}",
        body=f"At {night.venue}. You're in."
        if kind == "day"
        else f"At {night.venue}. See you on court!",
        url=url,
        tag=tag,
    )
    unanswered = Message(
        title="Are you in?",
        body=f"Meetup at {night.venue} {when}. Tap to answer.",
        url=url,
        tag=tag,
    )
    return going, unanswered


@dataclass(frozen=True, slots=True)
class DueRecap:
    group_id: UUID
    crew: str
    outing: Outing
    players: frozenset[UUID]  # signed-up players to tell


def due_recaps(rows: Sequence[Row[Any]], now: datetime) -> list[DueRecap]:
    """Outings in `rows` (app_jobs_recent_matches since now - RECAP_LOOKBACK) whose last game
    was RECAP_AFTER to RECAP_WITHIN ago."""
    since = now - RECAP_LOOKBACK
    by_group: dict[UUID, list[Row[Any]]] = {}
    for row in rows:
        by_group.setdefault(row.group_id, []).append(row)
    found: list[DueRecap] = []
    for group_id, group_rows in by_group.items():
        users = {row.match_id: set(row.user_ids) for row in group_rows}
        matches = [PlayedMatch(row.match_id, row.played_at, (), (), ()) for row in group_rows]
        for outing in outings(matches):
            # An outing that might have started before the window would get the wrong key.
            if outing.start - since <= OUTING_GAP:
                continue
            if RECAP_AFTER <= now - outing.end <= RECAP_WITHIN:
                players = frozenset(u for m in outing.matches for u in users[m.id])
                found.append(DueRecap(group_id, group_rows[0].group_name, outing, players))
    return found


def _recap_message(due: DueRecap) -> Message:
    games = len(due.outing.matches)
    return Message(
        title="Your recap is ready",
        # No one's name on the lock screen: the crew and the count only.
        body=f"{due.crew}: {games} game{'s' if games != 1 else ''}. Tap to see the awards.",
        url=f"/groups/{due.group_id}/recaps/{due.outing.key}",
        tag=f"recap-{due.outing.key}",
    )


def announce_recaps(
    engine: Engine, sender: PushSender | None, now: datetime
) -> tuple[int, int, list[str]]:
    """(outings announced, notifications sent, endpoints that are gone)."""
    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT * FROM app_jobs_recent_matches(:since)"),
            {"since": now - RECAP_LOOKBACK},
        ).all()
    announced = sent = 0
    gone: list[str] = []
    for due in due_recaps(rows, now):
        with engine.begin() as conn:
            claimed = conn.execute(
                text("SELECT app_jobs_claim_recap(:g, :k)"),
                {"g": due.group_id, "k": due.outing.key},
            ).scalar_one()
            if not claimed:
                continue
            targets = conn.execute(
                text("SELECT * FROM app_jobs_recap_targets(:g, :users)"),
                {"g": due.group_id, "users": list(due.players)},
            ).all()
        announced += 1
        subs = [Subscription(t.endpoint, t.p256dh, t.auth) for t in targets]
        if sender is not None and subs:
            gone += sender.send(subs, _recap_message(due))
            sent += len(subs)
    return announced, sent, gone


class AccountDeleter(Protocol):
    def delete(self, subject: str) -> None: ...


def delete_accounts(engine: Engine, deleter: AccountDeleter | None) -> int:
    """Accounts whose time to change their mind is up: the sign-in, then the data.

    The sign-in goes first: if that fails, the account waits for the next run with nothing
    lost. Deleting the data then replaces the stored sign-in, so it must come second.
    """
    with engine.begin() as conn:
        due = conn.execute(text("SELECT * FROM app_jobs_due_deletions()")).all()
    deleted = 0
    for account in due:
        if deleter is None:
            log.warning("tick.sign_in_not_deleted", reason="not configured")
        else:
            try:
                deleter.delete(account.auth_subject)
            except AccountDeleteError:
                continue
        with engine.begin() as conn:
            if conn.execute(
                text("SELECT app_jobs_purge_user(:u)"), {"u": account.user_id}
            ).scalar_one():
                deleted += 1
    return deleted


def run(
    engine: Engine,
    sender: PushSender | None,
    now: datetime | None = None,
    deleter: AccountDeleter | None = None,
) -> Summary:
    now = now or datetime.now(UTC)
    deleted_accounts = delete_accounts(engine, deleter)
    with engine.begin() as conn:
        purged = int(conn.execute(text("SELECT app_purge_deleted_groups()")).scalar_one())
        old_activity = int(conn.execute(text("SELECT app_jobs_purge_activity()")).scalar_one())
        old_visits = int(conn.execute(text("SELECT app_jobs_purge_visits()")).scalar_one())

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

    announced, recap_sent, recap_gone = announce_recaps(engine, sender, now)
    sent += recap_sent
    gone += recap_gone

    if gone:
        with engine.begin() as conn:
            for endpoint in gone:
                conn.execute(text("SELECT app_forget_push_endpoint(:e)"), {"e": endpoint})
    summary = Summary(
        purged_groups=purged,
        purged_activity_days=old_activity,
        reminded_nights=reminded,
        announced_recaps=announced,
        notifications=sent,
        deleted_accounts=deleted_accounts,
        purged_visit_days=old_visits,
    )
    log.info(
        "tick.done",
        purged_groups=summary.purged_groups,
        purged_activity_days=summary.purged_activity_days,
        reminded_nights=summary.reminded_nights,
        announced_recaps=summary.announced_recaps,
        notifications=summary.notifications,
        deleted_accounts=summary.deleted_accounts,
        purged_visit_days=summary.purged_visit_days,
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
    deleter = (
        IdentityPlatformDeleter(settings.firebase_project_id)
        if settings.firebase_project_id
        else None
    )
    try:
        run(engine, sender, deleter=deleter)
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
