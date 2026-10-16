"""Open crews (migration 0036, routes/open_crews.py and routes/admin_open_crews.py).

Each crew gets its own made-up place at a random spot, far from everyone else's, so the
listing in one test never sees another test's crews. Each test puts its own crews on the
crew.open list.
"""

import secrets
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError, ProgrammingError

from popshot_api.admin_main import create_admin_app
from popshot_api.main import create_app
from popshot_api.routes.admin_actions import FRESH_SIGN_IN
from tests.conftest import make_settings
from tests.db.conftest import ADMIN, Admins, as_user, create, sign_in
from tests.db.test_events_api import Lists, lists  # noqa: F401  (a fixture)
from tests.db.test_features import owner
from tests.db.test_games_api import join_and_approve
from tests.db.test_notifications_api import RecordingSender, device
from tests.fakes import FakeTokenVerifier

pytestmark = pytest.mark.db

Headers = dict[str, str]
FEATURE = "crew.open"
REASON = "Listing reported as spam twice; checked it."


@pytest.fixture
def sender() -> RecordingSender:
    return RecordingSender()


@pytest.fixture
def admins(app_engine: Engine, admin_engine: Engine, sender: RecordingSender) -> Iterator[Admins]:
    """People on the API (with pushes recorded) and the admin service, sharing a verifier."""
    verifier = FakeTokenVerifier()
    settings = make_settings(admin_emails=ADMIN)
    with (
        TestClient(create_app(settings, verifier, app_engine, push_sender=sender)) as client,
        TestClient(create_admin_app(settings, verifier, admin_engine)) as admin,
    ):
        yield Admins(client, verifier, admin)


@pytest.fixture
def boss(admins: Admins) -> Headers:
    return sign_in(admins, ADMIN.lower())


class Crews:
    """Crews with a court on the map at a spot of their own, on the crew.open list."""

    def __init__(self, people: Admins, owner_engine: Engine, lists: Lists) -> None:  # noqa: F811
        self.people = people
        self.owner_engine = owner_engine
        self.lists = lists
        self.places: list[str] = []

    def spot(self) -> tuple[float, float]:
        # Somewhere no other test's crew is: a random point, away from the poles.
        pick = secrets.SystemRandom()
        return round(pick.uniform(-60, 60), 4), round(pick.uniform(-170, 170), 4)

    def new(
        self,
        name: str = "Court Crew",
        *,
        at: tuple[float, float] | None = None,
        switch: bool = True,
    ) -> dict[str, Any]:
        lead = self.people.new("Casey")
        gid = create(self.people, lead, name)["id"]
        lat, lng = at or self.spot()
        crew = {"gid": gid, "lead": lead, "lat": lat, "lng": lng}
        # Its first court, so its default: one from the map.
        crew["place"] = self.court(crew, "Riverside courts", at=(lat, lng))
        if switch:
            self.lists.add(FEATURE, gid)
        return crew

    def court(
        self, crew: dict[str, Any], label: str, *, at: tuple[float, float] | None = None
    ) -> str | None:
        """Save a court for the crew as if its lead had: from the map when `at` is given,
        typed otherwise. Returns its Google ID, if any."""
        place, place_id = None, None
        with owner(self.owner_engine) as conn:
            if at is not None:
                place = f"test-{uuid4().hex}"
                place_id = conn.execute(
                    text(
                        "INSERT INTO places (google_place_id, lat, lng, coords_at) "
                        "VALUES (:p, :lat, :lng, now()) RETURNING id"
                    ),
                    {"p": place, "lat": at[0], "lng": at[1]},
                ).scalar_one()
                self.places.append(place)
            conn.execute(
                text(
                    "INSERT INTO crew_courts (group_id, place_id, label, created_by) "
                    "VALUES (:g, :p, :label, :by)"
                ),
                {
                    "g": crew["gid"],
                    "p": place_id,
                    "label": label,
                    "by": self.people.user_id(crew["lead"]),
                },
            )
        return place

    def court_id(self, crew: dict[str, Any], label: str) -> str:
        group = self.people.client.get(f"/v1/groups/{crew['gid']}", headers=crew["lead"]).json()
        [found] = [c["id"] for c in group["courts"] if c["label"] == label]
        return str(found)

    def make_default(self, crew: dict[str, Any], label: str) -> Any:
        return self.people.client.patch(
            f"/v1/groups/{crew['gid']}/courts/{self.court_id(crew, label)}",
            json={"is_default": True},
            headers=crew["lead"],
        )

    def open(self, crew: dict[str, Any], **body: Any) -> Any:
        return self.people.client.put(
            f"/v1/groups/{crew['gid']}/open",
            json={"open": True, **body},
            headers=crew["lead"],
        )

    def cleanup(self) -> None:
        with owner(self.owner_engine) as conn:
            conn.execute(
                text(
                    "DELETE FROM crew_courts WHERE place_id IN "
                    "(SELECT id FROM places WHERE google_place_id = ANY(:p))"
                ),
                {"p": self.places},
            )
            conn.execute(
                text("DELETE FROM places WHERE google_place_id = ANY(:p)"), {"p": self.places}
            )


