"""The Google Places client (popshot_api.places), with Google replaced by a recorded answer."""

import io
import json
import os
import urllib.error
import urllib.request
from typing import Any

import pytest

from popshot_api.places import FakePlaces, GooglePlaces, PlacesUnavailableError
from popshot_api.settings import Environment
from tests.conftest import make_settings


class Recorder:
    def __init__(self, answer: dict[str, Any] | Exception) -> None:
        self.answer = answer
        self.requests: list[urllib.request.Request] = []

    def __call__(self, request: urllib.request.Request) -> dict[str, Any]:
        self.requests.append(request)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def places(answer: dict[str, Any] | Exception) -> tuple[GooglePlaces, Recorder]:
    recorder = Recorder(answer)
    return GooglePlaces("popshot-test", token=lambda: "tok", http=recorder), recorder


SUGGESTIONS = {
    "suggestions": [
        {
            "placePrediction": {
                "placeId": "ChIJ1",
                "text": {"text": "Riverside Park Courts, Springfield"},
                "structuredFormat": {
                    "mainText": {"text": "Riverside Park Courts"},
                    "secondaryText": {"text": "Springfield"},
                },
            }
        },
        # Query predictions and malformed entries are skipped.
        {"queryPrediction": {"text": {"text": "pickleball near me"}}},
        {"placePrediction": {"placeId": 7}},
        {"placePrediction": {"placeId": "ChIJ2", "text": {"text": "Only Text Court"}}},
    ]
}


def test_suggestions_use_our_identity_and_project_and_the_session() -> None:
    client, recorder = places(SUGGESTIONS)
    found = client.suggest("riverside", "session-1")
    assert [(s.place_id, s.main, s.secondary) for s in found] == [
        ("ChIJ1", "Riverside Park Courts", "Springfield"),
        ("ChIJ2", "Only Text Court", ""),
    ]
    [request] = recorder.requests
    assert request.full_url == "https://places.googleapis.com/v1/places:autocomplete"
    headers = {k.lower(): v for k, v in request.header_items()}
    # OAuth as our service account: no API key anywhere.
    assert headers["authorization"] == "Bearer tok"
    assert headers["x-goog-user-project"] == "popshot-test"
    assert "key" not in request.full_url
    assert isinstance(request.data, bytes)
    assert json.loads(request.data) == {"input": "riverside", "sessionToken": "session-1"}


def test_at_most_five_suggestions() -> None:
    many = {
        "suggestions": [
            {"placePrediction": {"placeId": f"id{i}", "text": {"text": f"Court {i}"}}}
            for i in range(9)
        ]
    }
    client, _ = places(many)
    assert len(client.suggest("court", "s")) == 5


def test_locating_asks_only_for_the_location() -> None:
    client, recorder = places({"id": "ChIJ1", "location": {"latitude": 40.8, "longitude": -73.9}})
    found = client.locate("ChIJ1", "session-1")
    assert found is not None
    assert (found.lat, found.lng) == (40.8, -73.9)
    [request] = recorder.requests
    assert request.full_url == (
        "https://places.googleapis.com/v1/places/ChIJ1?sessionToken=session-1"
    )
    headers = {k.lower(): v for k, v in request.header_items()}
    # Place Details Essentials: nothing that costs more, and nothing we couldn't keep anyway.
    assert headers["x-goog-fieldmask"] == "id,location"


def test_a_place_google_no_longer_knows_is_none() -> None:
    gone = urllib.error.HTTPError("u", 404, "Not Found", {}, io.BytesIO(b"{}"))  # type: ignore[arg-type]
    client, _ = places(gone)
    assert client.locate("ChIJ1", None) is None


@pytest.mark.parametrize(
    "answer",
    [
        urllib.error.HTTPError("u", 403, "Forbidden", {}, io.BytesIO(b"{}")),  # type: ignore[arg-type]
        urllib.error.URLError("down"),
        TimeoutError(),
        {"id": "x"},
        {"location": {"latitude": "40", "longitude": 1}},
        {"location": {"latitude": 91, "longitude": 1}},
    ],
)
def test_odd_answers_are_unavailable_never_kept(answer: Any) -> None:
    client, _ = places(answer)
    with pytest.raises(PlacesUnavailableError):
        client.locate("ChIJ1", None)


def test_the_fake_matches_any_word() -> None:
    fake = FakePlaces()
    assert [s.place_id for s in fake.suggest("park courts", "s")] == [
        "fake-riverside-park",
        "fake-sunset-park",
    ]
    assert fake.locate("fake-nowhere", None) is None


def test_the_fake_is_for_local_development_and_tests_only(monkeypatch: pytest.MonkeyPatch) -> None:
    assert make_settings(places="fake").places == "fake"
    with pytest.raises(ValueError, match="local development and tests"):
        make_settings(Environment.PROD, places="fake")
    monkeypatch.setitem(os.environ, "K_SERVICE", "api")
    with pytest.raises(ValueError, match="local development and tests"):
        make_settings(places="fake")


def test_google_needs_the_project() -> None:
    with pytest.raises(ValueError, match="gcp_project"):
        make_settings(places="google")
    assert make_settings(places="google", gcp_project="popshot-test").places == "google"
