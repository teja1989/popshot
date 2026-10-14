import { describe, expect, it } from "vitest";

import {
  actorAt,
  BALL_RADIUS,
  ballAt,
  ballAtTime,
  ballHeight,
  calloutAt,
  clock,
  firstView,
  flightPath,
  NET_MIDDLE,
  NET_POST,
  netHeight,
  problems,
  type Actor,
  type Flight,
  type Scene,
} from "./shot-scene";

// The same serve, return and third-shot drop as the API's tests/test_learn_scene.py.
function goodScene(): Scene {
  return {
    schema_version: 1,
    duration: 6,
    camera: "behind",
    actors: [
      {
        id: "you",
        keys: [
          { t: 0, x: 15, y: 1, stance: "ready" },
          { t: 3.6, x: 14, y: 3 },
          { t: 6, x: 13, y: 12, stance: "split" },
        ],
      },
      {
        id: "partner",
        keys: [
          { t: 0, x: 5, y: 1 },
          { t: 6, x: 6, y: 13 },
        ],
      },
      {
        id: "them_1",
        keys: [
          { t: 0, x: 5, y: 41 },
          { t: 3, x: 6, y: 30 },
        ],
      },
      { id: "them_2", keys: [{ t: 0, x: 15, y: 30 }] },
    ],
    flights: [
      { t0: 0, t1: 1.2, start: { x: 15, y: 1, z: 2.5 }, end: { x: 5, y: 38, z: 0 }, apex_z: 8, kind: "serve" },
      { t0: 1.8, t1: 3, start: { x: 5, y: 40, z: 1.5 }, end: { x: 14, y: 4, z: 0 }, apex_z: 9, kind: "return" },
      { t0: 3.6, t1: 5, start: { x: 14, y: 3, z: 1.5 }, end: { x: 8, y: 25, z: 0 }, apex_z: 7, kind: "drop" },
    ],
    callouts: [
      { t: 3.6, text: "Lift it soft" },
      { t: 4.5, text: "Follow it in" },
    ],
    zones: [{ x0: 0, y0: 22, x1: 20, y1: 29, label: "Kitchen" }],
  };
}

function flight(start: number, end: number, apex: number): Flight {
  return { t0: 0, t1: 1, start: { x: 0, y: 0, z: start }, end: { x: 0, y: 40, z: end }, apex_z: apex, kind: "drop" };
}

describe("the ball's arc", () => {
  it.each([
    [1.5, 0, 6],
    [0, 0, 4],
    [3, 3, 3],
    [2, 5, 5],
    [5, 2, 5],
    [0, 1, 7.5],
  ])("from %d to %d peaking at %d", (start, end, apex) => {
    const f = flight(start, end, apex);
    expect(ballHeight(f, 0)).toBeCloseTo(start);
    expect(ballHeight(f, 1)).toBeCloseTo(end);
    const heights = Array.from({ length: 1001 }, (_, i) => ballHeight(f, i / 1000));
    expect(Math.max(...heights)).toBeCloseTo(apex, 3);
    expect(Math.min(...heights)).toBeGreaterThanOrEqual(Math.min(start, end) - 1e-9);
  });

  it("peaks halfway when both ends are level", () => {
    const f = { ...flight(0, 0, 4), end: { x: 10, y: 40, z: 0 } };
    const middle = ballAt(f, 0.5);
    expect([middle.x, middle.y, middle.z]).toEqual([5, 20, expect.closeTo(4) as number]);
  });

  it("draws a path from end to end", () => {
    const path = flightPath(flight(1, 0, 5), 10);
    expect(path).toHaveLength(11);
    expect(path[0]?.z).toBeCloseTo(1);
    expect(path[10]?.y).toBe(40);
  });
});

describe("the net", () => {
  it("is lowest in the middle", () => {
    expect(netHeight(10)).toBeCloseTo(NET_MIDDLE);
    expect(netHeight(-1)).toBeCloseTo(NET_POST);
    expect(netHeight(21)).toBeCloseTo(NET_POST);
    expect(netHeight(-5)).toBeCloseTo(NET_POST);
  });
});

