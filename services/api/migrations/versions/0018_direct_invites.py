"""Direct invites: a lead or co-lead invites a person, who accepts or declines.

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-12

Popshot has no open search for people. A lead finds someone in one of two ways:

- People they know: anyone who is or was in a crew with them (app_known_people).
- A Popshot code the person gave them (users.invite_code, shown on that person's You page).
  Codes are random and can be changed; looking one up is limited to 20 tries an hour per
  person (app_lookup_invite_code), so codes can't be found by trying them in bulk.

An invite can only go to someone found one of those ways. It lasts 14 days. Accepting
joins the crew at once (a lead already chose them). Declining is quiet: the invite just
leaves the lead's list. The invitee can also block the crew from inviting them again; a
crew that was declined in the last 14 days, or blocked, still sees "sent", but nothing
reaches the person.

direct_invites, invite_blocks and invite_code_lookups are reached only through the
SECURITY DEFINER functions below (popshot_app has no rights on the tables), because the
person invited isn't in the crew and the crew can't see them otherwise.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"
FUNCTIONS = [
    "app_known_people(uuid, text)",
    "app_lookup_invite_code(uuid, text)",
    "app_send_direct_invite(uuid, uuid)",
    "app_group_direct_invites(uuid)",
    "app_cancel_direct_invite(uuid)",
    "app_my_direct_invites()",
    "app_answer_direct_invite(uuid, text)",
    "app_my_invite_blocks()",
    "app_unblock_invites(uuid)",
]

UPGRADE = f"""
-- Crockford base32, 8 characters, stored without the dash.
ALTER TABLE users ADD COLUMN invite_code text UNIQUE
    CHECK (invite_code ~ '^[0-9A-HJKMNP-TV-Z]{{8}}$');
GRANT UPDATE (invite_code) ON users TO {APP_ROLE};

CREATE TABLE direct_invites (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id uuid NOT NULL REFERENCES groups (id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    invited_by uuid REFERENCES users (id) ON DELETE SET NULL,
    -- 'silenced': the person declined lately or blocked the crew. The crew sees it like a
    -- pending invite; the person never does.
    status text NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'silenced', 'accepted', 'declined', 'cancelled', 'expired')
    ),
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL DEFAULT now() + interval '14 days',
    responded_at timestamptz,
    CHECK (expires_at > created_at)
);
-- One open invite per person per crew.
CREATE UNIQUE INDEX direct_invites_open_idx ON direct_invites (group_id, user_id)
    WHERE status IN ('pending', 'silenced');
CREATE INDEX direct_invites_user_idx ON direct_invites (user_id, status);

CREATE TABLE invite_blocks (
    user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    group_id uuid NOT NULL REFERENCES groups (id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, group_id)
);

