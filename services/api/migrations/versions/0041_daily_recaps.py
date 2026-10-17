"""Recaps are by day: every crew has a time zone, and stored recap rows move to day keys.

Revision ID: 0041
Revises: 0040
Create Date: 2026-10-17

A recap now covers a crew's games on one local day (popshot_api.recap), so:

- Every crew needs a time zone. Crews without one get America/New_York, the owner's choice,
  which is also the default for new crews whose browser sends none. Leads can change it.
- The job (ops/tick.py) and shared links (routes/shares.py) read the crew's zone:
  app_jobs_recent_matches gains it, and app_public_share_zone gives it for a live link.
- A recap's key was its first game's id, which changed when games were backdated or
  deleted. It's now made from the crew and the date (recap.day_key, repeated below so this
  migration never changes). Shared links, stored words (recap_texts) and sent pushes
  (recap_notifications) move to the key of the day their old first game was on. Two old
  outings on one day become one: the first link and push record are kept, and words are
  kept only once (they're rewritten if the day's facts differ). Keys whose game is gone
  already led nowhere and are left alone.
"""

from collections.abc import Sequence
from uuid import UUID, uuid5

from alembic import op
from sqlalchemy import Connection, text

revision: str = "0041"
down_revision: str | None = "0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"
JOBS_ROLE = "popshot_jobs"
DEFAULT_ZONE = "America/New_York"
# recap.DAY_KEYS and recap.day_key, as they were when this ran.
DAY_KEYS = UUID("85b09a18-97f6-4a54-858f-e87aab46e025")
KEYED = ("recap_texts", "recap_notifications", "recap_shares")


def day_key(group_id: UUID, day: str) -> UUID:
    return uuid5(DAY_KEYS, f"{group_id}/{day}")


RECENT_MATCHES = """
CREATE FUNCTION app_jobs_recent_matches(since timestamptz)
RETURNS TABLE (group_id uuid, group_name text, {zone}match_id uuid, played_at timestamptz,
               user_ids uuid[])
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT m.group_id, g.name, {zone_column}m.id, m.played_at,
           coalesce(array_agg(p.user_id) FILTER (WHERE p.user_id IS NOT NULL), '{{}}')
    FROM public.matches m
    JOIN public.groups g ON g.id = m.group_id AND g.deleted_at IS NULL
    JOIN public.match_players mp ON mp.match_id = m.id
    JOIN public.players p ON p.id = mp.player_id
    WHERE m.played_at >= since
    GROUP BY m.group_id, g.name, {zone_column}m.id, m.played_at
$$;
REVOKE EXECUTE ON FUNCTION app_jobs_recent_matches(timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_jobs_recent_matches(timestamptz) TO {jobs};
"""

UPGRADE = f"""
UPDATE groups SET time_zone = '{DEFAULT_ZONE}' WHERE time_zone IS NULL;
ALTER TABLE groups ALTER COLUMN time_zone SET DEFAULT '{DEFAULT_ZONE}',
                   ALTER COLUMN time_zone SET NOT NULL;

DROP FUNCTION app_jobs_recent_matches(timestamptz);
{RECENT_MATCHES.format(zone="time_zone text, ", zone_column="g.time_zone, ", jobs=JOBS_ROLE)}

-- The time zone of a live link's crew, or nothing.
CREATE FUNCTION app_public_share_zone(token bytea) RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT g.time_zone FROM public.app_public_share(token) s
    JOIN public.groups g ON g.id = s.group_id
$$;
REVOKE EXECUTE ON FUNCTION app_public_share_zone(bytea) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_public_share_zone(bytea) TO {APP_ROLE};
"""

DOWNGRADE = f"""
DROP FUNCTION app_public_share_zone(bytea);
DROP FUNCTION app_jobs_recent_matches(timestamptz);
{RECENT_MATCHES.format(zone="", zone_column="", jobs=JOBS_ROLE)}
ALTER TABLE groups ALTER COLUMN time_zone DROP NOT NULL,
                   ALTER COLUMN time_zone DROP DEFAULT;
"""

