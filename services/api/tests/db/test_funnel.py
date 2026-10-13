"""The growth funnel (migration 0024, routes/funnel.py, routes/admin_funnel.py): where people
came from, anonymous visit counts, and the admin-only views of both."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, get_args
from uuid import UUID

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

from popshot_api.main import create_app
from popshot_api.routes.admin_funnel import stage_of
from popshot_api.routes.funnel import SignupSource, VisitPage
from tests.conftest import make_settings
from tests.db.conftest import (
    ADMIN,
    INSUFFICIENT_PRIVILEGE,
    Admins,
    People,
    as_user,
    create,
    sign_in,
    sqlstate_of,
)
from tests.db.test_games_api import add_guest, join_and_approve, log, players
from tests.db.test_tick import jobs_engine  # noqa: F401  (a fixture)

pytestmark = pytest.mark.db

Headers = dict[str, str]
FUNNEL_FUNCTIONS = [
    "SELECT * FROM app_admin_funnel_crews(now() - interval '1 day', now())",
    "SELECT * FROM app_admin_funnel_people(now() - interval '1 day', now())",
    "SELECT * FROM app_admin_funnel_sources(now() - interval '1 day', now())",
    "SELECT * FROM app_admin_funnel_loops(now() - interval '1 day', now())",
    "SELECT * FROM app_admin_crew_stages(30)",
]
# A window of its own for each test that rewinds time, far from anything else in the database.
BASE = datetime(2001, 2, 5, 12, tzinfo=UTC)


@pytest.fixture(scope="module")
def superuser(owner_engine: Engine) -> Iterator[Engine]:
    """Rewinds timestamps for the tests below. Row-level security doesn't apply to it."""
    admin = os.environ.get("POPSHOT_BOOTSTRAP_ADMIN_URL")
    if not admin:
        pytest.skip("POPSHOT_BOOTSTRAP_ADMIN_URL not set")
    url = make_url(admin).set(drivername="postgresql+psycopg", database=owner_engine.url.database)
    engine = create_engine(url, pool_size=1)
    yield engine
    engine.dispose()


def at(days: float) -> datetime:
    return BASE + timedelta(days=days)


def source_of(superuser: Engine, user_id: UUID) -> str | None:
    with superuser.connect() as conn:
        value: str | None = conn.execute(
            text("SELECT source FROM signup_sources WHERE user_id = :u"), {"u": user_id}
        ).scalar_one_or_none()
    return value


def visits(superuser: Engine, page: str, source: str) -> int:
    with superuser.connect() as conn:
        value = conn.execute(
            text(
                "SELECT coalesce(sum(visits), 0) FROM page_visits"
                " WHERE day = current_date AND page = :p AND source = :s"
            ),
            {"p": page, "s": source},
        ).scalar_one()
    return int(value)


def record(people: People, who: Headers, source: str) -> Any:
    return people.client.post("/v1/me/source", json={"source": source}, headers=who)


# --- Where people came from ------------------------------------------------------------


def test_a_new_account_records_its_source_once(people: People, superuser: Engine) -> None:
    riley = people.new("Riley")
    first = record(people, riley, "recap")
    assert first.status_code == 200, first.text
    assert first.json() == {"recorded": True}
    # The first one stays.
    assert record(people, riley, "reddit").json() == {"recorded": False}
    assert source_of(superuser, people.user_id(riley)) == "recap"


def test_only_a_new_account_gets_a_source(people: People, superuser: Engine) -> None:
    old = people.new("Morgan")
    old_id = people.user_id(old)
    with superuser.begin() as conn:
        conn.execute(
            text("UPDATE users SET created_at = now() - interval '2 days' WHERE id = :u"),
            {"u": old_id},
        )
    assert record(people, old, "poster").json() == {"recorded": False}
    assert source_of(superuser, old_id) is None


def test_unknown_sources_are_refused(people: People, app_engine: Engine) -> None:
    pat = people.new("Pat")
    assert record(people, pat, "<script>").status_code == 422
    assert record(people, pat, "x" * 500).status_code == 422
    # And straight to the database, as the API's role.
    with as_user(app_engine, people.user_id(pat)) as conn:
        assert conn.execute(text("SELECT app_set_signup_source('evil')")).scalar_one() is False


