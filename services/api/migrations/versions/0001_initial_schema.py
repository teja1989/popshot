"""Initial schema with forced row-level security.

Revision ID: 0001
Revises:
Create Date: 2026-10-10

How isolation works (ADR 0002):

- Each request runs in one transaction that starts with
  set_config('app.user_id', '<uuid>', true), the function form of SET LOCAL.
- Every group table has group_id, RLS enabled and forced, and policies for popshot_app that
  call the app_is_member / app_is_admin helpers. With no app.user_id set, the helpers return
  false and nothing matches.
- The helpers are SECURITY DEFINER, owned by the migration role, with a fixed search_path.
  Because RLS is forced, the owner is subject to policies too, so the owner gets narrow
  policies (TO CURRENT_USER) only on the tables the helpers need. No role needs BYPASSRLS.
- popshot_app never gets UPDATE on a group_id column, so rows can't be moved between groups.
- Child tables reference parents with composite (id, group_id) foreign keys. Foreign key
  checks bypass RLS, so a plain FK would let a member of group B attach group A's rows by ID.
- Joining a group and creating a group only happen through SECURITY DEFINER functions;
  popshot_app has no INSERT on groups or group_members.
- Rows that game history depends on (group_members, players) are never deleted on their
  own: popshot_app has no DELETE on them and the owner has no DELETE policy. People leave by
  becoming 'removed'. So ON DELETE CASCADE from those tables only runs when a lead deletes
  the whole group.

RLS protects against queries that forget a filter. It doesn't protect against arbitrary SQL
run as popshot_app (for example SQL injection), which could call set_config itself.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"

SCHEMA = """
CREATE TYPE group_role AS ENUM ('lead', 'co_lead', 'member');
CREATE TYPE member_status AS ENUM ('pending', 'active', 'removed');
CREATE TYPE match_format AS ENUM ('doubles', 'singles');
CREATE TYPE match_status AS ENUM ('pending', 'confirmed', 'disputed');
CREATE TYPE team_side AS ENUM ('A', 'B');
CREATE TYPE confirmation_decision AS ENUM ('confirm', 'dispute');

CREATE TABLE users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_subject text NOT NULL UNIQUE CHECK (char_length(auth_subject) BETWEEN 1 AND 128),
    display_name text NOT NULL CHECK (char_length(display_name) BETWEEN 1 AND 80),
    avatar_url text CHECK (
        avatar_url IS NULL OR (char_length(avatar_url) <= 2048 AND avatar_url LIKE 'https://%')
    ),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE groups (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL CHECK (char_length(btrim(name)) BETWEEN 1 AND 60),
    default_format match_format NOT NULL DEFAULT 'doubles',
    default_points_to smallint NOT NULL DEFAULT 11 CHECK (default_points_to IN (11, 15, 21)),
    default_win_by_two boolean NOT NULL DEFAULT true,
    created_by uuid NOT NULL REFERENCES users (id),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE group_members (
    group_id uuid NOT NULL REFERENCES groups (id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users (id),
    role group_role NOT NULL DEFAULT 'member',
    status member_status NOT NULL DEFAULT 'pending',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (group_id, user_id)
);
CREATE INDEX group_members_user_idx ON group_members (user_id, group_id);

CREATE TABLE group_invites (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id uuid NOT NULL REFERENCES groups (id) ON DELETE CASCADE,
    -- SHA-256 of the invite token. The token itself is never stored.
    token_hash bytea NOT NULL UNIQUE CHECK (octet_length(token_hash) = 32),
    created_by uuid NOT NULL,
    expires_at timestamptz NOT NULL,
    max_uses integer NOT NULL DEFAULT 1 CHECK (max_uses BETWEEN 1 AND 100),
    use_count integer NOT NULL DEFAULT 0 CHECK (use_count BETWEEN 0 AND max_uses),
    requires_approval boolean NOT NULL DEFAULT true,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (group_id, created_by) REFERENCES group_members (group_id, user_id)
        ON DELETE CASCADE
);
CREATE INDEX group_invites_group_idx ON group_invites (group_id);

CREATE TABLE players (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id uuid NOT NULL REFERENCES groups (id) ON DELETE CASCADE,
    -- NULL for a guest who hasn't signed up and claimed this player yet.
    user_id uuid,
    display_name text NOT NULL CHECK (char_length(btrim(display_name)) BETWEEN 1 AND 80),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, group_id),
    UNIQUE (group_id, user_id),
    FOREIGN KEY (group_id, user_id) REFERENCES group_members (group_id, user_id)
        ON DELETE CASCADE
);

CREATE TABLE matches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id uuid NOT NULL REFERENCES groups (id) ON DELETE CASCADE,
    format match_format NOT NULL,
    points_to smallint NOT NULL CHECK (points_to IN (11, 15, 21)),
    win_by_two boolean NOT NULL,
    best_of smallint NOT NULL DEFAULT 1 CHECK (best_of IN (1, 3)),
    played_at timestamptz NOT NULL,
    entered_by uuid NOT NULL,
    status match_status NOT NULL DEFAULT 'pending',
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, group_id),
    FOREIGN KEY (group_id, entered_by) REFERENCES group_members (group_id, user_id)
        ON DELETE CASCADE
);
CREATE INDEX matches_group_played_idx ON matches (group_id, played_at DESC);

