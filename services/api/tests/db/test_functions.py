"""The SECURITY DEFINER entry points: sign-in, creating a group, redeeming invites."""

from uuid import UUID

import pytest
from sqlalchemy import Connection, Engine, text

from tests.db.conftest import INSUFFICIENT_PRIVILEGE, Seed, as_user, new_token_hash, sqlstate_of

pytestmark = pytest.mark.db


def _invite(conn: Connection, seed: Seed, **overrides: object) -> bytes:
    token_hash = new_token_hash()
    values = {
        "expires_at": "now() + interval '1 day'",
        "max_uses": "1",
        "requires_approval": "true",
        "revoked_at": "NULL",
    }
    values.update({k: str(v) for k, v in overrides.items()})
    conn.execute(
        text(
            "INSERT INTO group_invites (group_id, token_hash, created_by, expires_at, max_uses, "
            f"requires_approval, revoked_at) VALUES (:g, :h, :u, {values['expires_at']}, "
            f"{values['max_uses']}, {values['requires_approval']}, {values['revoked_at']})"
        ),
        {"g": seed.group_a, "h": token_hash, "u": seed.alice},
    )
    return token_hash


def _redeem(conn: Connection, user: UUID, token_hash: bytes) -> list[tuple[UUID, str]]:
    conn.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": str(user)})
    rows = conn.execute(text("SELECT * FROM app_redeem_invite(:h)"), {"h": token_hash})
    return [(r.group_id, r.status) for r in rows]


def _as_alice(conn: Connection, seed: Seed) -> None:
    conn.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": str(seed.alice)})


def test_resolve_user_is_stable_and_keeps_profile(app_engine: Engine) -> None:
    with as_user(app_engine, None) as conn:
        first = conn.execute(text("SELECT app_resolve_user('sub-stable', 'Pat', NULL)"))
        first_id = first.scalar_one()
        again = conn.execute(text("SELECT app_resolve_user('sub-stable', 'Changed', NULL)"))
        assert again.scalar_one() == first_id
        conn.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": str(first_id)})
        name = conn.execute(text("SELECT display_name FROM users")).scalar_one()
        assert name == "Pat"


def test_resolve_user_rejects_bad_profile(app_engine: Engine) -> None:
    with as_user(app_engine, None) as conn:
        bad_avatar = "SELECT app_resolve_user('sub-x', 'Pat', 'javascript:alert(1)')"
        assert sqlstate_of(conn, bad_avatar) == "23514"
        assert sqlstate_of(conn, "SELECT app_resolve_user('', 'Pat', NULL)") == "23514"


def test_create_group_needs_a_user(app_engine: Engine) -> None:
    with as_user(app_engine, None) as conn:
        state = sqlstate_of(conn, "SELECT app_create_group('X', 'doubles', 11::smallint, true)")
        assert state == INSUFFICIENT_PRIVILEGE


def test_create_group_makes_you_lead_and_player(app_engine: Engine, seed: Seed) -> None:
    with as_user(app_engine, seed.nobody) as conn:
        group = conn.execute(
            text("SELECT app_create_group('  Lunch League ', 'singles', 21::smallint, false)")
        ).scalar_one()
        row = conn.execute(text("SELECT name, default_points_to FROM groups")).one()
        assert (row.name, row.default_points_to) == ("Lunch League", 21)
        member = conn.execute(text("SELECT role, status FROM group_members")).one()
        assert (member.role, member.status) == ("lead", "active")
        players = conn.execute(text("SELECT group_id, user_id FROM players")).all()
        assert [(p.group_id, p.user_id) for p in players] == [(group, seed.nobody)]


@pytest.mark.parametrize(
    "overrides",
    [
        {"expires_at": "now() - interval '1 second'"},
        {"revoked_at": "now()"},
    ],
    ids=["expired", "revoked"],
)
def test_dead_invites_do_nothing(app_engine: Engine, seed: Seed, overrides: dict[str, str]) -> None:
    with as_user(app_engine, seed.alice) as conn:
        token_hash = _invite(conn, seed, **overrides)
        assert _redeem(conn, seed.nobody, token_hash) == []
        assert conn.execute(text("SELECT count(*) FROM group_members")).scalar_one() == 0