-- Code lookups, for the hourly limit. Each person's rows older than a day are cleared on
-- their next lookup.
CREATE TABLE invite_code_lookups (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    found_user uuid REFERENCES users (id) ON DELETE CASCADE,
    at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX invite_code_lookups_user_idx ON invite_code_lookups (user_id, at);

ALTER TABLE direct_invites ENABLE ROW LEVEL SECURITY;
ALTER TABLE direct_invites FORCE ROW LEVEL SECURITY;
ALTER TABLE invite_blocks ENABLE ROW LEVEL SECURITY;
ALTER TABLE invite_blocks FORCE ROW LEVEL SECURITY;
ALTER TABLE invite_code_lookups ENABLE ROW LEVEL SECURITY;
ALTER TABLE invite_code_lookups FORCE ROW LEVEL SECURITY;
REVOKE ALL ON direct_invites, invite_blocks, invite_code_lookups FROM PUBLIC;

-- Only the functions below touch these tables.
CREATE POLICY owner_definer_all ON direct_invites FOR ALL TO CURRENT_USER
    USING (true) WITH CHECK (true);
CREATE POLICY owner_definer_all ON invite_blocks FOR ALL TO CURRENT_USER
    USING (true) WITH CHECK (true);
CREATE POLICY owner_definer_all ON invite_code_lookups FOR ALL TO CURRENT_USER
    USING (true) WITH CHECK (true);

-- Whether `target_user` is or was in a crew with the current user (both actually joined).
CREATE FUNCTION app_knows(target_user uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.group_members me
        JOIN public.group_members them ON them.group_id = me.group_id
        WHERE me.user_id = public.app_current_user_id()
          AND me.status IN ('active', 'removed')
          AND them.user_id = target_user
          AND them.status IN ('active', 'removed')
          AND them.user_id <> me.user_id
    )
$$;

-- Where a person stands with a crew, as a lead sees it.
CREATE FUNCTION app_invite_standing(target_group uuid, target_user uuid) RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT CASE
        WHEN m.status = 'active' THEN 'member'
        WHEN m.status = 'pending' THEN 'requested'
        WHEN EXISTS (
            SELECT 1 FROM public.direct_invites d
            WHERE d.group_id = target_group AND d.user_id = target_user
              AND d.status IN ('pending', 'silenced') AND d.expires_at > now()
        ) THEN 'invited'
    END
    FROM (SELECT 1) one
    LEFT JOIN public.group_members m
           ON m.group_id = target_group AND m.user_id = target_user
$$;

-- People the current user knows, for a lead or co-lead of `target_group` to invite. Up to
-- 20, A to Z, whose name contains `query` (any case).
CREATE FUNCTION app_known_people(target_group uuid, query text)
RETURNS TABLE (user_id uuid, display_name text, avatar_url text, standing text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT u.id, u.display_name, u.avatar_url, public.app_invite_standing(target_group, u.id)
    FROM public.users u
    WHERE public.app_is_admin(target_group)
      AND public.app_knows(u.id)
      AND strpos(lower(u.display_name), lower(coalesce(query, ''))) > 0
    ORDER BY lower(u.display_name), u.id
    LIMIT 20
$$;

-- The person with this code, for a lead or co-lead of `target_group`. At most 20 lookups an
-- hour per person, found or not (SQLSTATE PS429 past that).
CREATE FUNCTION app_lookup_invite_code(target_group uuid, code text)
RETURNS TABLE (user_id uuid, display_name text, avatar_url text, standing text)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
    found_id uuid;
BEGIN
    IF me IS NULL OR NOT public.app_is_admin(target_group) THEN
        RETURN;
    END IF;
    DELETE FROM public.invite_code_lookups l
    WHERE l.user_id = me AND l.at < now() - interval '1 day';
    IF (SELECT count(*) FROM public.invite_code_lookups l
        WHERE l.user_id = me AND l.at > now() - interval '1 hour') >= 20 THEN
        RAISE EXCEPTION 'too many code lookups' USING ERRCODE = 'PS429';
    END IF;
    SELECT u.id INTO found_id FROM public.users u
    WHERE u.invite_code = code AND u.id <> me;
    INSERT INTO public.invite_code_lookups (user_id, found_user) VALUES (me, found_id);
    IF found_id IS NOT NULL THEN
        RETURN QUERY
        SELECT u.id, u.display_name, u.avatar_url,
               public.app_invite_standing(target_group, u.id)
        FROM public.users u WHERE u.id = found_id;
    END IF;
END;
$$;

-- Invite someone the current user knows, or looked up by code in the last hour. Returns
-- 'sent', 'member', 'requested', 'too_many', or 'not_found' (not a lead or co-lead here,
-- or nobody they can invite).
CREATE FUNCTION app_send_direct_invite(target_group uuid, invitee uuid) RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
    standing text;
    quiet boolean;
BEGIN
    IF me IS NULL OR invitee IS NULL OR invitee = me OR NOT public.app_is_admin(target_group)
    THEN
        RETURN 'not_found';
    END IF;
    IF NOT (public.app_knows(invitee) OR EXISTS (
        SELECT 1 FROM public.invite_code_lookups l
        WHERE l.user_id = me AND l.found_user = invitee AND l.at > now() - interval '1 hour'
    )) THEN
        RETURN 'not_found';
    END IF;

    UPDATE public.direct_invites d SET status = 'expired'
    WHERE d.group_id = target_group AND d.user_id = invitee
      AND d.status IN ('pending', 'silenced') AND d.expires_at <= now();
    standing := public.app_invite_standing(target_group, invitee);
    IF standing = 'invited' THEN
        RETURN 'sent';
    ELSIF standing IS NOT NULL THEN
        RETURN standing;
    END IF;
    IF (SELECT count(*) FROM public.direct_invites d
        WHERE d.group_id = target_group AND d.status IN ('pending', 'silenced')
          AND d.expires_at > now()) >= 50 THEN
        RETURN 'too_many';
    END IF;

    quiet := EXISTS (
        SELECT 1 FROM public.invite_blocks b
        WHERE b.user_id = invitee AND b.group_id = target_group
    ) OR EXISTS (
        SELECT 1 FROM public.direct_invites d
        WHERE d.group_id = target_group AND d.user_id = invitee AND d.status = 'declined'
          AND d.responded_at > now() - interval '14 days'
    );
    INSERT INTO public.direct_invites (group_id, user_id, invited_by, status)
    VALUES (target_group, invitee, me, CASE WHEN quiet THEN 'silenced' ELSE 'pending' END)
    ON CONFLICT (group_id, user_id) WHERE status IN ('pending', 'silenced') DO NOTHING;
    INSERT INTO public.audit_log (group_id, actor_user_id, action, target_id)
    VALUES (target_group, me, 'invite.direct_sent', invitee);
    RETURN 'sent';
END;
$$;

-- A crew's open invites, for its leads and co-leads.
CREATE FUNCTION app_group_direct_invites(target_group uuid)
RETURNS TABLE (id uuid, user_id uuid, display_name text, avatar_url text,
               invited_by_name text, created_at timestamptz, expires_at timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT d.id, u.id, u.display_name, u.avatar_url, inviter.display_name,
           d.created_at, d.expires_at
    FROM public.direct_invites d
    JOIN public.users u ON u.id = d.user_id
    LEFT JOIN public.users inviter ON inviter.id = d.invited_by
    WHERE public.app_is_admin(target_group)
      AND d.group_id = target_group
      AND d.status IN ('pending', 'silenced') AND d.expires_at > now()
    ORDER BY d.created_at DESC
$$;

-- Take back an open invite. True if there was one.
CREATE FUNCTION app_cancel_direct_invite(invite uuid) RETURNS boolean
LANGUAGE sql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    WITH cancelled AS (
        UPDATE public.direct_invites d SET status = 'cancelled', responded_at = now()
        WHERE d.id = invite AND d.status IN ('pending', 'silenced')
          AND public.app_is_admin(d.group_id)
        RETURNING 1
    )
    SELECT EXISTS (SELECT 1 FROM cancelled)
$$;

-- The current user's invites waiting for an answer.
CREATE FUNCTION app_my_direct_invites()
RETURNS TABLE (id uuid, group_id uuid, group_name text, invited_by_name text,
               members bigint, created_at timestamptz, expires_at timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT d.id, g.id, g.name, inviter.display_name,
           (SELECT count(*) FROM public.group_members m
            WHERE m.group_id = g.id AND m.status = 'active'),
           d.created_at, d.expires_at
    FROM public.direct_invites d
    JOIN public.groups g ON g.id = d.group_id AND g.deleted_at IS NULL
    LEFT JOIN public.users inviter ON inviter.id = d.invited_by
    WHERE d.user_id = public.app_current_user_id()
      AND d.status = 'pending' AND d.expires_at > now()
    ORDER BY d.created_at DESC
$$;

-- Answer an invite: 'accept' joins the crew, 'decline' says no, 'block' says no and stops
-- that crew inviting again. Returns the crew, or nothing if there's no such open invite.
CREATE FUNCTION app_answer_direct_invite(invite uuid, answer text) RETURNS uuid
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

-- Crews the current user has stopped from inviting them.
CREATE FUNCTION app_my_invite_blocks()
RETURNS TABLE (group_id uuid, group_name text, created_at timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT g.id, g.name, b.created_at
    FROM public.invite_blocks b
    JOIN public.groups g ON g.id = b.group_id
    WHERE b.user_id = public.app_current_user_id()
    ORDER BY b.created_at DESC
$$;

-- Let a crew invite the current user again. True if it was blocked.
CREATE FUNCTION app_unblock_invites(target_group uuid) RETURNS boolean
LANGUAGE sql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    WITH removed AS (
        DELETE FROM public.invite_blocks b
        WHERE b.user_id = public.app_current_user_id() AND b.group_id = target_group
        RETURNING 1
    )
    SELECT EXISTS (SELECT 1 FROM removed)
$$;
"""

HELPERS = ["app_knows(uuid)", "app_invite_standing(uuid, uuid)"]


def upgrade() -> None:
    op.execute(UPGRADE)
    for signature in HELPERS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
    for signature in FUNCTIONS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP_ROLE}")


def downgrade() -> None:
    for signature in [*reversed(FUNCTIONS), *reversed(HELPERS)]:
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("DROP TABLE invite_code_lookups")
    op.execute("DROP TABLE invite_blocks")
    op.execute("DROP TABLE direct_invites")
    op.execute(f"REVOKE UPDATE (invite_code) ON users FROM {APP_ROLE}")
    op.execute("ALTER TABLE users DROP COLUMN invite_code")