def test_your_data_download_has_your_source_and_nobody_elses(people: People) -> None:
    casey = people.new("Casey")
    gid = create(people, casey, "Source Crew")["id"]
    sam = join_and_approve(people, casey, gid, "Sam")
    record(people, casey, "nextdoor")
    record(people, sam, "facebook")
    assert people.client.get("/v1/me/export", headers=casey).json()["signup_source"] == "nextdoor"
    mine = people.client.get("/v1/me/export", headers=sam)
    assert mine.json()["signup_source"] == "facebook"
    assert "nextdoor" not in mine.text


def test_crewmates_and_the_app_cant_read_anyones_source(people: People, app_engine: Engine) -> None:
    casey = people.new("Casey")
    gid = create(people, casey, "Private Crew")["id"]
    sam = join_and_approve(people, casey, gid, "Sam")
    record(people, sam, "nextdoor")
    with as_user(app_engine, people.user_id(casey)) as conn:
        assert sqlstate_of(conn, "SELECT * FROM signup_sources") == INSUFFICIENT_PRIVILEGE
    with as_user(app_engine, people.user_id(casey)) as conn:
        # Someone else's, through the function for your own: just yours (none).
        assert conn.execute(text("SELECT app_my_signup_source()")).scalar_one() is None
    # Nothing the app returns mentions it.
    for path in ("/v1/me", f"/v1/groups/{gid}", f"/v1/groups/{gid}/players"):
        body = people.client.get(path, headers=casey).text
        assert "nextdoor" not in body
        assert "signup_source" not in body


def test_no_response_in_the_api_carries_a_source() -> None:
    """Only the data download (a plain JSON file, not a response model) includes it."""
    schemas = create_app(make_settings()).openapi()["components"]["schemas"]
    for name, schema in schemas.items():
        assert "signup_source" not in schema.get("properties", {}), name
    assert set(schemas["SourceRecorded"]["properties"]) == {"recorded"}


def test_deleting_an_account_forgets_its_source(people: People, superuser: Engine) -> None:
    jo = people.new("Jo")
    jo_id = people.user_id(jo)
    record(people, jo, "partner")
    with superuser.begin() as conn:
        conn.execute(text("UPDATE users SET deleted_at = now() WHERE id = :u"), {"u": jo_id})
    assert source_of(superuser, jo_id) is None


def test_the_lists_match_the_database(superuser: Engine) -> None:
    with superuser.connect() as conn:
        checks: dict[str, str] = dict(
            conn.execute(
                text(
                    "SELECT conrelid::regclass::text || '.' || conname,"
                    " pg_get_constraintdef(oid) FROM pg_constraint"
                    " WHERE conrelid IN ('signup_sources'::regclass, 'page_visits'::regclass)"
                    " AND contype = 'c'"
                )
            ).all()
        )
    sources = [d for k, d in checks.items() if k.startswith("signup_sources.")]
    pages = [d for d in checks.values() if "page" in d and "source" not in d]
    for value in get_args(SignupSource):
        assert f"'{value}'" in sources[0]
    for value in get_args(VisitPage):
        assert f"'{value}'" in pages[0]


# --- Anonymous visit counts ------------------------------------------------------------


def test_visits_are_counted_by_page_and_source(people: People, superuser: Engine) -> None:
    before = visits(superuser, "recap_try", "poster")
    for _ in range(2):
        sent = people.client.post(
            "/v1/public/visits", json={"page": "recap_try", "source": "poster"}
        )
        assert sent.status_code == 204, sent.text
    assert visits(superuser, "recap_try", "poster") == before + 2


def test_visits_accept_only_known_pages_and_sources(people: People, app_engine: Engine) -> None:
    for body in (
        {"page": "admin", "source": "direct"},
        {"page": "home", "source": "https://evil.example"},
        {"page": "home"},
    ):
        assert people.client.post("/v1/public/visits", json=body).status_code == 422
    with as_user(app_engine, None) as conn:
        assert conn.execute(text("SELECT app_count_visit('nope', 'direct')")).scalar_one() is False


def test_the_app_can_add_visits_but_never_read_them(app_engine: Engine) -> None:
    with as_user(app_engine, None) as conn:
        assert sqlstate_of(conn, "SELECT * FROM page_visits") == INSUFFICIENT_PRIVILEGE
    with as_user(app_engine, None) as conn:
        assert (
            sqlstate_of(
                conn,
                "INSERT INTO page_visits (day, page, source)"
                " VALUES (current_date, 'home', 'direct')",
            )
            == INSUFFICIENT_PRIVILEGE
        )