CREATE TABLE match_players (
    match_id uuid NOT NULL,
    group_id uuid NOT NULL,
    player_id uuid NOT NULL,
    team team_side NOT NULL,
    PRIMARY KEY (match_id, player_id),
    FOREIGN KEY (match_id, group_id) REFERENCES matches (id, group_id) ON DELETE CASCADE,
    FOREIGN KEY (player_id, group_id) REFERENCES players (id, group_id) ON DELETE CASCADE
);
CREATE INDEX match_players_player_idx ON match_players (player_id);

CREATE TABLE match_games (
    match_id uuid NOT NULL,
    group_id uuid NOT NULL,
    game_number smallint NOT NULL CHECK (game_number BETWEEN 1 AND 3),
    team_a_score smallint NOT NULL CHECK (team_a_score BETWEEN 0 AND 99),
    team_b_score smallint NOT NULL CHECK (team_b_score BETWEEN 0 AND 99),
    PRIMARY KEY (match_id, game_number),
    FOREIGN KEY (match_id, group_id) REFERENCES matches (id, group_id) ON DELETE CASCADE
);

CREATE TABLE match_confirmations (
    match_id uuid NOT NULL,
    group_id uuid NOT NULL,
    user_id uuid NOT NULL,
    decision confirmation_decision NOT NULL,
    decided_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (match_id, user_id),
    FOREIGN KEY (match_id, group_id) REFERENCES matches (id, group_id) ON DELETE CASCADE,
    FOREIGN KEY (group_id, user_id) REFERENCES group_members (group_id, user_id)
        ON DELETE CASCADE
);