# Every key in the three tables, with the crew's zone.
_KEYS = """
SELECT k.group_id, k.outing_key, g.time_zone
FROM (SELECT group_id, outing_key FROM recap_texts
      UNION SELECT group_id, outing_key FROM recap_notifications
      UNION SELECT group_id, outing_key FROM recap_shares) k
JOIN groups g ON g.id = k.group_id
"""


def _move(conn: Connection, moves: dict[tuple[UUID, UUID], UUID]) -> None:
    """Moves each (crew, old key) to its new key in the three tables."""
    for (group_id, old), new in moves.items():
        keys = {"g": group_id, "old": old, "new": new}
        conn.execute(
            text(
                "UPDATE recap_shares SET outing_key = :new "
                "WHERE group_id = :g AND outing_key = :old"
            ),
            keys,
        )
        conn.execute(
            text(
                "INSERT INTO recap_notifications (group_id, outing_key, notified_at) "
                "SELECT group_id, :new, notified_at FROM recap_notifications "
                "WHERE group_id = :g AND outing_key = :old ON CONFLICT DO NOTHING"
            ),
            keys,
        )
        conn.execute(
            text(
                "UPDATE recap_texts SET outing_key = :new "
                "WHERE group_id = :g AND outing_key = :old AND NOT EXISTS "
                "(SELECT 1 FROM recap_texts t WHERE t.group_id = :g AND t.outing_key = :new)"
            ),
            keys,
        )
        for table in ("recap_notifications", "recap_texts"):
            conn.execute(
                text(f"DELETE FROM {table} WHERE group_id = :g AND outing_key = :old"),
                keys,
            )


def _to_days(conn: Connection) -> dict[tuple[UUID, UUID], UUID]:
    """Old key (a game's id) → the key of that game's day in the crew's zone."""
    rows = conn.execute(
        text(
            f"SELECT k.group_id, k.outing_key, "
            f"((m.played_at AT TIME ZONE k.time_zone)::date)::text AS day "
            f"FROM ({_KEYS}) k JOIN matches m ON m.id = k.outing_key AND m.group_id = k.group_id"
        )
    )
    return {(r.group_id, r.outing_key): day_key(r.group_id, r.day) for r in rows}


def _to_first_games(conn: Connection) -> dict[tuple[UUID, UUID], UUID]:
    """Day key → that day's first game, as keys were before."""
    rows = conn.execute(
        text(
            f"SELECT DISTINCT ON (m.group_id, day) m.group_id, m.id, day "
            f"FROM (SELECT DISTINCT group_id, time_zone FROM ({_KEYS}) k) c "
            f"JOIN matches m ON m.group_id = c.group_id, "
            f"LATERAL (SELECT ((m.played_at AT TIME ZONE c.time_zone)::date)::text AS day) d "
            f"ORDER BY m.group_id, day, m.played_at, m.id::text"
        )
    )
    return {(r.group_id, day_key(r.group_id, r.day)): r.id for r in rows}


def _rekey(forward: bool) -> None:
    conn = op.get_bind()
    # Row-level security is forced, and nothing else lets the owner change these rows.
    for table in KEYED:
        op.execute(
            f"CREATE POLICY rekey_0041 ON {table} FOR ALL TO CURRENT_USER "
            "USING (true) WITH CHECK (true)"
        )
    op.execute("CREATE POLICY rekey_0041 ON matches FOR SELECT TO CURRENT_USER USING (true)")
    _move(conn, _to_days(conn) if forward else _to_first_games(conn))
    for table in (*KEYED, "matches"):
        op.execute(f"DROP POLICY rekey_0041 ON {table}")


def upgrade() -> None:
    op.execute(UPGRADE)
    _rekey(forward=True)


def downgrade() -> None:
    _rekey(forward=False)
    op.execute(DOWNGRADE)
