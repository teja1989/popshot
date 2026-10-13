"""Crew events: Dink Shuffle and Ride the River, run round by round, scores as normal games.

Revision ID: 0028
Revises: 0027
Create Date: 2026-10-13

An event belongs to one crew. Its players are the crew's players (members and guests). Each
round lists who sits out; each court lists its two teams and, once scored, the game
(an ordinary match with matches.event_id set), so recaps, stats, crew points and Your week
include event games with no change. The rounds themselves are made by popshot_api.events.

Who may do what, enforced here as well as by the API:
- Any active member sees the crew's events.
- Leads and co-leads create events, and only while the format's switch is on for the crew
  (app_feature_on, 0027): 'events.shuffle' or 'events.river'. Only creating checks it, so an
  event already running can be played to the end if the crew loses access.
- Leads and co-leads add or remove players, start rounds, skip courts and finish.
- Any member fills in an empty court's score (app_score_court checks the game really is
  that court's); only leads and co-leads change one (by editing the game).

The switches arrive here, open to selected crews only, with nobody on the list.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"

UPGRADE = f"""
CREATE TABLE events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id uuid NOT NULL REFERENCES groups (id) ON DELETE CASCADE,
    kind text NOT NULL CHECK (kind IN ('shuffle', 'river')),
    name text NOT NULL CHECK (char_length(btrim(name)) BETWEEN 1 AND 60),
    vibe text NOT NULL DEFAULT 'social' CHECK (vibe IN ('social', 'competitive')),
    points_to smallint NOT NULL CHECK (points_to IN (11, 15, 21)),
    win_by_two boolean NOT NULL,
    best_of smallint NOT NULL CHECK (best_of IN (1, 3, 5)),
    courts smallint NOT NULL CHECK (courts BETWEEN 1 AND 6),
    night_id uuid,
    -- Ride the River's starting order: how it was made. Never shown.
    seeding text CHECK (seeding IN ('random', 'crew_points', 'level')),
    seed integer NOT NULL,
    status text NOT NULL DEFAULT 'live' CHECK (status IN ('live', 'finished')),
    created_by uuid NOT NULL REFERENCES users (id),
    created_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    CHECK ((status = 'finished') = (finished_at IS NOT NULL)),
    CHECK ((kind = 'river') = (seeding IS NOT NULL)),
    UNIQUE (id, group_id),
    FOREIGN KEY (night_id, group_id) REFERENCES play_nights (id, group_id)
        ON DELETE SET NULL (night_id)
);
CREATE INDEX events_group_idx ON events (group_id, created_at DESC);

CREATE TABLE event_players (
    event_id uuid NOT NULL,
    group_id uuid NOT NULL,
    player_id uuid NOT NULL,
    -- Ride the River's starting order (1 first). Never shown.
    start_rank smallint,
    joined_at timestamptz NOT NULL DEFAULT now(),
    left_at timestamptz,
    PRIMARY KEY (event_id, player_id),
    FOREIGN KEY (event_id, group_id) REFERENCES events (id, group_id) ON DELETE CASCADE,
    FOREIGN KEY (player_id, group_id) REFERENCES players (id, group_id) ON DELETE CASCADE
);

CREATE TABLE event_rounds (
    event_id uuid NOT NULL,
    group_id uuid NOT NULL,
    number smallint NOT NULL CHECK (number BETWEEN 1 AND 200),
    sitting_out uuid[] NOT NULL DEFAULT '{{}}' CHECK (cardinality(sitting_out) <= 24),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (event_id, number),
    FOREIGN KEY (event_id, group_id) REFERENCES events (id, group_id) ON DELETE CASCADE
);

CREATE TABLE event_courts (
    event_id uuid NOT NULL,
    group_id uuid NOT NULL,
    round smallint NOT NULL,
    court smallint NOT NULL CHECK (court BETWEEN 1 AND 6),
    team_a uuid[] NOT NULL CHECK (cardinality(team_a) = 2),
    team_b uuid[] NOT NULL CHECK (cardinality(team_b) = 2),
    match_id uuid UNIQUE,
    skipped boolean NOT NULL DEFAULT false,
    PRIMARY KEY (event_id, round, court),
    CHECK (NOT (skipped AND match_id IS NOT NULL)),
    FOREIGN KEY (event_id, round) REFERENCES event_rounds (event_id, number) ON DELETE CASCADE,
    FOREIGN KEY (event_id, group_id) REFERENCES events (id, group_id) ON DELETE CASCADE,
    -- Deleting the game empties the court again.
    FOREIGN KEY (match_id, group_id) REFERENCES matches (id, group_id)
        ON DELETE SET NULL (match_id)
);

ALTER TABLE matches ADD COLUMN event_id uuid;
ALTER TABLE matches ADD CONSTRAINT matches_event_fk FOREIGN KEY (event_id, group_id)
    REFERENCES events (id, group_id) ON DELETE SET NULL (event_id);
CREATE INDEX matches_event_idx ON matches (event_id) WHERE event_id IS NOT NULL;

ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE events FORCE ROW LEVEL SECURITY;
ALTER TABLE event_players ENABLE ROW LEVEL SECURITY;
ALTER TABLE event_players FORCE ROW LEVEL SECURITY;
ALTER TABLE event_rounds ENABLE ROW LEVEL SECURITY;
ALTER TABLE event_rounds FORCE ROW LEVEL SECURITY;
ALTER TABLE event_courts ENABLE ROW LEVEL SECURITY;
ALTER TABLE event_courts FORCE ROW LEVEL SECURITY;
REVOKE ALL ON events, event_players, event_rounds, event_courts FROM PUBLIC;

