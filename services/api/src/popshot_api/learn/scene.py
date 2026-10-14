"""A shot's scene: players moving on a court and the ball's flights, as data.

Distances are in feet. x runs across the court (0 to 20), y along it (0 to 44) with the net
at y = 22 and the kitchen lines at y = 15 and y = 29, and z is height. You and your partner
play the near half (y below the net); the other two play the far half.

A flight is the ball's path from one hit to where it lands or is hit next. Authors set where
it starts, where it ends and how high it peaks; ball_height works out the arc between, the
same way the web's lib/shot-scene.ts draws it.

Scene checks the shape (bounds, times, sizes) whenever a scene is saved. problems() checks
that it's a playable shot (the ball goes over the net and lands in, players stay on their
side), which a scene must pass to be published but not to be saved as a draft.
"""

import itertools
import math
from dataclasses import dataclass
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

COURT_WIDTH = 20.0
COURT_LENGTH = 44.0
NET_Y = 22.0
KITCHEN = 7.0
# Net height: 34 inches in the middle, 36 at the posts, which stand a foot outside the lines.
NET_MIDDLE = 34 / 12
NET_POST = 36 / 12
POST_OUTSIDE = 1.0
BALL_RADIUS = 1.45 / 12

MAX_DURATION = 20.0
MAX_ACTORS = 4
MAX_KEYS = 60
MAX_FLIGHTS = 30
MAX_CALLOUTS = 20
MAX_ZONES = 6
# Stored as jsonb; this is the most a scene's JSON may take.
MAX_SCENE_BYTES = 32 * 1024

ActorId = Literal["you", "partner", "them_1", "them_2"]
NEAR: frozenset[str] = frozenset({"you", "partner"})
Stance = Literal["ready", "split", "low", "run"]
FlightKind = Literal[
    "serve", "return", "drop", "drive", "dink", "reset", "volley", "lob", "smash", "speedup"
]
Camera = Literal["behind", "side", "top"]

Time = Annotated[float, Field(ge=0, le=MAX_DURATION, allow_inf_nan=False)]
# Players can stand a little outside the lines; the ball can go further.
PlayerX = Annotated[float, Field(ge=-8, le=COURT_WIDTH + 8, allow_inf_nan=False)]
PlayerY = Annotated[float, Field(ge=-10, le=COURT_LENGTH + 10, allow_inf_nan=False)]
BallX = Annotated[float, Field(ge=-10, le=COURT_WIDTH + 10, allow_inf_nan=False)]
BallY = Annotated[float, Field(ge=-15, le=COURT_LENGTH + 15, allow_inf_nan=False)]
Height = Annotated[float, Field(ge=0, le=30, allow_inf_nan=False)]
CourtX = Annotated[float, Field(ge=0, le=COURT_WIDTH, allow_inf_nan=False)]
CourtY = Annotated[float, Field(ge=0, le=COURT_LENGTH, allow_inf_nan=False)]
Words = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Key(_Strict):
    t: Time
    x: PlayerX
    y: PlayerY
    stance: Stance | None = None


class Actor(_Strict):
    id: ActorId
    keys: list[Key] = Field(min_length=1, max_length=MAX_KEYS)

    @model_validator(mode="after")
    def _times_go_forward(self) -> Self:
        times = [k.t for k in self.keys]
        if any(b <= a for a, b in itertools.pairwise(times)):
            raise ValueError("Each player's keyframes must go forward in time.")
        return self


class BallPoint(_Strict):
    x: BallX
    y: BallY
    z: Height


class Flight(_Strict):
    t0: Time
    t1: Time
    start: BallPoint
    end: BallPoint
    apex_z: Height
    kind: FlightKind

    @model_validator(mode="after")
    def _sensible(self) -> Self:
        if self.t1 <= self.t0:
            raise ValueError("A flight has to end after it starts.")
        if self.apex_z < max(self.start.z, self.end.z):
            raise ValueError("A flight can't peak lower than where it starts or ends.")
        return self


class Callout(_Strict):
    t: Time
    text: Words
    x: CourtX | None = None
    y: CourtY | None = None


class Zone(_Strict):
    x0: CourtX
    y0: CourtY
    x1: CourtX
    y1: CourtY
    label: Label | None = None

    @model_validator(mode="after")
    def _has_area(self) -> Self:
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ValueError("A zone needs a width and a length.")
        return self


