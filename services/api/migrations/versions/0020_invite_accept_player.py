"""Accepting a direct invite also makes you a player, so you can be put in games.

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-12

0018's app_answer_direct_invite made the person an active member but not a player, unlike
approving a join request (routes/invites.py), so they couldn't be picked for a game. This
replaces the function to add the player record, and adds one for any active member who
has none.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ANSWER = """
CREATE OR REPLACE FUNCTION app_answer_direct_invite(invite uuid, answer text) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
    inv public.direct_invites%ROWTYPE;
    existing public.member_status;
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no user context' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF answer NOT IN ('accept', 'decline', 'block') THEN
        RAISE EXCEPTION 'unknown answer' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    SELECT d.* INTO inv FROM public.direct_invites d
    JOIN public.groups g ON g.id = d.group_id AND g.deleted_at IS NULL
    WHERE d.id = invite AND d.user_id = me AND d.status = 'pending' AND d.expires_at > now()
    FOR UPDATE OF d;
    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    IF answer <> 'accept' THEN
        UPDATE public.direct_invites d SET status = 'declined', responded_at = now()
        WHERE d.id = inv.id;
        IF answer = 'block' THEN
            INSERT INTO public.invite_blocks (user_id, group_id) VALUES (me, inv.group_id)
            ON CONFLICT DO NOTHING;
        END IF;
        RETURN inv.group_id;
    END IF;

    SELECT m.status INTO existing FROM public.group_members m
    WHERE m.group_id = inv.group_id AND m.user_id = me
    FOR UPDATE;
    IF NOT FOUND THEN
        INSERT INTO public.group_members (group_id, user_id, role, status)
        VALUES (inv.group_id, me, 'member', 'active');
    ELSIF existing <> 'active' THEN
        -- A join request, or someone who left or was removed: a lead invited them back.
        UPDATE public.group_members gm
        SET status = 'active', role = 'member', left_at = NULL, updated_at = now()
        WHERE gm.group_id = inv.group_id AND gm.user_id = me;
    END IF;
    -- Their player record, so they can be put in games (as approving a request does).
    INSERT INTO public.players (group_id, user_id, display_name)
    SELECT inv.group_id, me, u.display_name FROM public.users u WHERE u.id = me
    ON CONFLICT (group_id, user_id) DO NOTHING;
    UPDATE public.direct_invites d SET status = 'accepted', responded_at = now()
    WHERE d.id = inv.id;
    INSERT INTO public.audit_log (group_id, actor_user_id, action, target_id)
    VALUES (inv.group_id, me, 'invite.direct_accepted', inv.invited_by);
    RETURN inv.group_id;
END;
$$;
"""

BEFORE = """
CREATE OR REPLACE FUNCTION app_answer_direct_invite(invite uuid, answer text) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
    inv public.direct_invites%ROWTYPE;
    existing public.member_status;
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no user context' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF answer NOT IN ('accept', 'decline', 'block') THEN
        RAISE EXCEPTION 'unknown answer' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    SELECT d.* INTO inv FROM public.direct_invites d
    JOIN public.groups g ON g.id = d.group_id AND g.deleted_at IS NULL
    WHERE d.id = invite AND d.user_id = me AND d.status = 'pending' AND d.expires_at > now()
    FOR UPDATE OF d;
    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    IF answer <> 'accept' THEN
        UPDATE public.direct_invites d SET status = 'declined', responded_at = now()
        WHERE d.id = inv.id;
        IF answer = 'block' THEN
            INSERT INTO public.invite_blocks (user_id, group_id) VALUES (me, inv.group_id)
            ON CONFLICT DO NOTHING;
        END IF;
        RETURN inv.group_id;
    END IF;

    SELECT m.status INTO existing FROM public.group_members m
    WHERE m.group_id = inv.group_id AND m.user_id = me
    FOR UPDATE;
    IF NOT FOUND THEN
        INSERT INTO public.group_members (group_id, user_id, role, status)
        VALUES (inv.group_id, me, 'member', 'active');
    ELSIF existing <> 'active' THEN
        -- A join request, or someone who left or was removed: a lead invited them back.
        UPDATE public.group_members gm
        SET status = 'active', role = 'member', left_at = NULL, updated_at = now()
        WHERE gm.group_id = inv.group_id AND gm.user_id = me;
    END IF;
    UPDATE public.direct_invites d SET status = 'accepted', responded_at = now()
    WHERE d.id = inv.id;
    INSERT INTO public.audit_log (group_id, actor_user_id, action, target_id)
    VALUES (inv.group_id, me, 'invite.direct_accepted', inv.invited_by);
    RETURN inv.group_id;
END;
$$;
"""

# Active members with no player record in their group.
BACKFILL = """
INSERT INTO players (group_id, user_id, display_name)
SELECT gm.group_id, gm.user_id, u.display_name
FROM group_members gm
JOIN users u ON u.id = gm.user_id
WHERE gm.status = 'active'
  AND NOT EXISTS (
      SELECT 1 FROM players p WHERE p.group_id = gm.group_id AND p.user_id = gm.user_id
  )
"""


def upgrade() -> None:
    op.execute(ANSWER)
    op.execute(BACKFILL)


def downgrade() -> None:
    op.execute(BEFORE)
