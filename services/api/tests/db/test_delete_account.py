"""Deleting your account and downloading your data (migration 0023, routes/me.py,
routes/export.py, ops/tick.py)."""

from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import ProgrammingError

from popshot_api.accounts import AccountDeleteError
from popshot_api.ops.tick import delete_accounts
from tests.db.conftest import People, as_user, create
from tests.db.test_direct_invites_api import code_of, person
from tests.db.test_games_api import join_and_approve, log, players
from tests.db.test_notifications_api import device
from tests.db.test_tick import jobs_engine  # noqa: F401  (a fixture)

pytestmark = pytest.mark.db

Headers = dict[str, str]


class FakeDeleter:
    def __init__(self, fail: bool = False) -> None:
        self.deleted: list[str] = []
        self.fail = fail

    def delete(self, subject: str) -> None:
        if self.fail:
            raise AccountDeleteError("Google said no")
        self.deleted.append(subject)


@pytest.fixture
def crew(people: People) -> dict[str, Any]:
    """Casey leads Lunch Dinkers with Sam and Jo. Sam logged a game against Casey."""
    casey = people.new("Casey")
    gid = create(people, casey, name="Lunch Dinkers")["id"]
    sam = join_and_approve(people, casey, gid, "Sam Field")
    jo = join_and_approve(people, casey, gid, "Jo")
    ids = {name.split()[0]: p["id"] for name, p in players(people, casey, gid).items()}
    logged = log(
        people,
        sam,
        gid,
        format="singles",
        team_a=[ids["Sam"]],
        team_b=[ids["Casey"]],
        games=[{"team_a": 11, "team_b": 8}],
    )
    assert logged.status_code == 201, logged.text
    return {"group_id": gid, "casey": casey, "sam": sam, "jo": jo, "ids": ids}


def ask_to_delete(people: People, who: Headers) -> Any:
    return people.client.post("/v1/me/delete", headers=who)


def backdate(owner_engine: Engine, user_id: UUID, days: int) -> None:
    with owner_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE popshot_owner"))
        conn.execute(
            text(
                "UPDATE users SET delete_requested_at = now() - CAST(:d AS interval) WHERE id = :u"
            ),
            {"d": f"{days} days", "u": user_id},
        )


def subject_of(owner_engine: Engine, user_id: UUID) -> str:
    with owner_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE popshot_owner"))
        subject: str = conn.execute(
            text("SELECT auth_subject FROM users WHERE id = :u"), {"u": user_id}
        ).scalar_one()
    return subject


def week_claims_of(owner_engine: Engine, user_id: UUID) -> int:
    with owner_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE popshot_owner"))
        count: int = conn.execute(
            text("SELECT count(*) FROM week_notifications WHERE user_id = :u"), {"u": user_id}
        ).scalar_one()
    return count


def test_asking_to_delete_and_changing_your_mind(people: People, crew: dict[str, Any]) -> None:
    asked = ask_to_delete(people, crew["sam"])
    assert asked.status_code == 200, asked.text
    me = asked.json()
    assert me["delete_requested_at"] is not None
    assert me["delete_on"] > me["delete_requested_at"]
    # Asking again keeps the first date.
    again = ask_to_delete(people, crew["sam"]).json()
    assert again["delete_requested_at"] == me["delete_requested_at"]
    kept = people.client.post("/v1/me/delete/cancel", headers=crew["sam"])
    assert kept.json()["delete_requested_at"] is None
    assert kept.json()["delete_on"] is None


def test_a_lead_hands_over_first(people: People, crew: dict[str, Any]) -> None:
    refused = ask_to_delete(people, crew["casey"])
    assert refused.status_code == 409
    assert "Lunch Dinkers" in refused.json()["detail"]
    # A crew you lead alone doesn't stop you.
    solo = people.new("Robin")
    create(people, solo, name="Robin's Practice")
    assert ask_to_delete(people, solo).status_code == 200


def test_after_seven_days_the_account_is_emptied_but_games_stay(
    people: People,
    crew: dict[str, Any],
    owner_engine: Engine,
    jobs_engine: Engine,  # noqa: F811
) -> None:
    gid = crew["group_id"]
    sam_id = people.user_id(crew["sam"])
    device(people, crew["sam"])
    people.client.put("/v1/me/focus", json={"strengths": [], "improve": []}, headers=crew["sam"])
    subject = subject_of(owner_engine, sam_id)
    # Sam played this week, so the Monday push claimed Sam.
    with jobs_engine.begin() as conn:
        conn.execute(
            text(
                "SELECT * FROM app_jobs_claim_week(current_date, now() - interval '7 days', "
                "now() + interval '1 hour')"
            )
        )
    assert week_claims_of(owner_engine, sam_id) == 1
    ask_to_delete(people, crew["sam"])

    # Not yet: 6 days in.
    backdate(owner_engine, sam_id, 6)
    deleter = FakeDeleter()
    assert delete_accounts(jobs_engine, deleter) == 0
    assert deleter.deleted == []

    backdate(owner_engine, sam_id, 8)
    assert delete_accounts(jobs_engine, deleter) == 1
    assert deleter.deleted == [subject]

    # The crew no longer lists Sam, but the game Sam logged and played is still there.
    detail = people.client.get(f"/v1/groups/{gid}", headers=crew["casey"]).json()
    assert "Sam Field" not in {m["display_name"] for m in detail["members"]}
    games = people.client.get(f"/v1/groups/{gid}/matches", headers=crew["casey"]).json()
    assert len(games) == 1
    assert "Former player" in repr(games[0])
    assert "Sam" not in repr(games[0])

    with owner_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE popshot_owner"))
        row = conn.execute(
            text(
                "SELECT display_name, avatar_url, auth_subject, deleted_at, invite_code "
                "FROM users WHERE id = :u"
            ),
            {"u": sam_id},
        ).one()
        devices = conn.execute(
            text("SELECT count(*) FROM push_subscriptions WHERE user_id = :u"), {"u": sam_id}
        ).scalar_one()
    assert row.display_name == "Former player"
    assert row.avatar_url is None
    assert row.auth_subject.startswith("deleted:")
    assert row.deleted_at is not None
    assert devices == 0
    assert week_claims_of(owner_engine, sam_id) == 0

    # Signing in with the old Google account starts a brand-new, empty account.
    fresh = people.client.get("/v1/me", headers=crew["sam"]).json()
    assert fresh["id"] != str(sam_id)
    assert people.client.get(f"/v1/groups/{gid}", headers=crew["sam"]).status_code == 404

    # Running again does nothing more.
    assert delete_accounts(jobs_engine, deleter) == 0


