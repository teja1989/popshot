"""Push notifications: where to send them, and what each person wants.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-11

push_subscriptions holds one row per browser or installed app that turned notifications on:
the push service's endpoint URL and the browser's public keys. notification_settings holds
the categories someone has turned off. Both are private to their owner (forced RLS), like
user_focus.

Three SECURITY DEFINER functions cover what RLS can't:
- app_save_push_subscription: a device belongs to whoever turned notifications on last, so
  saving it removes the same endpoint from anyone else (someone signing in on a friend's
  phone mustn't leave the friend getting their notifications).
- app_push_targets: the devices to notify for some people, but only people the caller
  shares an active group with, never the caller, and not anyone who turned that category
  off. So a request can only notify its own crew.
- app_forget_push_endpoint: drops an endpoint the push service says is gone. Endpoints are
  long random capability URLs, so knowing one is the only way to drop it.

The API only accepts endpoints on the browser push services' hosts (popshot_api.push); the
database insists on https.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"
CATEGORIES = "'games', 'play_nights', 'tab', 'milestones'"
FUNCTIONS = [
    "app_save_push_subscription(text, text, text)",
    "app_push_targets(uuid[], text)",
    "app_forget_push_endpoint(text)",
]

UPGRADE = f"""
CREATE TABLE push_subscriptions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    endpoint text NOT NULL UNIQUE
        CHECK (endpoint ~ '^https://' AND char_length(endpoint) <= 1024),
    -- Base64url: a 65-byte P-256 public key and a 16-byte secret.
    p256dh text NOT NULL CHECK (p256dh ~ '^[A-Za-z0-9_-]{{86,88}}={{0,2}}$'),
    auth text NOT NULL CHECK (auth ~ '^[A-Za-z0-9_-]{{21,24}}={{0,2}}$'),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX push_subscriptions_user_idx ON push_subscriptions (user_id);

CREATE TABLE notification_settings (
    user_id uuid PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    muted text[] NOT NULL DEFAULT '{{}}'
        CHECK (muted <@ ARRAY[{CATEGORIES}]::text[]),
    updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE push_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE push_subscriptions FORCE ROW LEVEL SECURITY;
ALTER TABLE notification_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_settings FORCE ROW LEVEL SECURITY;
REVOKE ALL ON push_subscriptions FROM PUBLIC;
REVOKE ALL ON notification_settings FROM PUBLIC;

CREATE POLICY app_own ON push_subscriptions FOR ALL TO {APP_ROLE}
    USING (user_id = app_current_user_id())
    WITH CHECK (user_id = app_current_user_id());
CREATE POLICY app_own ON notification_settings FOR ALL TO {APP_ROLE}
    USING (user_id = app_current_user_id())
    WITH CHECK (user_id = app_current_user_id());

-- For the functions below.
CREATE POLICY owner_definer_all ON push_subscriptions FOR ALL TO CURRENT_USER
    USING (true) WITH CHECK (true);
CREATE POLICY owner_definer_read ON notification_settings FOR SELECT TO CURRENT_USER
    USING (true);

GRANT SELECT, DELETE ON push_subscriptions TO {APP_ROLE};
GRANT SELECT, INSERT, UPDATE (muted, updated_at) ON notification_settings TO {APP_ROLE};

CREATE FUNCTION app_save_push_subscription(new_endpoint text, new_p256dh text, new_auth text)
RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no user context' USING ERRCODE = 'insufficient_privilege';
    END IF;
    INSERT INTO public.push_subscriptions (user_id, endpoint, p256dh, auth)
    VALUES (me, new_endpoint, new_p256dh, new_auth)
    ON CONFLICT (endpoint) DO UPDATE
        SET user_id = me, p256dh = excluded.p256dh, auth = excluded.auth,
            created_at = now();
END;
$$;

CREATE FUNCTION app_push_targets(targets uuid[], category text)
RETURNS TABLE (endpoint text, p256dh text, auth text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT s.endpoint, s.p256dh, s.auth
    FROM public.push_subscriptions s
    LEFT JOIN public.notification_settings n ON n.user_id = s.user_id
    WHERE s.user_id = ANY(targets)
      AND s.user_id <> public.app_current_user_id()
      AND public.app_can_see_user(s.user_id)
      AND NOT (category = ANY(coalesce(n.muted, '{{}}')))
$$;

CREATE FUNCTION app_forget_push_endpoint(gone text) RETURNS void
LANGUAGE sql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    DELETE FROM public.push_subscriptions WHERE endpoint = gone
$$;
"""


def upgrade() -> None:
    op.execute(UPGRADE)
    for signature in FUNCTIONS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP_ROLE}")


def downgrade() -> None:
    for signature in FUNCTIONS:
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("DROP TABLE notification_settings")
    op.execute("DROP TABLE push_subscriptions")