@pytest.fixture
def crews(admins: Admins, owner_engine: Engine, lists: Lists) -> Iterator[Crews]:  # noqa: F811
    made = Crews(admins, owner_engine, lists)
    yield made
    made.cleanup()


def staff_did(owner_engine: Engine, action: str, group_id: str) -> list[dict[str, Any]]:
    with owner(owner_engine) as conn:
        rows = conn.execute(
            text(
                "SELECT reason, details FROM admin_actions WHERE action = :a AND group_id = :g "
                "ORDER BY id"
            ),
            {"a": action, "g": group_id},
        ).all()
    return [{"reason": r.reason, "details": r.details} for r in rows]


def search(people: Admins, who: Headers, crew: dict[str, Any], **over: Any) -> list[dict[str, Any]]:
    body = {"lat": crew["lat"], "lng": crew["lng"], **over}
    response = people.client.post("/v1/open-crews/search", json=body, headers=who)
    assert response.status_code == 200, response.text
    found: list[dict[str, Any]] = response.json()
    return found


def join(people: Admins, who: Headers, crew: dict[str, Any]) -> Any:
    return people.client.post(f"/v1/open-crews/{crew['gid']}/join", headers=who)


def report(people: Admins, who: Headers, crew: dict[str, Any], **body: Any) -> Any:
    return people.client.post(
        f"/v1/open-crews/{crew['gid']}/report", json={"reason": "spam", **body}, headers=who
    )


def test_a_lead_opens_the_crew_and_strangers_find_only_the_listing(
    admins: Admins, crews: Crews
) -> None:
    crew = crews.new("Tuesday Dinkers")
    join_and_approve(admins, crew["lead"], crew["gid"], "Sam Rivera")
    opened = crews.open(crew, max_members=8)
    assert opened.status_code == 200, opened.text
    assert (opened.json()["open_to_all"], opened.json()["max_members"]) == (True, 8)

    riley = admins.new("Riley")
    [found] = search(admins, riley, crew)
    assert found == {
        "group_id": crew["gid"],
        "name": "Tuesday Dinkers",
        "about": None,
        "usual_days": [],
        "usual_times": [],
        "court": "Riverside courts",
        "google_place_id": crew["place"],
        "distance_km": 0.0,
        "members": 2,
        "max_members": 8,
        "full": False,
        "my_status": None,
    }
    # Nobody's name in it.
    assert "Sam" not in str(found)
    assert "Casey" not in str(found)
    # About 55 km north: in a 100 km search, not in the 25 km one.
    north = {"lat": crew["lat"] + 0.5, "lng": crew["lng"]}
    assert search(admins, riley, crew, **north) == []
    [far] = search(admins, riley, crew, **north, radius_km=100)
    assert 54 < far["distance_km"] < 57
    # Members see that they're in.
    assert search(admins, crew["lead"], crew)[0]["my_status"] == "active"


def test_where_you_search_from_is_checked(admins: Admins) -> None:
    riley = admins.new("Riley")
    for body in (
        {"lat": 91, "lng": 0},
        {"lat": 0, "lng": 181},
        {"lat": 0, "lng": 0, "radius_km": 101},
        {"lat": 0, "lng": 0, "radius_km": 0},
        {"lat": 0, "lng": 0, "near": "home"},
    ):
        response = admins.client.post("/v1/open-crews/search", json=body, headers=riley)
        assert response.status_code == 422, body


