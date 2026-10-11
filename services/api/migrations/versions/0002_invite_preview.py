"""Invite previews, and invite links that keep working for the person who used them.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-11

app_preview_invite is a SECURITY DEFINER function like app_redeem_invite: the person opening
the link isn't in the group yet, so row-level security hides it from them. It answers only
a signed-in user, and only for a live invite (not revoked, expired or used up) unless the
caller already has a membership in that group. It returns the group's name, who made the
invite, and the caller's membership if they have one.
The group's ID only comes back to someone already in it or waiting to be let in.

It reads groups, which the owner had no policy for, so this adds a read-only owner policy
on groups, used only by definer functions (ADR 0004, point 3).

app_redeem_invite now looks for an existing membership before checking that the invite is
still live, so opening a used-up single-use link again shows "waiting for approval" instead
of "invalid". The preview does the same. Neither tells anyone outside the group anything new.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"
SIGNATURE = "app_preview_invite(bytea)"

PREVIEW = """
CREATE FUNCTION app_preview_invite(invite_token_hash bytea)
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
           ON m.group_id = i.group_id AND m.user_id = public.app_current_user_id()
    WHERE public.app_current_user_id() IS NOT NULL
      AND i.token_hash = invite_token_hash
      AND (m.status IS NOT NULL
           OR (i.revoked_at IS NULL AND i.expires_at > now() AND i.use_count < i.max_uses))
$$;
"""


def _redeem(existing_first: bool) -> str:
    existing = """
    SELECT m.status INTO existing FROM public.group_members m
    WHERE m.group_id = inv.group_id AND m.user_id = me;
    IF FOUND THEN
        RETURN QUERY SELECT inv.group_id, existing;
        RETURN;
    END IF;
"""
    live = """
    IF inv.revoked_at IS NOT NULL OR inv.expires_at <= now()
       OR inv.use_count >= inv.max_uses THEN
        RETURN;
    END IF;
"""
    checks = existing + live if existing_first else live + existing
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
    new_status public.member_status;
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
{checks}
    new_status := CASE WHEN inv.requires_approval THEN 'pending' ELSE 'active' END;
    INSERT INTO public.group_members (group_id, user_id, role, status)
    VALUES (inv.group_id, me, 'member', new_status);
    UPDATE public.group_invites SET use_count = use_count + 1 WHERE id = inv.id;
    RETURN QUERY SELECT inv.group_id, new_status;
END;
$$;
"""


def upgrade() -> None:
    op.execute("CREATE POLICY owner_definer_read ON groups FOR SELECT TO CURRENT_USER USING (true)")
    op.execute(PREVIEW)
    op.execute(f"REVOKE EXECUTE ON FUNCTION {SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {SIGNATURE} TO {APP_ROLE}")
    op.execute(_redeem(existing_first=True))


def downgrade() -> None:
    op.execute(_redeem(existing_first=False))
    op.execute(f"DROP FUNCTION {SIGNATURE}")
    op.execute("DROP POLICY owner_definer_read ON groups")
