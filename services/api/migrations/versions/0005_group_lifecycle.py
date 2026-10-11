"""Deleting and restoring a group, and leaving one for good or for now.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-11

Deleting a group is soft: groups.deleted_at is set, and for 30 days its lead can restore
it. While deleted, nobody is a member of it as far as row-level security is concerned:
app_is_member, app_is_admin, app_is_lead, app_is_pending and app_can_see_user all ignore
deleted groups, so every policy built on them hides the group and its games without each
policy changing. Its invites are revoked on delete and stay revoked after a restore.

After 30 days app_purge_deleted_groups() deletes the group for good (cascading to its
members, players, games and log). It isn't granted to the app; a scheduled job runs it
as the owner.

group_members.left_at records that someone left on their own, as opposed to being removed
or declined by an admin. Someone who left can ask to join again with a live invite (they
go back to pending, or straight in if the invite doesn't need approval). Someone removed
or declined can't; only an admin can restore them.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"
RESTORE_DAYS = 30

APP_FUNCTIONS = [
    "app_delete_group(uuid)",
    "app_restore_group(uuid)",
    "app_deleted_groups()",
    "app_hand_over_lead(uuid, uuid)",
    "app_former_members(uuid)",
]
OWNER_ONLY = "app_purge_deleted_groups()"

LIVE_GROUP = (
    "EXISTS (SELECT 1 FROM public.groups g WHERE g.id = target_group AND g.deleted_at IS NULL)"
)


def _membership_check(name: str, extra: str, live_only: bool) -> str:
    live = f"\n          AND {LIVE_GROUP}" if live_only else ""
    return f"""
CREATE OR REPLACE FUNCTION {name}(target_group uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.group_members m
        WHERE m.group_id = target_group
          AND m.user_id = public.app_current_user_id()
          {extra}
    ){live}
$$;
"""


def _membership_checks(live_only: bool) -> str:
    return "".join(
        _membership_check(name, extra, live_only)
        for name, extra in [
            ("app_is_member", "AND m.status = 'active'"),
            (
                "app_is_admin",
                "AND m.status = 'active'\n          AND m.role IN ('lead', 'co_lead')",
            ),
            ("app_is_lead", "AND m.status = 'active'\n          AND m.role = 'lead'"),
            ("app_is_pending", "AND m.status = 'pending'"),
        ]
    )


def _can_see_user(live_only: bool) -> str:
    live = (
        "\n        JOIN public.groups g ON g.id = me.group_id AND g.deleted_at IS NULL"
        if live_only
        else ""
    )
    return f"""
CREATE OR REPLACE FUNCTION app_can_see_user(target_user uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.group_members me
        JOIN public.group_members them ON them.group_id = me.group_id{live}
        WHERE me.user_id = public.app_current_user_id()
          AND me.status = 'active'
          AND them.user_id = target_user
          AND (
              them.status = 'active'
              OR (them.status = 'pending' AND me.role IN ('lead', 'co_lead'))
          )
    )
$$;
"""


LIFECYCLE = f"""
-- The lead deletes their group. Returns false if the caller isn't its lead.
CREATE FUNCTION app_delete_group(target_group uuid) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
BEGIN
    IF NOT public.app_is_lead(target_group) THEN
        RETURN false;
    END IF;
    INSERT INTO public.audit_log (group_id, actor_user_id, action, target_id)
    VALUES (target_group, me, 'group.deleted', target_group);
    UPDATE public.group_invites SET revoked_at = now()
    WHERE group_id = target_group AND revoked_at IS NULL;
    UPDATE public.groups SET deleted_at = now(), deleted_by = me WHERE id = target_group;
    RETURN true;
END;
$$;

