"""Shared recap links, and keeping your name off them.

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-12

A member can share an outing's recap as a link anyone can open (routes/shares.py). The link
carries a random token; only its SHA-256 is stored, like invite links. Links last 30 days
at most, and whoever made one, or a lead or co-lead, can turn it off.

Opening a link needs no sign-in, so the API reads the recap through the app_public_share_*
functions below: each takes the token's hash, checks the link is live (not turned off, not
expired, its group not deleted) and returns that one group's data for the card, nothing
else. They're granted to popshot_app, which calls them with no user set.

users.hide_on_shared_cards: someone who'd rather not be named on shared cards is shown as
"a crew member" there. Inside the app nothing changes.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"
PUBLIC = [
    "app_public_share(bytea)",
    "app_public_share_matches(bytea)",
    "app_public_share_players(bytea)",
    "app_public_share_nights(bytea)",
    "app_public_share_text(bytea)",
]

UPGRADE = f"""
ALTER TABLE users ADD COLUMN hide_on_shared_cards boolean NOT NULL DEFAULT false;
GRANT UPDATE (hide_on_shared_cards) ON users TO {APP_ROLE};

CREATE TABLE recap_shares (
    token_hash bytea PRIMARY KEY CHECK (octet_length(token_hash) = 32),
    group_id uuid NOT NULL REFERENCES groups (id) ON DELETE CASCADE,
    outing_key uuid NOT NULL,
    created_by uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL DEFAULT now() + interval '30 days',
    revoked_at timestamptz,
    CHECK (expires_at > created_at AND expires_at <= created_at + interval '30 days')
);
CREATE INDEX recap_shares_outing_idx ON recap_shares (group_id, outing_key);

ALTER TABLE recap_shares ENABLE ROW LEVEL SECURITY;
ALTER TABLE recap_shares FORCE ROW LEVEL SECURITY;
REVOKE ALL ON recap_shares FROM PUBLIC;
CREATE POLICY app_member_select ON recap_shares FOR SELECT TO {APP_ROLE}
    USING (app_is_member(group_id));
CREATE POLICY app_member_insert ON recap_shares FOR INSERT TO {APP_ROLE}
    WITH CHECK (app_is_member(group_id) AND created_by = app_current_user_id());
-- Turning a link off: whoever made it, or a lead or co-lead.
CREATE POLICY app_turn_off ON recap_shares FOR UPDATE TO {APP_ROLE}
    USING (app_is_member(group_id)
           AND (created_by = app_current_user_id() OR app_is_admin(group_id)))
    WITH CHECK (app_is_member(group_id)
                AND (created_by = app_current_user_id() OR app_is_admin(group_id)));
GRANT SELECT, INSERT, UPDATE (revoked_at) ON recap_shares TO {APP_ROLE};

-- For the functions below.
CREATE POLICY owner_definer_read ON recap_shares FOR SELECT TO CURRENT_USER USING (true);
CREATE POLICY owner_definer_read ON match_games FOR SELECT TO CURRENT_USER USING (true);
CREATE POLICY owner_definer_read ON recap_texts FOR SELECT TO CURRENT_USER USING (true);

-- The group and outing of a live link, or nothing.
CREATE FUNCTION app_public_share(token bytea)
RETURNS TABLE (group_id uuid, outing_key uuid, crew text, expires_at timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT s.group_id, s.outing_key, g.name, s.expires_at
    FROM public.recap_shares s
    JOIN public.groups g ON g.id = s.group_id AND g.deleted_at IS NULL
    WHERE s.token_hash = token AND s.revoked_at IS NULL AND s.expires_at > now()
$$;

-- That group's games, shaped like routes/board.group_matches.
CREATE FUNCTION app_public_share_matches(token bytea)
RETURNS TABLE (id uuid, played_at timestamptz, team_a uuid[], team_b uuid[], games json)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT m.id, m.played_at,
           (SELECT array_agg(mp.player_id ORDER BY mp.player_id)
            FROM public.match_players mp WHERE mp.match_id = m.id AND mp.team = 'A'),
           (SELECT array_agg(mp.player_id ORDER BY mp.player_id)
            FROM public.match_players mp WHERE mp.match_id = m.id AND mp.team = 'B'),
           (SELECT json_agg(json_build_array(g.team_a_score, g.team_b_score)
                            ORDER BY g.game_number)
            FROM public.match_games g WHERE g.match_id = m.id)
    FROM public.matches m
    WHERE m.group_id = (SELECT s.group_id FROM public.app_public_share(token) s)
$$;

-- That group's players: names, and whether they'd rather not be named on shared cards.
CREATE FUNCTION app_public_share_players(token bytea)
RETURNS TABLE (player_id uuid, display_name text, hidden boolean)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT p.id, p.display_name, coalesce(u.hide_on_shared_cards, false)
    FROM public.players p
    LEFT JOIN public.users u ON u.id = p.user_id
    WHERE p.group_id = (SELECT s.group_id FROM public.app_public_share(token) s)
$$;

-- That group's meetups that weren't cancelled (for the venue).
CREATE FUNCTION app_public_share_nights(token bytea)
RETURNS TABLE (starts_at timestamptz, venue text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT n.starts_at, n.venue
    FROM public.play_nights n
    WHERE n.group_id = (SELECT s.group_id FROM public.app_public_share(token) s)
      AND n.cancelled_at IS NULL
$$;

-- Words the AI wrote for the shared outing, if any.
CREATE FUNCTION app_public_share_text(token bytea)
RETURNS TABLE (facts_hash text, status text, headline text, lines text[])
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT t.facts_hash, t.status, t.headline, t.lines
    FROM public.recap_texts t
    JOIN public.app_public_share(token) s
      ON s.group_id = t.group_id AND s.outing_key = t.outing_key
$$;
"""


def upgrade() -> None:
    op.execute(UPGRADE)
    for signature in PUBLIC:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP_ROLE}")


def downgrade() -> None:
    for signature in reversed(PUBLIC):
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("DROP POLICY owner_definer_read ON recap_texts")
    op.execute("DROP POLICY owner_definer_read ON match_games")
    op.execute("DROP TABLE recap_shares")
    op.execute(f"REVOKE UPDATE (hide_on_shared_cards) ON users FROM {APP_ROLE}")
    op.execute("ALTER TABLE users DROP COLUMN hide_on_shared_cards")