class Scene(_Strict):
    schema_version: Literal[1]
    duration: Annotated[float, Field(ge=1, le=MAX_DURATION, allow_inf_nan=False)]
    camera: Camera = "behind"
    actors: list[Actor] = Field(min_length=1, max_length=MAX_ACTORS)
    flights: list[Flight] = Field(default_factory=list, max_length=MAX_FLIGHTS)
    callouts: list[Callout] = Field(default_factory=list, max_length=MAX_CALLOUTS)
    zones: list[Zone] = Field(default_factory=list, max_length=MAX_ZONES)

    @model_validator(mode="after")
    def _fits(self) -> Self:
        ids = [a.id for a in self.actors]
        if len(set(ids)) != len(ids):
            raise ValueError("Each player can only appear once.")
        if any(k.t > self.duration for a in self.actors for k in a.keys):
            raise ValueError("A keyframe is after the end of the scene.")
        if any(f.t1 > self.duration for f in self.flights):
            raise ValueError("A flight ends after the end of the scene.")
        if any(c.t > self.duration for c in self.callouts):
            raise ValueError("A callout is after the end of the scene.")
        for before, after in itertools.pairwise(self.flights):
            if after.t0 < before.t1:
                raise ValueError("Flights must be in order and can't overlap.")
        return self


def _curve(start_z: float, end_z: float, apex_z: float) -> tuple[float, float]:
    """(a, b) for z(s) = a*s² + b*s + start_z: through start_z at s=0 and end_z at s=1, with
    its highest point apex_z. Where the apex is at an end, the highest point is that end."""
    rise = apex_z - start_z
    change = end_z - start_z
    a = change - 2 * rise - 2 * math.sqrt(max(0.0, rise * (rise - change)))
    return a, change - a


def ball_height(flight: Flight, s: float) -> float:
    """The ball's height a fraction s (0 to 1) of the way along a flight."""
    a, b = _curve(flight.start.z, flight.end.z, flight.apex_z)
    return a * s * s + b * s + flight.start.z


def ball_at(flight: Flight, s: float) -> tuple[float, float, float]:
    x = flight.start.x + (flight.end.x - flight.start.x) * s
    y = flight.start.y + (flight.end.y - flight.start.y) * s
    return x, y, ball_height(flight, s)


def net_height(x: float) -> float:
    """The top of the net at x: lowest in the middle, rising to the posts."""
    from_middle = min(abs(x - COURT_WIDTH / 2), COURT_WIDTH / 2 + POST_OUTSIDE)
    return NET_MIDDLE + (NET_POST - NET_MIDDLE) * from_middle / (COURT_WIDTH / 2 + POST_OUTSIDE)


ProblemCode = Literal["same_side", "net", "out", "wrong_side"]


@dataclass(frozen=True, slots=True)
class Problem:
    code: ProblemCode
    message: str
    # Which flight or player it's about.
    flight: int | None = None
    actor: ActorId | None = None


def _in_court(x: float, y: float) -> bool:
    return 0 <= x <= COURT_WIDTH and 0 <= y <= COURT_LENGTH


def problems(scene: Scene) -> list[Problem]:
    """What would stop this scene from being a real rally. Empty means it's fine to publish."""
    found: list[Problem] = []
    for i, f in enumerate(scene.flights):
        number = i + 1
        crossing = (f.start.y - NET_Y) * (f.end.y - NET_Y)
        if crossing >= 0:
            found.append(Problem("same_side", f"Shot {number} doesn't go over the net.", flight=i))
            continue
        s = (NET_Y - f.start.y) / (f.end.y - f.start.y)
        x, _, z = ball_at(f, s)
        if z - BALL_RADIUS < net_height(x):
            found.append(Problem("net", f"Shot {number} hits the net.", flight=i))
        if f.end.z == 0 and not _in_court(f.end.x, f.end.y):
            found.append(Problem("out", f"Shot {number} lands out.", flight=i))
    for actor in scene.actors:
        near = actor.id in NEAR
        if any((k.y > NET_Y) if near else (k.y < NET_Y) for k in actor.keys):
            found.append(
                Problem(
                    "wrong_side",
                    f"{_ACTOR_NAMES[actor.id]} can't cross the net.",
                    actor=actor.id,
                )
            )
    return found


_ACTOR_NAMES: dict[str, str] = {
    "you": "You",
    "partner": "Your partner",
    "them_1": "Their first player",
    "them_2": "Their second player",
}
