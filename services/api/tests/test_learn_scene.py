"""A shot's scene (popshot_api.learn.scene): its shape, the ball's arc and the rally checks."""

import math
from typing import Any

import pytest
from pydantic import ValidationError

from popshot_api.learn.scene import (
    BALL_RADIUS,
    NET_MIDDLE,
    NET_POST,
    Flight,
    Scene,
    ball_at,
    ball_height,
    net_height,
    problems,
)


def good_scene() -> dict[str, Any]:
    """A serve, a return and a third-shot drop that lands in the kitchen."""
    return {
        "schema_version": 1,
        "duration": 6,
        "camera": "behind",
        "actors": [
            {
                "id": "you",
                "keys": [
                    {"t": 0, "x": 15, "y": 1, "stance": "ready"},
                    {"t": 3.6, "x": 14, "y": 3},
                    {"t": 6, "x": 13, "y": 12, "stance": "split"},
                ],
            },
            {"id": "partner", "keys": [{"t": 0, "x": 5, "y": 1}, {"t": 6, "x": 6, "y": 13}]},
            {"id": "them_1", "keys": [{"t": 0, "x": 5, "y": 41}, {"t": 3, "x": 6, "y": 30}]},
            {"id": "them_2", "keys": [{"t": 0, "x": 15, "y": 30}]},
        ],
        "flights": [
            {
                "t0": 0,
                "t1": 1.2,
                "start": {"x": 15, "y": 1, "z": 2.5},
                "end": {"x": 5, "y": 38, "z": 0},
                "apex_z": 8,
                "kind": "serve",
            },
            {
                "t0": 1.8,
                "t1": 3.0,
                "start": {"x": 5, "y": 40, "z": 1.5},
                "end": {"x": 14, "y": 4, "z": 0},
                "apex_z": 9,
                "kind": "return",
            },
            {
                "t0": 3.6,
                "t1": 5.0,
                "start": {"x": 14, "y": 3, "z": 1.5},
                "end": {"x": 8, "y": 25, "z": 0},
                "apex_z": 7,
                "kind": "drop",
            },
        ],
        "callouts": [{"t": 3.6, "text": "Lift it soft, land it in the kitchen"}],
        "zones": [{"x0": 0, "y0": 22, "x1": 20, "y1": 29, "label": "Kitchen"}],
    }


def flight(**changes: Any) -> Flight:
    base = good_scene()["flights"][2]
    return Flight.model_validate({**base, **changes})


def test_a_good_scene_has_no_problems() -> None:
    assert problems(Scene.model_validate(good_scene())) == []


@pytest.mark.parametrize(
    ("start", "end", "apex"),
    [(1.5, 0, 6), (0, 0, 4), (3, 3, 3), (2, 5, 5), (5, 2, 5), (0, 1, 7.5), (1, 1, 1)],
)
def test_the_arc_passes_through_its_ends_and_peaks_at_the_apex(
    start: float, end: float, apex: float
) -> None:
    f = flight(start={"x": 0, "y": 0, "z": start}, end={"x": 0, "y": 40, "z": end}, apex_z=apex)
    assert ball_height(f, 0) == pytest.approx(start)
    assert ball_height(f, 1) == pytest.approx(end)
    highest = max(ball_height(f, i / 1000) for i in range(1001))
    assert highest == pytest.approx(apex, abs=1e-3)
    # Never below the lower end: no dips under the court.
    assert min(ball_height(f, i / 1000) for i in range(1001)) >= min(start, end) - 1e-9


def test_a_level_arc_peaks_halfway() -> None:
    f = flight(start={"x": 0, "y": 0, "z": 0}, end={"x": 10, "y": 40, "z": 0}, apex_z=4)
    assert ball_at(f, 0.5) == pytest.approx((5, 20, 4))


def test_the_net_is_lowest_in_the_middle() -> None:
    assert net_height(10) == pytest.approx(NET_MIDDLE)
    assert net_height(-1) == pytest.approx(NET_POST)
    assert net_height(21) == pytest.approx(NET_POST)
    assert net_height(-5) == pytest.approx(NET_POST)
    assert NET_MIDDLE < net_height(3) < NET_POST


def scene_with(**changes: Any) -> Scene:
    return Scene.model_validate({**good_scene(), **changes})


def test_a_ball_into_the_net_is_a_problem() -> None:
    flights = good_scene()["flights"]
    # Peaking at the net's own height means the ball's bottom is below the tape.
    flights[2] = {**flights[2], "start": {"x": 10, "y": 3, "z": 1}, "apex_z": 1}
    found = problems(scene_with(flights=flights))
    assert [(p.code, p.flight) for p in found] == [("net", 2)]
    assert found[0].message == "Shot 3 hits the net."