def test_only_a_lead_with_the_switch_and_a_court_can_open(
    admins: Admins, crews: Crews, owner_engine: Engine
) -> None:
    crew = crews.new()
    sam = join_and_approve(admins, crew["lead"], crew["gid"], "Sam")
    path = f"/v1/groups/{crew['gid']}/open"
    assert admins.client.put(path, json={"open": True}, headers=sam).status_code == 403
    assert (
        admins.client.put(path, json={"open": True}, headers=admins.new("Pat")).status_code == 404
    )
    for cap in (1, 101):
        assert crews.open(crew, max_members=cap).status_code == 422
    # Without the switch, it isn't there.
    off = crews.new(switch=False)
    assert crews.open(off).status_code == 404
    # Its default court must be one from the map: a typed default can't be listed.
    crews.court(crew, "Hall")
    assert crews.make_default(crew, "Hall").status_code == 200
    response = crews.open(crew)
    assert (response.status_code, response.json()["detail"]) == (
        409,
        "Make a court from the map the crew's default first.",
    )
    # Nor can no court at all.
    with owner(owner_engine) as conn:
        conn.execute(text("DELETE FROM crew_courts WHERE group_id = :g"), {"g": crew["gid"]})
    assert crews.open(crew).status_code == 409


def test_joining_is_instant_and_the_leads_hear(
    admins: Admins,
    crews: Crews,
    sender: RecordingSender,
    app_engine: Engine,
    owner_engine: Engine,
) -> None:
    crew = crews.new("Court Crew")
    sam = join_and_approve(admins, crew["lead"], crew["gid"], "Sam")
    lead_phone = device(admins, crew["lead"])
    sam_phone = device(admins, sam)
    assert crews.open(crew).status_code == 200
    riley = admins.new("Riley Stone")
    sender.sent.clear()

    joined = join(admins, riley, crew)
    assert joined.status_code == 200, joined.text
    body = joined.json()
    assert (body["outcome"], body["group"]["my_status"], body["group"]["my_role"]) == (
        "joined",
        "active",
        "member",
    )
    # A player at once, so Riley can be put in games.
    names = {p["display_name"] for p in body["group"]["members"]}
    assert "Riley Stone" in names
    # The lead hears, by first name; members don't.
    assert [endpoint for endpoint, _ in sender.sent] == [lead_phone]
    assert sender.sent[0][1].title == "Riley joined Court Crew"
    assert sam_phone not in [endpoint for endpoint, _ in sender.sent]
    assert join(admins, riley, crew).json()["outcome"] == "already"
    assert len(sender.sent) == 1
    # The crew's log says how Riley came in; leads read it.
    with as_user(app_engine, admins.user_id(crew["lead"])) as conn:
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM audit_log "
                    "WHERE group_id = :g AND action = 'member.joined_open'"
                ),
                {"g": crew["gid"]},
            ).scalar_one()
            == 1
        )
    with owner(owner_engine) as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM players WHERE group_id = :g AND user_id = :u"),
                {"g": crew["gid"], "u": admins.user_id(riley)},
            ).scalar_one()
            == 1
        )


def test_a_full_crew_takes_nobody_from_the_listing_but_invites_still_work(
    admins: Admins, crews: Crews
) -> None:
    crew = crews.new()
    join_and_approve(admins, crew["lead"], crew["gid"], "Sam")
    assert crews.open(crew, max_members=2).status_code == 200
    riley = admins.new("Riley")
    assert search(admins, riley, crew)[0]["full"] is True
    full = join(admins, riley, crew)
    assert (full.status_code, full.json()["detail"]) == (409, "This crew is full right now.")
    # The cap is only for the listing: the lead can still bring someone in.
    join_and_approve(admins, crew["lead"], crew["gid"], "Pat")