describe("problems, matching the API", () => {
  it("finds none in a good rally", () => {
    expect(problems(goodScene())).toEqual([]);
  });

  it("finds a ball into the net, one on its own side and one out", () => {
    const scene = goodScene();
    const [serve, back, drop] = scene.flights as [Flight, Flight, Flight];
    scene.flights = [
      { ...serve, end: { x: 5, y: 18, z: 0 } },
      { ...back, end: { x: 21, y: 4, z: 0 } },
      { ...drop, start: { x: 10, y: 3, z: 1 }, apex_z: 1 },
    ];
    expect(problems(scene).map((p) => [p.code, p.flight, p.message])).toEqual([
      ["same_side", 0, "Shot 1 doesn't go over the net."],
      ["out", 1, "Shot 2 lands out."],
      ["net", 2, "Shot 3 hits the net."],
    ]);
  });

  it("is exact at the tape", () => {
    function clears(height: number): boolean {
      const scene = goodScene();
      scene.flights = [
        {
          t0: 0,
          t1: 1,
          start: { x: 10, y: 12, z: height },
          end: { x: 10, y: 32, z: height },
          apex_z: height,
          kind: "drive",
        },
      ];
      return problems(scene).length === 0;
    }
    expect(clears(NET_MIDDLE + BALL_RADIUS + 0.01)).toBe(true);
    expect(clears(NET_MIDDLE + BALL_RADIUS - 0.01)).toBe(false);
  });

  it("keeps players on their side", () => {
    const scene = goodScene();
    const [you] = scene.actors as [Actor];
    you.keys.push({ t: 6.5, x: 10, y: 23 });
    expect(problems(scene).map((p) => p.message)).toEqual(["You can't cross the net."]);
  });
});

describe("playback", () => {
  it("moves players between keyframes and holds them before and after", () => {
    const [you] = goodScene().actors as [Actor];
    expect(actorAt(you, 0)).toEqual({ x: 15, y: 1, stance: "ready" });
    expect(actorAt(you, 1.8)).toEqual({ x: 14.5, y: 2, stance: "ready" });
    expect(actorAt(you, 6)).toEqual({ x: 13, y: 12, stance: "split" });
    expect(actorAt(you, 9)).toEqual({ x: 13, y: 12, stance: "split" });
  });

  it("follows the ball along each flight and bounces it between them", () => {
    const scene = goodScene();
    expect(ballAtTime(scene, 0)).toEqual({ at: { x: 15, y: 1, z: 2.5 }, flight: null });
    expect(ballAtTime(scene, 0.6)?.flight).toBe(0);
    // Between the serve landing (z 0) and the return (z 1.5), it bounces up above both.
    const bounce = ballAtTime(scene, 1.5);
    expect(bounce?.flight).toBeNull();
    expect(bounce?.at.z).toBeGreaterThan(1.5);
    expect(ballAtTime(scene, 4.3)?.flight).toBe(2);
    expect(ballAtTime(scene, 6)).toEqual({ at: { x: 8, y: 25, z: 0 }, flight: null });
    expect(ballAtTime({ ...scene, flights: [] }, 1)).toBeNull();
  });

  it("shows the latest callout for a while", () => {
    const scene = goodScene();
    expect(calloutAt(scene, 3)).toBeNull();
    expect(calloutAt(scene, 4)?.text).toBe("Lift it soft");
    expect(calloutAt(scene, 4.6)?.text).toBe("Follow it in");
    expect(calloutAt(scene, 7.1)).toBeNull();
  });

  it("formats the clock", () => {
    expect(clock(0)).toBe("0:00.0");
    expect(clock(3.56)).toBe("0:03.5");
    expect(clock(12.05)).toBe("0:12.0");
  });

  it("opens in 3D unless it can't or motion should be reduced", () => {
    expect(firstView(true, false)).toBe("3d");
    expect(firstView(true, true)).toBe("above");
    expect(firstView(false, false)).toBe("above");
  });
});
