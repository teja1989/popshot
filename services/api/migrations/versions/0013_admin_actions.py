"""Support actions: an admin can make an active member a crew's lead, with a logged reason.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-11

admin_actions is the record of every change an admin makes: who, what, to which crew and
person, why (a required reason) and what it was before. Only the action functions write it,
in the same transaction as the change, so a change can't happen without its record. No
role can write it directly; popshot_admin reads a crew's actions through
app_admin_group_actions.

app_admin_make_lead mirrors a lead handing over (app_hand_over_lead, migration 0005): the
new lead must be an active member, and whoever was lead becomes a co-lead, so the crew still
has exactly one lead. It's for crews whose lead has gone quiet or lost their account.

Like the other admin functions, these are granted to popshot_admin only, and the admin
service checks who's asking (allowlist, and a sign-in within 15 minutes for changes).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ADMIN_ROLE = "popshot_admin"
FUNCTIONS = [
    "app_admin_make_lead(uuid, uuid, text)",
    "app_admin_group_actions(uuid)",
]

UPGRADE = """
CREATE TABLE admin_actions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    admin_user_id uuid NOT NULL REFERENCES users (id),
    action text NOT NULL CHECK (action ~ '^[a-z][a-z_.]{0,63}$'),
    group_id uuid REFERENCES groups (id) ON DELETE SET NULL,
    target_user_id uuid REFERENCES users (id) ON DELETE SET NULL,
    reason text NOT NULL CHECK (char_length(btrim(reason)) BETWEEN 10 AND 500),
    details jsonb NOT NULL DEFAULT '{}' CHECK (pg_column_size(details) <= 4096),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX admin_actions_group_idx ON admin_actions (group_id, created_at DESC);

ALTER TABLE admin_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_actions FORCE ROW LEVEL SECURITY;
REVOKE ALL ON admin_actions FROM PUBLIC;
-- Written and read only by the functions below (and the owner, for review).
CREATE POLICY owner_definer_insert ON admin_actions FOR INSERT TO CURRENT_USER
    WITH CHECK (true);
CREATE POLICY owner_definer_read ON admin_actions FOR SELECT TO CURRENT_USER USING (true);

-- 'done' with the previous lead (if there was one), or why not: 'no_crew' (missing or
-- deleted), 'not_member' (not an active member), 'already_lead'.
CREATE FUNCTION app_admin_make_lead(target_group uuid, new_lead uuid, why text)
RETURNS TABLE (outcome text, previous_lead uuid)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
    previous uuid;
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no signed-in user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    -- One change to a crew's leadership at a time.
    PERFORM 1 FROM public.groups g
    WHERE g.id = target_group AND g.deleted_at IS NULL FOR UPDATE;
    IF NOT FOUND THEN
        RETURN QUERY SELECT 'no_crew'::text, NULL::uuid;
        RETURN;
    END IF;
    PERFORM 1 FROM public.group_members m
    WHERE m.group_id = target_group AND m.user_id = new_lead AND m.status = 'active';
    IF NOT FOUND THEN
        RETURN QUERY SELECT 'not_member'::text, NULL::uuid;
        RETURN;
    END IF;
    SELECT m.user_id INTO previous FROM public.group_members m
    WHERE m.group_id = target_group AND m.role = 'lead' AND m.status = 'active'
    ORDER BY m.created_at LIMIT 1;
    IF previous = new_lead THEN
        RETURN QUERY SELECT 'already_lead'::text, previous;
        RETURN;
    END IF;
    UPDATE public.group_members m SET role = 'co_lead', updated_at = now()
    WHERE m.group_id = target_group AND m.role = 'lead' AND m.user_id <> new_lead;
    UPDATE public.group_members m SET role = 'lead', updated_at = now()
    WHERE m.group_id = target_group AND m.user_id = new_lead;
    INSERT INTO public.admin_actions
        (admin_user_id, action, group_id, target_user_id, reason, details)
    VALUES (me, 'crew.lead_changed', target_group, new_lead, btrim(why),
            jsonb_build_object('previous_lead', previous));
    RETURN QUERY SELECT 'done'::text, previous;
END;
$$;

-- A crew's support history, newest first, with names as they are now.
CREATE FUNCTION app_admin_group_actions(target uuid)
RETURNS TABLE (created_at timestamptz, action text, admin_name text,
               target_user_id uuid, target_name text, reason text, details jsonb)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT a.created_at, a.action, admin_user.display_name, a.target_user_id,
        target_user.display_name, a.reason, a.details
    FROM public.admin_actions a
    JOIN public.users admin_user ON admin_user.id = a.admin_user_id
    LEFT JOIN public.users target_user ON target_user.id = a.target_user_id
    WHERE a.group_id = target
    ORDER BY a.created_at DESC
    LIMIT 50
$$;
"""


def upgrade() -> None:
    op.execute(UPGRADE)
    for signature in FUNCTIONS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {ADMIN_ROLE}")


def downgrade() -> None:
    for signature in FUNCTIONS:
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("DROP TABLE admin_actions")