-- Everyone in the crew sees its events.
CREATE POLICY app_member_select ON events FOR SELECT TO {APP_ROLE}
    USING (app_is_member(group_id));
CREATE POLICY app_member_select ON event_players FOR SELECT TO {APP_ROLE}
    USING (app_is_member(group_id));
CREATE POLICY app_member_select ON event_rounds FOR SELECT TO {APP_ROLE}
    USING (app_is_member(group_id));
CREATE POLICY app_member_select ON event_courts FOR SELECT TO {APP_ROLE}
    USING (app_is_member(group_id));

-- Leads and co-leads create events, only while the format is switched on for the crew.
CREATE POLICY app_admin_insert ON events FOR INSERT TO {APP_ROLE}
    WITH CHECK (app_is_admin(group_id) AND created_by = app_current_user_id()
                AND app_feature_on('events.' || kind, group_id));
CREATE POLICY app_admin_update ON events FOR UPDATE TO {APP_ROLE}
    USING (app_is_admin(group_id)) WITH CHECK (app_is_admin(group_id));

-- Leads and co-leads run the event: players, rounds, courts.
CREATE POLICY app_admin_insert ON event_players FOR INSERT TO {APP_ROLE}
    WITH CHECK (app_is_admin(group_id));
CREATE POLICY app_admin_update ON event_players FOR UPDATE TO {APP_ROLE}
    USING (app_is_admin(group_id)) WITH CHECK (app_is_admin(group_id));
CREATE POLICY app_admin_insert ON event_rounds FOR INSERT TO {APP_ROLE}
    WITH CHECK (app_is_admin(group_id));
CREATE POLICY app_admin_insert ON event_courts FOR INSERT TO {APP_ROLE}
    WITH CHECK (app_is_admin(group_id));
-- Skipping a court. Scores are linked only by app_score_court below.
CREATE POLICY app_admin_update ON event_courts FOR UPDATE TO {APP_ROLE}
    USING (app_is_admin(group_id)) WITH CHECK (app_is_admin(group_id));
CREATE POLICY owner_definer_read ON event_courts FOR SELECT TO CURRENT_USER USING (true);
CREATE POLICY owner_definer_update ON event_courts FOR UPDATE TO CURRENT_USER
    USING (true) WITH CHECK (true);

-- Link a court to the game just logged for it. Anyone in the crew may fill a court with no
-- score; a skipped court only by a lead or co-lead. The game must be this event's, in this
-- crew, with exactly this court's two players on each side, so no other game can be
-- attached. Returns 'done', or why not: 'no_court', 'scored', 'skipped', 'wrong_game'.
CREATE FUNCTION app_score_court(target_event uuid, target_round smallint,
                                target_court smallint, new_match uuid) RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    c public.event_courts;
BEGIN
    SELECT * INTO c FROM public.event_courts ec
    WHERE ec.event_id = target_event AND ec.round = target_round AND ec.court = target_court
    FOR UPDATE;
    IF NOT FOUND OR NOT public.app_is_member(c.group_id) THEN
        RETURN 'no_court';
    END IF;
    IF c.match_id IS NOT NULL THEN
        RETURN 'scored';
    END IF;
    IF c.skipped AND NOT public.app_is_admin(c.group_id) THEN
        RETURN 'skipped';
    END IF;
    PERFORM 1 FROM public.matches m
    WHERE m.id = new_match AND m.group_id = c.group_id AND m.event_id = target_event
      AND (SELECT array_agg(mp.player_id ORDER BY mp.player_id) FROM public.match_players mp
           WHERE mp.match_id = m.id AND mp.team = 'A')
          = (SELECT array_agg(x ORDER BY x) FROM unnest(c.team_a) x)
      AND (SELECT array_agg(mp.player_id ORDER BY mp.player_id) FROM public.match_players mp
           WHERE mp.match_id = m.id AND mp.team = 'B')
          = (SELECT array_agg(x ORDER BY x) FROM unnest(c.team_b) x);
    IF NOT FOUND THEN
        RETURN 'wrong_game';
    END IF;
    UPDATE public.event_courts ec SET match_id = new_match, skipped = false
    WHERE ec.event_id = target_event AND ec.round = target_round AND ec.court = target_court;
    RETURN 'done';
END;
$$;

GRANT SELECT, INSERT, UPDATE (status, finished_at) ON events TO {APP_ROLE};
GRANT SELECT, INSERT, UPDATE (left_at) ON event_players TO {APP_ROLE};
GRANT SELECT, INSERT ON event_rounds TO {APP_ROLE};
GRANT SELECT, INSERT, UPDATE (skipped) ON event_courts TO {APP_ROLE};

INSERT INTO features (key, area, title, description, needs_plan, rollout) VALUES
    ('events.shuffle', 'events', 'Dink Shuffle',
     'Round robin with rotating partners: a new partner every round, fair sit-outs.',
     NULL, 'crews'),
    ('events.river', 'events', 'Ride the River',
     'Up and down the river: winners move up a court, losers move down, partners split.',
     'organizer', 'crews');
"""


FUNCTIONS = ["app_score_court(uuid, smallint, smallint, uuid)"]


def upgrade() -> None:
    op.execute(UPGRADE)
    for signature in FUNCTIONS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP_ROLE}")


def downgrade() -> None:
    op.execute("DROP FUNCTION app_score_court(uuid, smallint, smallint, uuid)")
    op.execute("DELETE FROM features WHERE key IN ('events.shuffle', 'events.river')")
    op.execute("ALTER TABLE matches DROP COLUMN event_id")
    op.execute("DROP TABLE event_courts")
    op.execute("DROP TABLE event_rounds")
    op.execute("DROP TABLE event_players")
    op.execute("DROP TABLE events")