def test_someone_a_lead_removed_cant_find_or_join_but_someone_who_left_can(
    admins: Admins, crews: Crews
) -> None:
    crew = crews.new()
    sam = join_and_approve(admins, crew["lead"], crew["gid"], "Sam")
    pat = join_and_approve(admins, crew["lead"], crew["gid"], "Pat")
    assert crews.open(crew).status_code == 200
    removed = admins.client.patch(
        f"/v1/groups/{crew['gid']}/members/{admins.user_id(sam)}",
        json={"action": "remove"},
        headers=crew["lead"],
    )
    assert removed.status_code == 200, removed.text
    assert search(admins, sam, crew) == []
    assert join(admins, sam, crew).status_code == 404
    # Pat leaves, then changes their mind.
    assert admins.client.post(f"/v1/groups/{crew['gid']}/leave", headers=pat).status_code == 204
    assert search(admins, pat, crew)[0]["my_status"] is None
    assert join(admins, pat, crew).json()["outcome"] == "joined"


def test_someone_waiting_on_a_link_can_join_at_once(admins: Admins, crews: Crews) -> None:
    crew = crews.new()
    assert crews.open(crew).status_code == 200
    wren = admins.new("Wren")
    token = admins.client.post(
        f"/v1/groups/{crew['gid']}/invites", json={}, headers=crew["lead"]
    ).json()["token"]
    admins.client.post("/v1/invites/join", json={"token": token}, headers=wren)
    assert search(admins, wren, crew)[0]["my_status"] == "pending"
    assert join(admins, wren, crew).json()["group"]["my_status"] == "active"


def test_closed_switched_off_and_deleted_crews_arent_listed(
    admins: Admins,
    crews: Crews,
    lists: Lists,  # noqa: F811
) -> None:
    riley = admins.new("Riley")
    closed = crews.new()
    assert crews.open(closed).status_code == 200
    assert (
        admins.client.put(
            f"/v1/groups/{closed['gid']}/open", json={"open": False}, headers=closed["lead"]
        ).json()["open_to_all"]
        is False
    )
    assert search(admins, riley, closed) == []
    assert join(admins, riley, closed).status_code == 404

    switched = crews.new()
    assert crews.open(switched).status_code == 200
    lists.remove(FEATURE, switched["gid"])
    assert search(admins, riley, switched) == []
    assert join(admins, riley, switched).status_code == 404

    deleted = crews.new()
    assert crews.open(deleted).status_code == 200
    gone = admins.client.delete(f"/v1/groups/{deleted['gid']}", headers=deleted["lead"])
    assert gone.status_code == 204, gone.text
    assert search(admins, riley, deleted) == []
    assert join(admins, riley, deleted).status_code == 404
    assert join(admins, riley, {"gid": str(uuid4())}).status_code == 404


def listed(admins: Admins, crew: dict[str, Any]) -> bool:
    found = admins.client.post(
        "/v1/open-crews/search",
        json={"lat": crew["lat"], "lng": crew["lng"], "radius_km": 1},
        headers=admins.new("Riley"),
    ).json()
    return crew["gid"] in [c["group_id"] for c in found]


def test_a_typed_default_court_closes_the_crew_and_tells_its_leads(
    admins: Admins, crews: Crews
) -> None:
    crew = crews.new()
    crews.court(crew, "Hall")
    # Switching the default to another court from the map keeps it open: for a moment while
    # it switches the crew has no default, but the rule is checked when the change is saved.
    crews.court(crew, "Sunset courts", at=(crew["lat"], crew["lng"]))
    assert crews.open(crew).status_code == 200
    kept = crews.make_default(crew, "Sunset courts").json()
    assert (kept["open_to_all"], kept["closed_for_court"]) == (True, False)
    assert listed(admins, crew)

    closed = crews.make_default(crew, "Hall")
    assert closed.status_code == 200
    assert (closed.json()["open_to_all"], closed.json()["closed_for_court"]) == (False, True)
    assert not listed(admins, crew)
    # Making a court from the map the default again doesn't reopen it: the lead does.
    assert crews.make_default(crew, "Riverside courts").json()["open_to_all"] is False
    reopened = crews.open(crew).json()
    assert (reopened["open_to_all"], reopened["closed_for_court"]) == (True, False)
    assert listed(admins, crew)


def test_removing_the_default_court_from_the_map_closes_the_crew(
    admins: Admins, crews: Crews
) -> None:
    crew = crews.new()
    crews.court(crew, "Hall")
    assert crews.open(crew).status_code == 200
    # The default passes to Hall, a typed court.
    gone = admins.client.delete(
        f"/v1/groups/{crew['gid']}/courts/{crews.court_id(crew, 'Riverside courts')}",
        headers=crew["lead"],
    )
    assert gone.status_code == 200
    assert (gone.json()["open_to_all"], gone.json()["closed_for_court"]) == (False, True)
    assert not listed(admins, crew)