def test_old_visit_counts_are_purged(superuser: Engine, jobs_engine: Engine) -> None:  # noqa: F811
    with superuser.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO page_visits (day, page, source, visits)"
                " VALUES (current_date - interval '14 months', 'home', 'court', 3)"
                " ON CONFLICT DO NOTHING"
            )
        )
    with jobs_engine.begin() as conn:
        assert conn.execute(text("SELECT app_jobs_purge_visits()")).scalar_one() >= 1
    with superuser.connect() as conn:
        left = conn.execute(
            text("SELECT count(*) FROM page_visits WHERE day < current_date - interval '13 months'")
        ).scalar_one()
    assert left == 0


# --- Admin only ------------------------------------------------------------------------


@pytest.mark.parametrize("call", FUNNEL_FUNCTIONS)
def test_only_the_admin_role_can_run_the_funnel(
    call: str,
    app_engine: Engine,
    jobs_engine: Engine,  # noqa: F811
    admin_engine: Engine,
) -> None:
    for engine in (app_engine, jobs_engine):
        with engine.connect() as conn:
            assert sqlstate_of(conn, call) == INSUFFICIENT_PRIVILEGE
    with admin_engine.connect() as conn:
        conn.execute(text(call)).all()


def test_the_api_cant_purge_visits(app_engine: Engine) -> None:
    with app_engine.connect() as conn:
        assert sqlstate_of(conn, "SELECT app_jobs_purge_visits()") == INSUFFICIENT_PRIVILEGE


def test_the_funnel_page_is_for_admins_only(admins: Admins) -> None:
    someone = admins.new("Casey")
    assert admins.admin.get("/v1/admin/funnel", headers=someone).status_code == 404
    assert admins.admin.get("/v1/admin/funnel").status_code == 401
    # The main API has no such page, even for the admin.
    boss = sign_in(admins, ADMIN.lower())
    assert admins.client.get("/v1/admin/funnel", headers=boss).status_code == 404


def test_the_funnel_page(admins: Admins, owner_engine: Engine) -> None:
    casey = admins.new("Casey")
    gid = create(admins, casey, "Brand New Crew")["id"]
    boss = sign_in(admins, ADMIN.lower())
    response = admins.admin.get("/v1/admin/funnel?weeks=8", headers=boss)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["weeks"] == 8
    assert body["crews"]["created"] >= 1
    assert len(body["active_crews"]) == 8
    mine = next(s for s in body["stages"] if s["id"] == gid)
    assert mine["stage"] == "needs_member"
    for wrong in ("5", "16", "0", "x"):
        assert admins.admin.get(f"/v1/admin/funnel?weeks={wrong}", headers=boss).status_code == 422
    with owner_engine.connect() as conn:
        conn.execute(text("SET LOCAL ROLE popshot_owner"))
        seen = conn.execute(
            text("SELECT count(*) FROM admin_views WHERE page = 'funnel'")
        ).scalar_one()
    assert seen >= 1


# --- The numbers -----------------------------------------------------------------------


def funnel(admin_engine: Engine, name: str, since: datetime, until: datetime) -> Any:
    with admin_engine.connect() as conn:
        return conn.execute(
            text(f"SELECT * FROM {name}(:since, :until)"), {"since": since, "until": until}
        ).all()


def rewind_crew(superuser: Engine, gid: str, created: datetime, games: list[datetime]) -> None:
    """Move a crew, its members' joins and its games (oldest first) back in time."""
    with superuser.begin() as conn:
        conn.execute(
            text("UPDATE groups SET created_at = :t WHERE id = :g"), {"t": created, "g": gid}
        )
        conn.execute(
            text("UPDATE players SET created_at = :t WHERE group_id = :g"),
            {"t": created + timedelta(hours=2), "g": gid},
        )
        ids = conn.execute(
            text("SELECT id FROM matches WHERE group_id = :g ORDER BY created_at, id"), {"g": gid}
        ).scalars()
        for match_id, when in zip(ids, games, strict=True):
            conn.execute(
                text("UPDATE matches SET created_at = :t WHERE id = :m"), {"t": when, "m": match_id}
            )


def singles(people: People, lead: Headers, gid: str, times: int) -> None:
    add_guest(people, lead, gid, "Gary")
    ids = {name.split()[0]: p["id"] for name, p in players(people, lead, gid).items()}
    lead_name = next(n for n in ids if n != "Gary")
    for _ in range(times):
        logged = log(
            people,
            lead,
            gid,
            format="singles",
            team_a=[ids[lead_name]],
            team_b=[ids["Gary"]],
        )
        assert logged.status_code == 201, logged.text


