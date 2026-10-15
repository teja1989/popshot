"""Google Places (New): find a court by name, then look up where it is.

The API calls Google as its own service account (OAuth, a token from the metadata server), so
there's no API key anywhere. Only what Google's terms let us keep is kept (migration 0035):
the place ID, and coordinates for at most 30 days. Suggestions' names are shown to the person
searching and never stored.

Cost: autocomplete requests carry a session token, and the pick that ends the session asks
only for `id,location` (Place Details Essentials). The database limits both
(app_place_lookup), well inside Google's free monthly allowance.

Locally and in tests, FakePlaces answers from a short fixed list, so nothing reaches Google.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import structlog

from popshot_api.db import MetadataAccessToken

log = structlog.get_logger()

AUTOCOMPLETE_URL = "https://places.googleapis.com/v1/places:autocomplete"
DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"
TIMEOUT_SECONDS = 5
MAX_SUGGESTIONS = 5


@dataclass(frozen=True, slots=True)
class Suggestion:
    place_id: str
    main: str
    secondary: str


@dataclass(frozen=True, slots=True)
class Location:
    place_id: str
    lat: float
    lng: float


class PlacesUnavailableError(Exception):
    """Google couldn't be reached or answered oddly; nothing was kept."""


class Places(Protocol):
    def suggest(self, text: str, session: str) -> list[Suggestion]: ...

    def locate(self, place_id: str, session: str | None) -> Location | None: ...


Http = Callable[[urllib.request.Request], dict[str, Any]]


def _http(request: urllib.request.Request) -> dict[str, Any]:
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
        data: dict[str, Any] = json.load(response)
    return data


def _text(value: Any) -> str:
    """Google's `{"text": "..."}` shapes, or an empty string."""
    if isinstance(value, dict) and isinstance(value.get("text"), str):
        return str(value["text"])
    return ""


class GooglePlaces:
    def __init__(
        self,
        project: str,
        token: Callable[[], str] | None = None,
        http: Http | None = None,
    ) -> None:
        self._project = project
        self._token = token or MetadataAccessToken()
        self._http = http or _http

    def _headers(self, field_mask: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._token()}",
            # Bill and count our project's quota (needs serviceusage.services.use).
            "X-Goog-User-Project": self._project,
            "Content-Type": "application/json",
        }
        if field_mask:
            headers["X-Goog-FieldMask"] = field_mask
        return headers

    def _call(self, request: urllib.request.Request) -> dict[str, Any]:
        try:
            return self._http(request)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise
            log.warning("places.call_failed", status=exc.code)
            raise PlacesUnavailableError("places call failed") from exc
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            log.warning("places.call_failed", error=type(exc).__name__)
            raise PlacesUnavailableError("places call failed") from exc

    def suggest(self, text: str, session: str) -> list[Suggestion]:
        body = {"input": text, "sessionToken": session}
        request = urllib.request.Request(
            AUTOCOMPLETE_URL,
            data=json.dumps(body).encode(),
            headers=self._headers(),
            method="POST",
        )
        data = self._call(request)
        found: list[Suggestion] = []
        for item in data.get("suggestions") or []:
            prediction = item.get("placePrediction") if isinstance(item, dict) else None
            if not isinstance(prediction, dict) or not isinstance(prediction.get("placeId"), str):
                continue
            structured = prediction.get("structuredFormat") or {}
            main = _text(structured.get("mainText")) or _text(prediction.get("text"))
            if not main:
                continue
            found.append(
                Suggestion(
                    place_id=prediction["placeId"],
                    main=main,
                    secondary=_text(structured.get("secondaryText")),
                )
            )
        return found[:MAX_SUGGESTIONS]

    def locate(self, place_id: str, session: str | None) -> Location | None:
        query = f"?{urllib.parse.urlencode({'sessionToken': session})}" if session else ""
        request = urllib.request.Request(  # noqa: S310 (a fixed https URL)
            DETAILS_URL.format(place_id=urllib.parse.quote(place_id, safe="")) + query,
            headers=self._headers("id,location"),
            method="GET",
        )
        try:
            data = self._call(request)
        except urllib.error.HTTPError:
            return None  # A 404: Google no longer knows the place.
        location = data.get("location") or {}
        lat, lng = location.get("latitude"), location.get("longitude")
        if not isinstance(lat, int | float) or not isinstance(lng, int | float):
            raise PlacesUnavailableError("no location in the answer")
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise PlacesUnavailableError("location out of range")
        return Location(place_id=place_id, lat=float(lat), lng=float(lng))


FAKE: tuple[tuple[str, str, str, float, float], ...] = (
    (
        "fake-riverside-park",
        "Riverside Park Pickleball Courts",
        "Riverside Dr, Springfield",
        40.80,
        -73.97,
    ),
    ("fake-st-james-rec", "St. James Recreation Center", "Jerome Ave, Springfield", 40.86, -73.90),
    ("fake-sunset-park", "Sunset Park Courts", "44th St, Springfield", 40.65, -74.00),
)


class FakePlaces:
    """Local development and tests: a few made-up courts, matched by any word typed."""

    def __init__(self) -> None:
        # What was asked, and with which Google session: tests check one session per pick.
        self.calls: list[tuple[str, str | None]] = []

    def suggest(self, text: str, session: str) -> list[Suggestion]:
        self.calls.append(("suggest", session))
        words = [w for w in text.lower().split() if w]
        return [
            Suggestion(place_id=pid, main=main, secondary=secondary)
            for pid, main, secondary, _, _ in FAKE
            if any(w in main.lower() for w in words)
        ]

    def locate(self, place_id: str, session: str | None) -> Location | None:
        self.calls.append(("locate", session))
        for pid, _, _, lat, lng in FAKE:
            if pid == place_id:
                return Location(place_id=pid, lat=lat, lng=lng)
        return None