def test_a_failed_sign_in_delete_waits_for_the_next_run(
    people: People,
    crew: dict[str, Any],
    owner_engine: Engine,
    jobs_engine: Engine,  # noqa: F811
) -> None:
    sam_id = people.user_id(crew["sam"])
    ask_to_delete(people, crew["sam"])
    backdate(owner_engine, sam_id, 8)
    assert delete_accounts(jobs_engine, FakeDeleter(fail=True)) == 0
    # Still Sam: nothing was emptied.
    assert people.client.get("/v1/me", headers=crew["sam"]).json()["id"] == str(sam_id)
    assert delete_accounts(jobs_engine, FakeDeleter()) == 1


def test_crews_alone_go_and_crews_led_pass_on(
    people: People,
    crew: dict[str, Any],
    owner_engine: Engine,
    jobs_engine: Engine,  # noqa: F811
) -> None:
    casey_id = people.user_id(crew["casey"])
    alone = create(people, crew["casey"], name="Casey Solo")["id"]
    # Jo becomes co-lead; then Casey's request skips the hand-over check (set directly, as
    # if Sam and Jo joined after Casey asked).
    jo_id = people.user_id(crew["jo"])
    people.client.patch(
        f"/v1/groups/{crew['group_id']}/members/{jo_id}",
        json={"action": "make_co_lead"},
        headers=crew["casey"],
    )
    backdate(owner_engine, casey_id, 8)
    assert delete_accounts(jobs_engine, FakeDeleter()) == 1

    detail = people.client.get(f"/v1/groups/{crew['group_id']}", headers=crew["jo"]).json()
    assert detail["my_role"] == "lead"
    with owner_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE popshot_owner"))
        left = conn.execute(
            text("SELECT count(*) FROM groups WHERE id = :g"), {"g": alone}
        ).scalar_one()
    assert left == 0


def test_deleted_accounts_cant_be_invited(
    people: People,
    crew: dict[str, Any],
    owner_engine: Engine,
    jobs_engine: Engine,  # noqa: F811
) -> None:
    gid = crew["group_id"]
    sam_id = people.user_id(crew["sam"])
    ask_to_delete(people, crew["sam"])
    backdate(owner_engine, sam_id, 8)
    delete_accounts(jobs_engine, FakeDeleter())
    known = people.client.get(f"/v1/groups/{gid}/people", headers=crew["casey"]).json()
    assert str(sam_id) not in {p["user_id"] for p in known}
    assert "Former player" not in {p["display_name"] for p in known}


def test_only_the_job_can_purge(people: People, app_engine: Engine) -> None:
    riley = people.user_id(people.new("Riley"))
    for call in ("SELECT * FROM app_jobs_due_deletions()", "SELECT app_jobs_purge_user(NULL)"):
        with as_user(app_engine, riley) as conn, pytest.raises(ProgrammingError, match="denied"):
            conn.execute(text(call))


def test_download_your_data(people: People, crew: dict[str, Any]) -> None:
    response = people.client.get("/v1/me/export", headers=crew["sam"])
    assert response.status_code == 200, response.text
    assert "attachment" in response.headers["content-disposition"]
    data = response.json()
    assert data["profile"]["display_name"] == "Sam Field"
    assert [c["crew"] for c in data["crews"]] == ["Lunch Dinkers"]
    [game] = data["games"]
    assert game["scores"] == [[11, 8]]
    assert game["your_team"] == "A"
    # Only Sam's own notes and settings; nothing about another person's account.
    assert "email" not in repr(data["profile"])
    jo = people.client.get("/v1/me/export", headers=crew["jo"]).json()
    assert jo["games"] == []
    assert jo["profile"]["display_name"] == "Jo"
    # Someone found by code isn't in the exporter's file.
    stranger = people.new("Pat Quinn")
    person(people, crew["casey"], crew["group_id"], code_of(people, stranger))
    assert "Quinn" not in people.client.get("/v1/me/export", headers=crew["casey"]).text