def test_unknown_invite_does_nothing(app_engine: Engine, seed: Seed) -> None:
    with as_user(app_engine, seed.nobody) as conn:
        assert _redeem(conn, seed.nobody, new_token_hash()) == []


def test_single_use_invite_is_used_up(app_engine: Engine, seed: Seed) -> None:
    with as_user(app_engine, seed.alice) as conn:
        token_hash = _invite(conn, seed, max_uses=1, requires_approval="false")
        assert _redeem(conn, seed.nobody, token_hash) == [(seed.group_a, "active")]
        assert _redeem(conn, seed.bob, token_hash) == []


def test_invite_needing_approval_makes_you_pending(app_engine: Engine, seed: Seed) -> None:
    with as_user(app_engine, seed.alice) as conn:
        token_hash = _invite(conn, seed)
        assert _redeem(conn, seed.nobody, token_hash) == [(seed.group_a, "pending")]
        assert conn.execute(text("SELECT count(*) FROM matches")).scalar_one() == 0


def test_existing_membership_is_unchanged_and_invite_not_used(
    app_engine: Engine, seed: Seed
) -> None:
    with as_user(app_engine, seed.alice) as conn:
        token_hash = _invite(conn, seed, max_uses=1, requires_approval="false")
        # Frank was removed; an invite doesn't bring him back.
        assert _redeem(conn, seed.frank, token_hash) == [(seed.group_a, "removed")]
        assert _redeem(conn, seed.carol, token_hash) == [(seed.group_a, "active")]
        _as_alice(conn, seed)
        used = conn.execute(
            text("SELECT use_count FROM group_invites WHERE token_hash = :h"), {"h": token_hash}
        ).scalar_one()
        assert used == 0


def test_redeem_needs_a_user(app_engine: Engine) -> None:
    with as_user(app_engine, None) as conn:
        state = sqlstate_of(conn, "SELECT * FROM app_redeem_invite(:h)", {"h": new_token_hash()})
        assert state == INSUFFICIENT_PRIVILEGE


def _preview(conn: Connection, user: UUID | None, token_hash: bytes) -> list[tuple[object, ...]]:
    value = "" if user is None else str(user)
    conn.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": value})
    rows = conn.execute(text("SELECT * FROM app_preview_invite(:h)"), {"h": token_hash})
    return [tuple(r) for r in rows]


def test_preview_needs_a_user_and_a_live_invite(app_engine: Engine, seed: Seed) -> None:
    with as_user(app_engine, seed.alice) as conn:
        live = _invite(conn, seed)
        dead = _invite(conn, seed, revoked_at="now()")
        assert _preview(conn, None, live) == []
        assert _preview(conn, seed.nobody, live) == [(None, "Tuesday Crew", "Alice", None)]
        assert _preview(conn, seed.nobody, dead) == []
        assert _preview(conn, seed.nobody, new_token_hash()) == []
        # Someone already in the group still sees it through a dead link, with its ID.
        assert _preview(conn, seed.carol, dead) == [
            (seed.group_a, "Tuesday Crew", "Alice", "active")
        ]
        # Someone removed sees their status but not the ID.
        assert _preview(conn, seed.frank, dead) == [(None, "Tuesday Crew", "Alice", "removed")]


def test_used_up_link_still_answers_the_person_who_used_it(app_engine: Engine, seed: Seed) -> None:
    with as_user(app_engine, seed.alice) as conn:
        token_hash = _invite(conn, seed, max_uses=1)
        assert _redeem(conn, seed.nobody, token_hash) == [(seed.group_a, "pending")]
        assert _redeem(conn, seed.nobody, token_hash) == [(seed.group_a, "pending")]
        assert _redeem(conn, seed.bob, token_hash) == []