def test_the_crew_funnel_steps(people: People, superuser: Engine, admin_engine: Engine) -> None:
    # A: two members, 3 games in its first week, back in weeks 2 and 4.
    alex = people.new("Alex")
    a = create(people, alex, "Crew A")["id"]
    join_and_approve(people, alex, a, "Bea")
    singles(people, alex, a, 5)
    rewind_crew(superuser, a, at(0), [at(1), at(2), at(3), at(9), at(23)])
    # B: one member, one game on day 2 with a guest.
    cam = people.new("Cam")
    b = create(people, cam, "Crew B")["id"]
    singles(people, cam, b, 1)
    rewind_crew(superuser, b, at(0.5), [at(2.5)])
    # C: nothing yet.
    dee = people.new("Dee")
    c = create(people, dee, "Crew C")["id"]
    rewind_crew(superuser, c, at(1), [])

    [row] = funnel(admin_engine, "app_admin_funnel_crews", at(-1), at(3))
    assert row.created == 3
    assert row.second_member == 1
    assert row.first_game == 2
    assert row.activated == 1
    assert row.week_2_eligible == 3
    assert row.played_week_2 == 1
    assert row.week_4_eligible == 3
    assert row.played_week_4 == 1
    # A took 24 hours to its first game, B 48.
    assert row.median_hours_to_first_game == pytest.approx(36)


def test_the_people_funnel_and_sources(
    people: People, superuser: Engine, admin_engine: Engine
) -> None:
    eve = people.new("Eve")  # joins a crew and plays, back in week 2: from a recap
    fin = people.new("Fin")  # signs up and does nothing: from reddit
    gid = create(people, eve, "People Crew")["id"]
    singles(people, eve, gid, 1)
    record(people, eve, "recap")
    record(people, fin, "reddit")
    eve_id, fin_id = people.user_id(eve), people.user_id(fin)
    start = BASE + timedelta(days=100)
    rewind_crew(superuser, gid, start, [start + timedelta(days=1)])
    with superuser.begin() as conn:
        conn.execute(
            text("UPDATE users SET created_at = :t WHERE id IN (:e, :f)"),
            {"t": start, "e": eve_id, "f": fin_id},
        )
        conn.execute(
            text("INSERT INTO user_activity (user_id, day) VALUES (:e, :d)"),
            {"e": eve_id, "d": (start + timedelta(days=9)).date()},
        )
        conn.execute(
            text(
                "INSERT INTO page_visits (day, page, source, visits) VALUES"
                " (:d, 'home', 'reddit', 40), (:d, 'home', 'recap', 7),"
                " (:d, 'recap', 'direct', 25), (:d, 'recap_try', 'direct', 9)"
            ),
            {"d": start.date()},
        )
    since, until = start - timedelta(days=1), start + timedelta(days=1)

    [row] = funnel(admin_engine, "app_admin_funnel_people", since, until)
    assert (row.signed_up, row.in_crew, row.played) == (2, 1, 1)
    assert (row.week_2_eligible, row.back_week_2) == (2, 1)

    sources = {s.source: s for s in funnel(admin_engine, "app_admin_funnel_sources", since, until)}
    assert (sources["recap"].visits, sources["recap"].signed_up, sources["recap"].played) == (
        7,
        1,
        1,
    )
    assert (sources["reddit"].visits, sources["reddit"].signed_up, sources["reddit"].in_crew) == (
        40,
        1,
        0,
    )

    [loops] = funnel(admin_engine, "app_admin_funnel_loops", since, until)
    assert (loops.share_views, loops.try_taps, loops.recap_signups) == (25, 9, 1)


def test_crew_stages() -> None:
    now = datetime(2026, 10, 13, tzinfo=UTC)
    recent = now - timedelta(days=2)
    old = now - timedelta(days=20)

    def stage(**kw: Any) -> str:
        args: dict[str, Any] = {
            "deleted": False,
            "members": 2,
            "games": 1,
            "games_first_week": 1,
            "last_game_at": recent,
            "now": now,
        }
        args.update(kw)
        return stage_of(**args)

    assert stage(deleted=True) == "deleted"
    assert stage(members=1, games=0, last_game_at=None) == "needs_member"
    assert stage(games=0, last_game_at=None) == "needs_first_game"
    # Playing with guests only still counts as playing.
    assert stage(members=1) == "getting_going"
    assert stage(games=4, games_first_week=3) == "activated"
    assert stage(games=4, games_first_week=3, last_game_at=old) == "quiet"