def test_just_over_the_net_is_fine_and_just_under_is_not() -> None:
    def clears(apex: float) -> bool:
        flights = good_scene()["flights"]
        flights[2] = {
            **flights[2],
            "start": {"x": 10, "y": 12, "z": apex},
            "end": {"x": 10, "y": 32, "z": apex},
            "apex_z": apex,
        }
        return problems(scene_with(flights=flights)) == []

    tape = NET_MIDDLE + BALL_RADIUS
    assert clears(tape + 0.01)
    assert not clears(tape - 0.01)


def test_a_shot_that_stays_on_one_side_or_lands_out_is_a_problem() -> None:
    flights = good_scene()["flights"]
    flights[0] = {**flights[0], "end": {"x": 5, "y": 18, "z": 0}}
    flights[2] = {**flights[2], "end": {"x": 21, "y": 25, "z": 0}}
    assert [(p.code, p.flight) for p in problems(scene_with(flights=flights))] == [
        ("same_side", 0),
        ("out", 2),
    ]


def test_a_volley_out_of_the_air_isnt_out() -> None:
    flights = good_scene()["flights"]
    flights[2] = {**flights[2], "end": {"x": 8, "y": 46, "z": 2}, "apex_z": 7}
    assert problems(scene_with(flights=flights)) == []


def test_players_stay_on_their_side() -> None:
    actors = good_scene()["actors"]
    actors[0]["keys"].append({"t": 5.5, "x": 10, "y": 23})
    actors[0]["keys"].sort(key=lambda k: k["t"])
    actors[3]["keys"].append({"t": 1, "x": 15, "y": 21})
    found = problems(scene_with(actors=actors))
    assert [(p.code, p.actor) for p in found] == [("wrong_side", "you"), ("wrong_side", "them_2")]
    assert [p.message for p in found] == [
        "You can't cross the net.",
        "Their second player can't cross the net.",
    ]


def _broken(**changes: Any) -> dict[str, Any]:
    return {**good_scene(), **changes}


def _with_flight(**changes: Any) -> dict[str, Any]:
    scene = good_scene()
    scene["flights"][2] = {**scene["flights"][2], **changes}
    return scene


def _with_key(key: dict[str, Any]) -> dict[str, Any]:
    scene = good_scene()
    scene["actors"][0]["keys"] = [key]
    return scene


@pytest.mark.parametrize(
    "scene",
    [
        _broken(schema_version=2),
        _broken(duration=0.5),
        _broken(duration=21),
        _broken(duration=math.inf),
        _broken(camera="drone"),
        _broken(actors=[]),
        _broken(actors=[good_scene()["actors"][0]] * 2),
        _broken(extra=True),
        _broken(duration=4),  # the drop ends at 5
        _with_flight(t1=3.6),
        _with_flight(t0=2.9),  # overlaps the return, which ends at 3
        _with_flight(apex_z=1),  # lower than where it starts
        _with_flight(apex_z=math.nan),
        _with_flight(kind="tweener"),
        _with_flight(spin=3),
        _with_flight(end={"x": 8, "y": 25, "z": -1}),
        _with_flight(end={"x": 8, "y": 99, "z": 0}),
        _with_key({"t": 0, "x": 99, "y": 0}),
        _with_key({"t": 0, "x": 0, "y": 0, "stance": "dab"}),
        _with_key({"t": 25, "x": 0, "y": 0}),
        _broken(callouts=[{"t": 0, "text": ""}]),
        _broken(callouts=[{"t": 0, "text": "x" * 81}]),
        _broken(callouts=[{"t": 7, "text": "After the end"}]),
        _broken(zones=[{"x0": 5, "y0": 0, "x1": 5, "y1": 10}]),
        _broken(zones=[{"x0": 0, "y0": 0, "x1": 25, "y1": 10}]),
        _broken(flights=[good_scene()["flights"][0]] * 31),
    ],
)
def test_bad_shapes_are_refused(scene: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Scene.model_validate(scene)


def test_keyframes_go_forward() -> None:
    scene = good_scene()
    scene["actors"][1]["keys"] = [{"t": 2, "x": 5, "y": 1}, {"t": 2, "x": 6, "y": 2}]
    with pytest.raises(ValidationError, match="forward in time"):
        Scene.model_validate(scene)