CREATE TABLE ratings (
    group_id uuid NOT NULL,
    player_id uuid NOT NULL,
    rating numeric(7, 2) NOT NULL,
    games_played integer NOT NULL DEFAULT 0 CHECK (games_played >= 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (group_id, player_id),
    FOREIGN KEY (player_id, group_id) REFERENCES players (id, group_id) ON DELETE CASCADE
);

CREATE TABLE rating_history (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    group_id uuid NOT NULL,
    player_id uuid NOT NULL,
    match_id uuid NOT NULL,
    rating_before numeric(7, 2) NOT NULL,
    rating_after numeric(7, 2) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (player_id, group_id) REFERENCES players (id, group_id) ON DELETE CASCADE,
    FOREIGN KEY (match_id, group_id) REFERENCES matches (id, group_id) ON DELETE CASCADE
);
CREATE INDEX rating_history_player_idx ON rating_history (group_id, player_id, created_at);

CREATE TABLE audit_log (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    group_id uuid NOT NULL REFERENCES groups (id) ON DELETE CASCADE,
    actor_user_id uuid NOT NULL,
    action text NOT NULL CHECK (action ~ '^[a-z][a-z_.]{0,63}$'),
    target_id uuid,
    details jsonb NOT NULL DEFAULT '{}' CHECK (pg_column_size(details) <= 4096),
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (group_id, actor_user_id) REFERENCES group_members (group_id, user_id)
        ON DELETE CASCADE
);
CREATE INDEX audit_log_group_idx ON audit_log (group_id, created_at DESC);
"""

# Helpers used by policies. All SECURITY DEFINER functions pin search_path and use
# schema-qualified names, so nothing on the caller's search_path can hijack them.
FUNCTIONS = """
CREATE FUNCTION app_current_user_id() RETURNS uuid
LANGUAGE sql STABLE
SET search_path = pg_catalog, pg_temp
AS $$
    -- Unset or empty means no user. A malformed value raises an error (fails closed).
    SELECT nullif(current_setting('app.user_id', true), '')::uuid
$$;

CREATE FUNCTION app_is_member(target_group uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.group_members m
        WHERE m.group_id = target_group
          AND m.user_id = public.app_current_user_id()
          AND m.status = 'active'
    )
$$;

CREATE FUNCTION app_is_admin(target_group uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.group_members m
        WHERE m.group_id = target_group
          AND m.user_id = public.app_current_user_id()
          AND m.status = 'active'
          AND m.role IN ('lead', 'co_lead')
    )
$$;

CREATE FUNCTION app_is_lead(target_group uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.group_members m
        WHERE m.group_id = target_group
          AND m.user_id = public.app_current_user_id()
          AND m.status = 'active'
          AND m.role = 'lead'
    )
$$;

CREATE FUNCTION app_is_pending(target_group uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.group_members m
        WHERE m.group_id = target_group
          AND m.user_id = public.app_current_user_id()
          AND m.status = 'pending'
    )
$$;

-- You can see a user if you share an active group, or you're an admin of a group they've
-- asked to join.
CREATE FUNCTION app_can_see_user(target_user uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.group_members me
        JOIN public.group_members them ON them.group_id = me.group_id
        WHERE me.user_id = public.app_current_user_id()
          AND me.status = 'active'
          AND them.user_id = target_user
          AND (
              them.status = 'active'
              OR (them.status = 'pending' AND me.role IN ('lead', 'co_lead'))
          )
    )
$$;

-- Called once per request with claims from a verified token, before app.user_id is set.
-- Creates the user on first sign-in. Profile fields are not overwritten later.
CREATE FUNCTION app_resolve_user(subject text, name text, avatar text) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    found_id uuid;
BEGIN
    SELECT u.id INTO found_id FROM public.users u WHERE u.auth_subject = subject;
    IF found_id IS NOT NULL THEN
        RETURN found_id;
    END IF;
    INSERT INTO public.users (auth_subject, display_name, avatar_url)
    VALUES (subject, name, avatar)
    ON CONFLICT (auth_subject) DO NOTHING;
    SELECT u.id INTO found_id FROM public.users u WHERE u.auth_subject = subject;
    RETURN found_id;
END;
$$;

-- Creates a group with the current user as its lead and as its first player.
CREATE FUNCTION app_create_group(
    group_name text, fmt match_format, points_to smallint, win_by_two boolean
) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
    new_group uuid := gen_random_uuid();
    my_name text;
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no user context' USING ERRCODE = 'insufficient_privilege';
    END IF;
    SELECT u.display_name INTO STRICT my_name FROM public.users u WHERE u.id = me;

    INSERT INTO public.groups (id, name, default_format, default_points_to,
                               default_win_by_two, created_by)
    VALUES (new_group, btrim(group_name), fmt, points_to, win_by_two, me);
    INSERT INTO public.group_members (group_id, user_id, role, status)
    VALUES (new_group, me, 'lead', 'active');
    INSERT INTO public.players (group_id, user_id, display_name)
    VALUES (new_group, me, my_name);
    RETURN new_group;
END;
$$;

-- Redeems an invite for the current user. Returns no row when the invite is unknown,
-- revoked, expired or used up, without saying which. An existing membership (including a
-- removed one) is returned unchanged and doesn't use up the invite.
CREATE FUNCTION app_redeem_invite(invite_token_hash bytea)
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
    IF NOT FOUND OR inv.revoked_at IS NOT NULL OR inv.expires_at <= now()
       OR inv.use_count >= inv.max_uses THEN
        RETURN;
    END IF;

    SELECT m.status INTO existing FROM public.group_members m
    WHERE m.group_id = inv.group_id AND m.user_id = me;
    IF FOUND THEN
        RETURN QUERY SELECT inv.group_id, existing;
        RETURN;
    END IF;

    new_status := CASE WHEN inv.requires_approval THEN 'pending' ELSE 'active' END;
    INSERT INTO public.group_members (group_id, user_id, role, status)
    VALUES (inv.group_id, me, 'member', new_status);
    UPDATE public.group_invites SET use_count = use_count + 1 WHERE id = inv.id;
    RETURN QUERY SELECT inv.group_id, new_status;
END;
$$;
"""

DEFINER_FUNCTIONS = [
    "app_is_member(uuid)",
    "app_is_admin(uuid)",
    "app_is_lead(uuid)",
    "app_is_pending(uuid)",
    "app_can_see_user(uuid)",
    "app_resolve_user(text, text, text)",
    "app_create_group(text, match_format, smallint, boolean)",
    "app_redeem_invite(bytea)",
]

GROUP_TABLES = [
    "groups",
    "group_members",
    "group_invites",
    "players",
    "matches",
    "match_players",
    "match_games",
    "match_confirmations",
    "ratings",
    "rating_history",
    "audit_log",
]

# Narrow policies for the owner, used only by the SECURITY DEFINER functions above.
# Everything else stays default-deny for the owner, because RLS is forced.
OWNER_POLICIES = """
CREATE POLICY owner_definer_read ON users FOR SELECT TO CURRENT_USER USING (true);
CREATE POLICY owner_definer_insert ON users FOR INSERT TO CURRENT_USER WITH CHECK (true);
CREATE POLICY owner_definer_insert ON groups FOR INSERT TO CURRENT_USER WITH CHECK (true);
CREATE POLICY owner_definer_read ON group_members FOR SELECT TO CURRENT_USER USING (true);
CREATE POLICY owner_definer_insert ON group_members FOR INSERT TO CURRENT_USER
    WITH CHECK (true);
CREATE POLICY owner_definer_read ON group_invites FOR SELECT TO CURRENT_USER USING (true);
CREATE POLICY owner_definer_update ON group_invites FOR UPDATE TO CURRENT_USER
    USING (true) WITH CHECK (true);
CREATE POLICY owner_definer_insert ON players FOR INSERT TO CURRENT_USER WITH CHECK (true);
"""

APP_POLICIES = f"""
-- users: yourself, and people you share a group with.
CREATE POLICY app_select ON users FOR SELECT TO {APP_ROLE}
    USING (id = app_current_user_id() OR app_can_see_user(id));
CREATE POLICY app_update_self ON users FOR UPDATE TO {APP_ROLE}
    USING (id = app_current_user_id()) WITH CHECK (id = app_current_user_id());

-- groups: members (and people waiting for approval) can see it; admins edit; the lead
-- deletes. Creation goes through app_create_group.
CREATE POLICY app_select ON groups FOR SELECT TO {APP_ROLE}
    USING (app_is_member(id) OR app_is_pending(id));
CREATE POLICY app_update ON groups FOR UPDATE TO {APP_ROLE}
    USING (app_is_admin(id)) WITH CHECK (app_is_admin(id));
CREATE POLICY app_delete ON groups FOR DELETE TO {APP_ROLE}
    USING (app_is_lead(id));

-- group_members: members see the roster; you always see your own row. The lead can change
-- any membership. Co-leads can only approve or remove plain members, and they stay plain
-- members, so a co-lead can't promote themselves or remove the lead. Anyone may leave,
-- ending up as a removed plain member. Joining goes through app_redeem_invite /
-- app_create_group.
CREATE POLICY app_select ON group_members FOR SELECT TO {APP_ROLE}
    USING (app_is_member(group_id) OR user_id = app_current_user_id());
CREATE POLICY app_lead_update ON group_members FOR UPDATE TO {APP_ROLE}
    USING (app_is_lead(group_id)) WITH CHECK (app_is_lead(group_id));
CREATE POLICY app_co_lead_update ON group_members FOR UPDATE TO {APP_ROLE}
    USING (app_is_admin(group_id) AND role = 'member')
    WITH CHECK (app_is_admin(group_id) AND role = 'member');
CREATE POLICY app_leave ON group_members FOR UPDATE TO {APP_ROLE}
    USING (user_id = app_current_user_id())
    WITH CHECK (user_id = app_current_user_id() AND status = 'removed' AND role = 'member');

-- group_invites: admins only.
CREATE POLICY app_admin_all ON group_invites FOR ALL TO {APP_ROLE}
    USING (app_is_admin(group_id))
    WITH CHECK (app_is_admin(group_id) AND created_by = app_current_user_id());

-- Game data: any active member.
CREATE POLICY app_member_all ON players FOR ALL TO {APP_ROLE}
    USING (app_is_member(group_id)) WITH CHECK (app_is_member(group_id));

CREATE POLICY app_member_select ON matches FOR SELECT TO {APP_ROLE}
    USING (app_is_member(group_id));
CREATE POLICY app_member_insert ON matches FOR INSERT TO {APP_ROLE}
    WITH CHECK (app_is_member(group_id) AND entered_by = app_current_user_id());
CREATE POLICY app_member_update ON matches FOR UPDATE TO {APP_ROLE}
    USING (app_is_member(group_id)) WITH CHECK (app_is_member(group_id));
CREATE POLICY app_member_delete ON matches FOR DELETE TO {APP_ROLE}
    USING (app_is_member(group_id));

CREATE POLICY app_member_all ON match_players FOR ALL TO {APP_ROLE}
    USING (app_is_member(group_id)) WITH CHECK (app_is_member(group_id));
CREATE POLICY app_member_all ON match_games FOR ALL TO {APP_ROLE}
    USING (app_is_member(group_id)) WITH CHECK (app_is_member(group_id));

CREATE POLICY app_member_select ON match_confirmations FOR SELECT TO {APP_ROLE}
    USING (app_is_member(group_id));
CREATE POLICY app_own_write ON match_confirmations FOR ALL TO {APP_ROLE}
    USING (app_is_member(group_id) AND user_id = app_current_user_id())
    WITH CHECK (app_is_member(group_id) AND user_id = app_current_user_id());

CREATE POLICY app_member_all ON ratings FOR ALL TO {APP_ROLE}
    USING (app_is_member(group_id)) WITH CHECK (app_is_member(group_id));
CREATE POLICY app_member_all ON rating_history FOR ALL TO {APP_ROLE}
    USING (app_is_member(group_id)) WITH CHECK (app_is_member(group_id));

-- audit_log: append-only. Members write their own entries; admins read.
CREATE POLICY app_admin_select ON audit_log FOR SELECT TO {APP_ROLE}
    USING (app_is_admin(group_id));
CREATE POLICY app_member_insert ON audit_log FOR INSERT TO {APP_ROLE}
    WITH CHECK (app_is_member(group_id) AND actor_user_id = app_current_user_id());
"""

# Table privileges for the app role. UPDATE is column-scoped and never includes group_id
# or other identity columns. Tables not listed get nothing.
APP_GRANTS = f"""
GRANT SELECT, UPDATE (display_name, avatar_url) ON users TO {APP_ROLE};
GRANT SELECT, DELETE,
      UPDATE (name, default_format, default_points_to, default_win_by_two)
      ON groups TO {APP_ROLE};
GRANT SELECT, UPDATE (role, status, updated_at) ON group_members TO {APP_ROLE};
GRANT SELECT, INSERT, DELETE, UPDATE (revoked_at) ON group_invites TO {APP_ROLE};
GRANT SELECT, INSERT, UPDATE (display_name) ON players TO {APP_ROLE};
GRANT SELECT, INSERT, DELETE,
      UPDATE (format, points_to, win_by_two, best_of, played_at, status)
      ON matches TO {APP_ROLE};
GRANT SELECT, INSERT, DELETE, UPDATE (team) ON match_players TO {APP_ROLE};
GRANT SELECT, INSERT, DELETE, UPDATE (team_a_score, team_b_score) ON match_games
      TO {APP_ROLE};
GRANT SELECT, INSERT, UPDATE (decision, decided_at) ON match_confirmations TO {APP_ROLE};
GRANT SELECT, INSERT, DELETE, UPDATE (rating, games_played, updated_at) ON ratings
      TO {APP_ROLE};
GRANT SELECT, INSERT ON rating_history TO {APP_ROLE};
GRANT SELECT, INSERT ON audit_log TO {APP_ROLE};
"""


def upgrade() -> None:
    op.execute(SCHEMA)
    op.execute(FUNCTIONS)
    for table in ["users", *GROUP_TABLES]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON {table} FROM PUBLIC")
    op.execute(OWNER_POLICIES)
    op.execute(APP_POLICIES)
    op.execute(APP_GRANTS)
    op.execute("REVOKE EXECUTE ON FUNCTION app_current_user_id() FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION app_current_user_id() TO {APP_ROLE}")
    for signature in DEFINER_FUNCTIONS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP_ROLE}")


def downgrade() -> None:
    for table in reversed(["users", *GROUP_TABLES]):
        op.execute(f"DROP TABLE {table} CASCADE")
    for signature in [*DEFINER_FUNCTIONS, "app_current_user_id()"]:
        op.execute(f"DROP FUNCTION {signature}")
    for type_name in [
        "confirmation_decision",
        "team_side",
        "match_status",
        "match_format",
        "member_status",
        "group_role",
    ]:
        op.execute(f"DROP TYPE {type_name}")