def test_five_joins_a_day(admins: Admins, crews: Crews) -> None:
    riley = admins.new("Riley")
    made = [crews.new(f"Crew {n}") for n in range(6)]
    for crew in made:
        assert crews.open(crew).status_code == 200
    for crew in made[:5]:
        assert join(admins, riley, crew).json()["outcome"] == "joined"
    limited = join(admins, riley, made[5])
    assert (limited.status_code, limited.json()["detail"]) == (
        429,
        "That's a lot of crews for one day. Try again tomorrow.",
    )
    # Nothing was added past the limit.
    assert search(admins, riley, made[5])[0]["my_status"] is None


def test_members_hear_once_a_week_when_their_crew_opens(
    admins: Admins, crews: Crews, sender: RecordingSender
) -> None:
    crew = crews.new("Court Crew")
    sam = join_and_approve(admins, crew["lead"], crew["gid"], "Sam")
    pat = join_and_approve(admins, crew["lead"], crew["gid"], "Pat")
    lead_phone = device(admins, crew["lead"])
    sam_phone = device(admins, sam)
    device(admins, pat)
    muted = admins.client.put("/v1/me/notifications", json={"muted": ["crew"]}, headers=pat)
    assert muted.status_code == 200, muted.text
    sender.sent.clear()
    assert crews.open(crew).status_code == 200
    # Sam hears; Pat turned crew news off; the lead who opened it doesn't need telling.
    assert [endpoint for endpoint, _ in sender.sent] == [sam_phone]
    message = sender.sent[0][1]
    assert message.title == "Court Crew is now open"
    assert "leave" in message.body
    assert lead_phone not in [endpoint for endpoint, _ in sender.sent]
    # Closing and opening again the same week: no second push.
    path = f"/v1/groups/{crew['gid']}/open"
    admins.client.put(path, json={"open": False}, headers=crew["lead"])
    assert crews.open(crew).status_code == 200
    assert len(sender.sent) == 1


def test_crew_news_is_offered_only_where_crews_can_open(admins: Admins, crews: Crews) -> None:
    outsider = admins.new("Riley")
    offered = admins.client.get("/v1/me/notifications", headers=outsider).json()["categories"]
    assert "crew" not in offered
    crew = crews.new()
    offered = admins.client.get("/v1/me/notifications", headers=crew["lead"]).json()["categories"]
    assert "crew" in offered


def test_reports_once_a_day_per_crew_and_three_a_day(
    admins: Admins, crews: Crews, owner_engine: Engine
) -> None:
    riley = admins.new("Riley")
    made = [crews.new(f"Crew {n}") for n in range(4)]
    for crew in made:
        assert crews.open(crew).status_code == 200
    first = report(admins, riley, made[0], reason="not_pickleball", note="  Sells paddles  ")
    assert first.status_code == 204, first.text
    # The same crew again today: fine, but not counted twice.
    assert report(admins, riley, made[0]).status_code == 204
    assert report(admins, riley, made[1]).status_code == 204
    assert report(admins, riley, made[2]).status_code == 204
    limited = report(admins, riley, made[3])
    assert limited.status_code == 429
    with owner(owner_engine) as conn:
        rows = conn.execute(
            text("SELECT reason, note FROM crew_reports WHERE reporter_id = :u ORDER BY id"),
            {"u": admins.user_id(riley)},
        ).all()
    assert [tuple(r) for r in rows] == [
        ("not_pickleball", "Sells paddles"),
        ("spam", None),
        ("spam", None),
    ]
    # Links, odd reasons, and crews that aren't listed are refused.
    other = admins.new("Pat")
    assert report(admins, other, made[3], note="see www.example.com").status_code == 422
    assert report(admins, other, made[3], reason="boring").status_code == 422
    closed = crews.new()
    assert report(admins, other, closed).status_code == 404