-- Groups you lead that were deleted in the last {RESTORE_DAYS} days.
CREATE FUNCTION app_deleted_groups()
RETURNS TABLE (group_id uuid, name text, deleted_at timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT g.id, g.name, g.deleted_at
    FROM public.groups g
    JOIN public.group_members m ON m.group_id = g.id
    WHERE m.user_id = public.app_current_user_id()
      AND m.status = 'active' AND m.role = 'lead'
      AND g.deleted_at > now() - interval '{RESTORE_DAYS} days'
    ORDER BY g.deleted_at DESC
$$;

-- The lead restores a group deleted in the last {RESTORE_DAYS} days.
CREATE FUNCTION app_restore_group(target_group uuid) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
BEGIN
    UPDATE public.groups g SET deleted_at = NULL, deleted_by = NULL
    WHERE g.id = target_group
      AND g.deleted_at > now() - interval '{RESTORE_DAYS} days'
      AND EXISTS (
          SELECT 1 FROM public.group_members m
          WHERE m.group_id = g.id AND m.user_id = me
            AND m.status = 'active' AND m.role = 'lead'
      );
    IF NOT FOUND THEN
        RETURN false;
    END IF;
    INSERT INTO public.audit_log (group_id, actor_user_id, action, target_id)
    VALUES (target_group, me, 'group.restored', target_group);
    RETURN true;
END;
$$;

-- The lead makes another active member the lead and becomes a co-lead, in one step (a
-- group always has exactly one lead). Returns false if the caller isn't the lead or the
-- new lead isn't an active member.
CREATE FUNCTION app_hand_over_lead(target_group uuid, new_lead uuid) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
BEGIN
    IF NOT public.app_is_lead(target_group) OR new_lead = me THEN
        RETURN false;
    END IF;
    UPDATE public.group_members SET role = 'lead', updated_at = now()
    WHERE group_id = target_group AND user_id = new_lead AND status = 'active';
    IF NOT FOUND THEN
        RETURN false;
    END IF;
    UPDATE public.group_members SET role = 'co_lead', updated_at = now()
    WHERE group_id = target_group AND user_id = me;
    INSERT INTO public.audit_log (group_id, actor_user_id, action, target_id)
    VALUES (target_group, me, 'member.made_lead', new_lead);
    RETURN true;
END;
$$;

-- For leads and co-leads: people an admin removed or declined, who could be restored.
-- People who left on their own aren't listed; they can ask again with an invite. Row-level
-- security on users hides people outside your groups, hence SECURITY DEFINER.
CREATE FUNCTION app_former_members(target_group uuid)
RETURNS TABLE (user_id uuid, display_name text, avatar_url text, since timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT u.id, u.display_name, u.avatar_url, m.updated_at
    FROM public.group_members m
    JOIN public.users u ON u.id = m.user_id
    WHERE m.group_id = target_group
      AND m.status = 'removed' AND m.left_at IS NULL
      AND public.app_is_admin(target_group)
    ORDER BY m.updated_at DESC, u.id
$$;

-- Deletes groups past their restore window, for good. Owner only (a scheduled job).
CREATE FUNCTION app_purge_deleted_groups() RETURNS integer
LANGUAGE sql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    WITH gone AS (
        DELETE FROM public.groups
        WHERE deleted_at <= now() - interval '{RESTORE_DAYS} days'
        RETURNING 1
    )
    SELECT count(*)::integer FROM gone
$$;
"""


def _preview(live_only: bool) -> str:
    # With live_only: nothing for a deleted group, and someone who left on their own is
    # treated as not in the group, so they're offered to ask again.
    live = "\n      AND g.deleted_at IS NULL" if live_only else ""
    left = " AND m.left_at IS NULL" if live_only else ""
    return f"""
CREATE OR REPLACE FUNCTION app_preview_invite(invite_token_hash bytea)
RETURNS TABLE (group_id uuid, group_name text, invited_by text, my_status member_status)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT CASE WHEN m.status IN ('active', 'pending') THEN g.id END,
           g.name, u.display_name, m.status
    FROM public.group_invites i
    JOIN public.groups g ON g.id = i.group_id
    JOIN public.users u ON u.id = i.created_by
    LEFT JOIN public.group_members m
           ON m.group_id = i.group_id AND m.user_id = public.app_current_user_id(){left}
    WHERE public.app_current_user_id() IS NOT NULL
      AND i.token_hash = invite_token_hash{live}
      AND (m.status IS NOT NULL
           OR (i.revoked_at IS NULL AND i.expires_at > now() AND i.use_count < i.max_uses))
$$;
"""


def _redeem(rejoin: bool) -> str:
    # 0002's version, plus (with rejoin) someone who left can come back with a live invite.
    # A deleted group's invites are all revoked, so they never pass the live check.
    existing = (
        """
    SELECT m.status, m.left_at INTO existing, existing_left FROM public.group_members m
    WHERE m.group_id = inv.group_id AND m.user_id = me;
    IF FOUND AND NOT (existing = 'removed' AND existing_left IS NOT NULL) THEN
        RETURN QUERY SELECT inv.group_id, existing;
        RETURN;
    END IF;
    rejoining := FOUND;
"""
        if rejoin
        else """
    SELECT m.status INTO existing FROM public.group_members m
    WHERE m.group_id = inv.group_id AND m.user_id = me;
    IF FOUND THEN
        RETURN QUERY SELECT inv.group_id, existing;
        RETURN;
    END IF;
"""
    )
    join = (
        """
    IF rejoining THEN
        UPDATE public.group_members gm
        SET status = new_status, role = 'member', left_at = NULL, updated_at = now()
        WHERE gm.group_id = inv.group_id AND gm.user_id = me;
    ELSE
        INSERT INTO public.group_members (group_id, user_id, role, status)
        VALUES (inv.group_id, me, 'member', new_status);
    END IF;
"""
        if rejoin
        else """
    INSERT INTO public.group_members (group_id, user_id, role, status)
    VALUES (inv.group_id, me, 'member', new_status);
"""
    )
    declare_extra = (
        "\n    existing_left timestamptz;\n    rejoining boolean := false;" if rejoin else ""
    )
    return f"""
CREATE OR REPLACE FUNCTION app_redeem_invite(invite_token_hash bytea)
RETURNS TABLE (group_id uuid, status member_status)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
    inv public.group_invites%ROWTYPE;
    existing public.member_status;
    new_status public.member_status;{declare_extra}
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no user context' USING ERRCODE = 'insufficient_privilege';
    END IF;

    SELECT * INTO inv FROM public.group_invites i
    WHERE i.token_hash = invite_token_hash
    FOR UPDATE;
    IF NOT FOUND THEN
        RETURN;
    END IF;
{existing}
    IF inv.revoked_at IS NOT NULL OR inv.expires_at <= now()
       OR inv.use_count >= inv.max_uses THEN
        RETURN;
    END IF;

    new_status := CASE WHEN inv.requires_approval THEN 'pending' ELSE 'active' END;{join}
    UPDATE public.group_invites SET use_count = use_count + 1 WHERE id = inv.id;
    RETURN QUERY SELECT inv.group_id, new_status;
END;
$$;
"""


OWNER_POLICIES = [
    ("owner_definer_update", "groups", "FOR UPDATE TO CURRENT_USER USING (true) WITH CHECK (true)"),
    ("owner_definer_delete", "groups", "FOR DELETE TO CURRENT_USER USING (true)"),
    (
        "owner_definer_update",
        "group_members",
        "FOR UPDATE TO CURRENT_USER USING (true) WITH CHECK (true)",
    ),
    ("owner_definer_insert", "audit_log", "FOR INSERT TO CURRENT_USER WITH CHECK (true)"),
]


def upgrade() -> None:
    op.execute(
        "ALTER TABLE groups ADD COLUMN deleted_at timestamptz, "
        "ADD COLUMN deleted_by uuid REFERENCES users (id) ON DELETE SET NULL"
    )
    op.execute(
        "CREATE INDEX groups_deleted_idx ON groups (deleted_at) WHERE deleted_at IS NOT NULL"
    )
    op.execute("ALTER TABLE group_members ADD COLUMN left_at timestamptz")
    op.execute(f"GRANT UPDATE (left_at) ON group_members TO {APP_ROLE}")
    for name, table, rule in OWNER_POLICIES:
        op.execute(f"CREATE POLICY {name} ON {table} {rule}")
    op.execute(_membership_checks(live_only=True))
    op.execute(_can_see_user(live_only=True))
    op.execute(_preview(live_only=True))
    op.execute(_redeem(rejoin=True))
    op.execute(LIFECYCLE)
    for signature in [*APP_FUNCTIONS, OWNER_ONLY]:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
    for signature in APP_FUNCTIONS:
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP_ROLE}")


def downgrade() -> None:
    for signature in [*APP_FUNCTIONS, OWNER_ONLY]:
        op.execute(f"DROP FUNCTION {signature}")
    op.execute(_redeem(rejoin=False))
    op.execute(_preview(live_only=False))
    op.execute(_can_see_user(live_only=False))
    op.execute(_membership_checks(live_only=False))
    for name, table, _ in OWNER_POLICIES:
        op.execute(f"DROP POLICY {name} ON {table}")
    op.execute(f"REVOKE UPDATE (left_at) ON group_members FROM {APP_ROLE}")
    op.execute("ALTER TABLE group_members DROP COLUMN left_at")
    op.execute("DROP INDEX groups_deleted_idx")
    op.execute("ALTER TABLE groups DROP COLUMN deleted_by, DROP COLUMN deleted_at")