def test_reports_are_yours_alone_and_go_nameless_with_your_account(
    admins: Admins, crews: Crews, app_engine: Engine, owner_engine: Engine
) -> None:
    crew = crews.new()
    assert crews.open(crew).status_code == 200
    riley = admins.new("Riley")
    assert report(admins, riley, crew).status_code == 204
    data = admins.client.get("/v1/me/export", headers=riley).json()
    assert [r["reason"] for r in data["crew_reports"]] == ["spam"]
    # The crew's lead, or anyone else, can't read it.
    with as_user(app_engine, admins.user_id(crew["lead"])) as conn:
        assert conn.execute(text("SELECT count(*) FROM crew_reports")).scalar_one() == 0
        with pytest.raises(ProgrammingError, match="denied"):
            conn.execute(
                text("INSERT INTO crew_reports (group_id, reason) VALUES (:g, 'spam')"),
                {"g": crew["gid"]},
            )
    riley_id = admins.user_id(riley)
    with owner(owner_engine) as conn:
        conn.execute(text("UPDATE users SET deleted_at = now() WHERE id = :u"), {"u": riley_id})
        left = conn.execute(
            text("SELECT count(*), count(reporter_id) FROM crew_reports WHERE group_id = :g"),
            {"g": crew["gid"]},
        ).one()
    assert tuple(left) == (1, 0)


def test_the_app_cant_list_or_unlist_around_the_rules(
    admins: Admins, crews: Crews, app_engine: Engine
) -> None:
    crew = crews.new()
    sam = join_and_approve(admins, crew["lead"], crew["gid"], "Sam")
    lead_id = admins.user_id(crew["lead"])
    # Staff's columns aren't the app's to write.
    for column in ("unlisted_at", "open_notice_at"):
        with (
            as_user(app_engine, lead_id) as conn,
            pytest.raises(ProgrammingError, match="denied"),
        ):
            conn.execute(
                text(f"UPDATE groups SET {column} = NULL WHERE id = :g"), {"g": crew["gid"]}
            )
    with as_user(app_engine, lead_id) as conn:
        conn.execute(text("DELETE FROM crew_courts WHERE group_id = :g"), {"g": crew["gid"]})
        # No court from the map, no listing, whatever the API says.
        with pytest.raises(DBAPIError, match="default court from the map"):
            conn.execute(
                text("UPDATE groups SET open_to_all = true WHERE id = :g"), {"g": crew["gid"]}
            )
    # A member can't open it by writing the row either.
    with as_user(app_engine, admins.user_id(sam)) as conn:
        changed = conn.execute(
            text("UPDATE groups SET open_to_all = false, max_members = 99 WHERE id = :g"),
            {"g": crew["gid"]},
        ).rowcount
    assert changed == 0


def test_staff_unlist_a_reported_crew_and_its_lead_cant_reopen_it(
    admins: Admins, crews: Crews, boss: Headers, app_engine: Engine, owner_engine: Engine
) -> None:
    crew = crews.new("Spam Crew")
    assert crews.open(crew).status_code == 200
    for name in ("Riley", "Pat"):
        assert report(admins, admins.new(name), crew).status_code == 204
    listed = admins.admin.get("/v1/admin/open-crews/reports", headers=boss)
    assert listed.status_code == 200, listed.text
    [row] = [r for r in listed.json() if r["group_id"] == crew["gid"]]
    assert (row["reports"], row["reasons"], row["open_to_all"]) == (2, ["spam"], True)

    path = f"/v1/admin/open-crews/{crew['gid']}/unlist"
    assert admins.admin.post(path, json={"reason": "short"}, headers=boss).status_code == 422
    stale = sign_in(admins, ADMIN.lower(), signed_in_ago=FRESH_SIGN_IN + 60)
    assert admins.admin.post(path, json={"reason": REASON}, headers=stale).status_code == 403
    assert admins.admin.post(path, json={"reason": REASON}, headers=boss).status_code == 204
    assert staff_did(owner_engine, "crew.unlisted", crew["gid"]) == [
        {"reason": REASON, "details": {"was_open": True}}
    ]

    riley = admins.new("Riley")
    assert search(admins, riley, crew) == []
    detail = admins.client.get(f"/v1/groups/{crew['gid']}", headers=crew["lead"]).json()
    assert (detail["open_to_all"], detail["unlisted"]) == (False, True)
    # Not by writing the row either.
    with (
        as_user(app_engine, admins.user_id(crew["lead"])) as conn,
        pytest.raises(DBAPIError, match="groups_open_listed"),
    ):
        conn.execute(text("UPDATE groups SET open_to_all = true WHERE id = :g"), {"g": crew["gid"]})
    again = crews.open(crew)
    assert (again.status_code, again.json()["detail"]) == (
        409,
        "This crew can't be listed right now. Write to us if that seems wrong.",
    )
    # Its reports are settled.
    listed = admins.admin.get("/v1/admin/open-crews/reports", headers=boss).json()
    assert crew["gid"] not in [r["group_id"] for r in listed]

    relist = f"/v1/admin/open-crews/{crew['gid']}/relist"
    assert admins.admin.post(relist, json={"reason": REASON}, headers=boss).status_code == 204
    assert crews.open(crew).status_code == 200
    missing = admins.admin.post(
        f"/v1/admin/open-crews/{uuid4()}/unlist", json={"reason": REASON}, headers=boss
    )
    assert missing.status_code == 404


def test_staff_can_dismiss_reports(
    admins: Admins, crews: Crews, boss: Headers, owner_engine: Engine
) -> None:
    crew = crews.new()
    assert crews.open(crew).status_code == 200
    assert report(admins, admins.new("Riley"), crew).status_code == 204
    path = f"/v1/admin/open-crews/{crew['gid']}/dismiss"
    assert admins.admin.post(path, json={"reason": REASON}, headers=boss).status_code == 204
    assert staff_did(owner_engine, "crew.reports_dismissed", crew["gid"]) == [
        {"reason": REASON, "details": {"reports": 1}}
    ]
    listed = admins.admin.get("/v1/admin/open-crews/reports", headers=boss).json()
    assert crew["gid"] not in [r["group_id"] for r in listed]
    assert search(admins, admins.new("Pat"), crew)[0]["group_id"] == crew["gid"]


def test_only_staff_see_reports_and_unlist(admins: Admins, crews: Crews) -> None:
    crew = crews.new()
    casey = crew["lead"]
    for method, path, body in (
        ("GET", "/v1/admin/open-crews/reports", None),
        ("POST", f"/v1/admin/open-crews/{crew['gid']}/unlist", {"reason": REASON}),
        ("POST", f"/v1/admin/open-crews/{crew['gid']}/relist", {"reason": REASON}),
        ("POST", f"/v1/admin/open-crews/{crew['gid']}/dismiss", {"reason": REASON}),
    ):
        response = admins.admin.request(method, path, json=body, headers=casey)
        assert (response.status_code, response.json()) == (404, {"detail": "Not Found"}), path


def test_only_staff_run_the_staff_functions(admins: Admins, app_engine: Engine) -> None:
    riley = admins.user_id(admins.new("Riley"))
    for call in (
        "SELECT * FROM app_admin_open_crew_reports()",
        f"SELECT app_admin_unlist_crew('{uuid4()}', 'a long enough reason')",
        f"SELECT app_admin_relist_crew('{uuid4()}', 'a long enough reason')",
        f"SELECT app_admin_dismiss_crew_reports('{uuid4()}', 'a long enough reason')",
        f"SELECT app_crew_listed('{uuid4()}')",
    ):
        with as_user(app_engine, riley) as conn, pytest.raises(ProgrammingError, match="denied"):
            conn.execute(text(call))


def test_only_a_lead_can_ask_for_the_members_push(
    admins: Admins, crews: Crews, app_engine: Engine, owner_engine: Engine
) -> None:
    crew = crews.new()
    sam = join_and_approve(admins, crew["lead"], crew["gid"], "Sam")
    # Open, and the members not told yet: a member still can't make Popshot tell them.
    with owner(owner_engine) as conn:
        conn.execute(text("UPDATE groups SET open_to_all = true WHERE id = :g"), {"g": crew["gid"]})
    with as_user(app_engine, admins.user_id(sam)) as conn:
        claimed = conn.execute(
            text("SELECT app_claim_open_notice(:g)"), {"g": crew["gid"]}
        ).scalar_one()
    assert claimed is False
    with as_user(app_engine, admins.user_id(crew["lead"])) as conn:
        claimed = conn.execute(
            text("SELECT app_claim_open_notice(:g)"), {"g": crew["gid"]}
        ).scalar_one()
    assert claimed is True
