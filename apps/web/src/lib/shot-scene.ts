// A shot's scene: players moving on a court and the ball's flights. Shapes and maths match the
// API's popshot_api/learn/scene.py, which checks every scene before it's saved.
//
// Distances are in feet. x runs across the court (0 to 20), y along it (0 to 44) with the net
// at y = 22, and z is height. You and your partner play the near half (y below the net).

export const COURT_WIDTH = 20;
export const COURT_LENGTH = 44;
export const NET_Y = 22;
export const KITCHEN = 7;
export const NET_MIDDLE = 34 / 12;
export const NET_POST = 36 / 12;
export const POST_OUTSIDE = 1;
export const BALL_RADIUS = 1.45 / 12;

export type ActorId = "you" | "partner" | "them_1" | "them_2";
export type Stance = "ready" | "split" | "low" | "run";
export type FlightKind =
  | "serve"
  | "return"
  | "drop"
  | "drive"
  | "dink"
  | "reset"
  | "volley"
  | "lob"
  | "smash"
  | "speedup";
export type Camera = "behind" | "side" | "top";

export interface Key {
  t: number;
  x: number;
  y: number;
  stance?: Stance | null;
}

export interface Actor {
  id: ActorId;
  keys: Key[];
}

export interface BallPoint {
  x: number;
  y: number;
  z: number;
}

export interface Flight {
  t0: number;
  t1: number;
  start: BallPoint;
  end: BallPoint;
  apex_z: number;
  kind: FlightKind;
}

export interface Callout {
  t: number;
  text: string;
  x?: number | null;
  y?: number | null;
}

export interface Zone {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  label?: string | null;
}

export interface Scene {
  schema_version: 1;
  duration: number;
  camera: Camera;
  actors: Actor[];
  flights: Flight[];
  callouts: Callout[];
  zones: Zone[];
}

export const ACTOR_LABEL: Record<ActorId, string> = {
  you: "You",
  partner: "Partner",
  them_1: "Them",
  them_2: "Them",
};

export const FLIGHT_LABEL: Record<FlightKind, string> = {
  serve: "Serve",
  return: "Return",
  drop: "Drop",
  drive: "Drive",
  dink: "Dink",
  reset: "Reset",
  volley: "Volley",
  lob: "Lob",
  smash: "Smash",
  speedup: "Speed-up",
};

export const CAMERA_LABEL: Record<Camera, string> = { behind: "Behind you", side: "Side", top: "Top" };

export function isNear(id: ActorId): boolean {
  return id === "you" || id === "partner";
}

/** (a, b) for z(s) = a·s² + b·s + start: through both ends, highest point at apex. */
function curve(start: number, end: number, apex: number): [number, number] {
  const rise = apex - start;
  const change = end - start;
  const a = change - 2 * rise - 2 * Math.sqrt(Math.max(0, rise * (rise - change)));
  return [a, change - a];
}

/** The ball's height a fraction s (0 to 1) of the way along a flight. */
export function ballHeight(flight: Flight, s: number): number {
  const [a, b] = curve(flight.start.z, flight.end.z, flight.apex_z);
  return a * s * s + b * s + flight.start.z;
}

export function ballAt(flight: Flight, s: number): BallPoint {
  return {
    x: flight.start.x + (flight.end.x - flight.start.x) * s,
    y: flight.start.y + (flight.end.y - flight.start.y) * s,
    z: ballHeight(flight, s),
  };
}

/** The top of the net at x: lowest in the middle, rising to the posts. */
export function netHeight(x: number): number {
  const reach = COURT_WIDTH / 2 + POST_OUTSIDE;
  const fromMiddle = Math.min(Math.abs(x - COURT_WIDTH / 2), reach);
  return NET_MIDDLE + ((NET_POST - NET_MIDDLE) * fromMiddle) / reach;
}

export type ProblemCode = "same_side" | "net" | "out" | "wrong_side";

export interface Problem {
  code: ProblemCode;
  message: string;
  flight: number | null;
  actor: ActorId | null;
}

const PROBLEM_NAME: Record<ActorId, string> = {
  you: "You",
  partner: "Your partner",
  them_1: "Their first player",
  them_2: "Their second player",
};

function inCourt(x: number, y: number): boolean {
  return x >= 0 && x <= COURT_WIDTH && y >= 0 && y <= COURT_LENGTH;
}

/** What would stop this scene from being a real rally. The API refuses to publish until it's empty. */
export function problems(scene: Scene): Problem[] {
  const found: Problem[] = [];
  scene.flights.forEach((f, i) => {
    const number = String(i + 1);
    if ((f.start.y - NET_Y) * (f.end.y - NET_Y) >= 0) {
      found.push({ code: "same_side", message: `Shot ${number} doesn't go over the net.`, flight: i, actor: null });
      return;
    }
    const at = ballAt(f, (NET_Y - f.start.y) / (f.end.y - f.start.y));
    if (at.z - BALL_RADIUS < netHeight(at.x)) {
      found.push({ code: "net", message: `Shot ${number} hits the net.`, flight: i, actor: null });
    }
    if (f.end.z === 0 && !inCourt(f.end.x, f.end.y)) {
      found.push({ code: "out", message: `Shot ${number} lands out.`, flight: i, actor: null });
    }
  });
  for (const actor of scene.actors) {
    const near = isNear(actor.id);
    if (actor.keys.some((k) => (near ? k.y > NET_Y : k.y < NET_Y))) {
      found.push({
        code: "wrong_side",
        message: `${PROBLEM_NAME[actor.id]} can't cross the net.`,
        flight: null,
        actor: actor.id,
      });
    }
  }
  return found;
}

// Playback: where everything is at time t.

export interface ActorPose {
  x: number;
  y: number;
  stance: Stance;
}

/** A player's spot at t, moving in a straight line between keyframes. */
export function actorAt(actor: Actor, t: number): ActorPose {
  const keys = actor.keys;
  const first = keys[0];
  if (!first) {
    return { x: COURT_WIDTH / 2, y: isNear(actor.id) ? 2 : COURT_LENGTH - 2, stance: "ready" };
  }
  let before = first;
  for (const key of keys) {
    if (key.t <= t) {
      before = key;
    } else {
      const s = (t - before.t) / (key.t - before.t);
      return {
        x: before.x + (key.x - before.x) * s,
        y: before.y + (key.y - before.y) * s,
        stance: before.stance ?? "ready",
      };
    }
  }
  return { x: before.x, y: before.y, stance: before.stance ?? "ready" };
}

// Between flights the ball bounces up from where it landed to where it's hit next.
const BOUNCE_LIFT = 1.5;

/** Where the ball is at t, and which flight it's on (null between flights). */
export function ballAtTime(scene: Scene, t: number): { at: BallPoint; flight: number | null } | null {
  const flights = scene.flights;
  const first = flights[0];
  if (!first) {
    return null;
  }
  if (t <= first.t0) {
    return { at: first.start, flight: null };
  }
  for (let i = 0; i < flights.length; i++) {
    const f = flights[i];
    if (!f) {
      continue;
    }
    if (t <= f.t1) {
      return { at: ballAt(f, (t - f.t0) / (f.t1 - f.t0)), flight: i };
    }
    const next = flights[i + 1];
    if (next && t < next.t0) {
      const gap: Flight = {
        t0: f.t1,
        t1: next.t0,
        start: f.end,
        end: next.start,
        apex_z: Math.max(f.end.z, next.start.z) + (f.end.z === 0 ? BOUNCE_LIFT : 0),
        kind: f.kind,
      };
      return { at: ballAt(gap, (t - gap.t0) / (gap.t1 - gap.t0)), flight: null };
    }
  }
  const last = flights[flights.length - 1] ?? first;
  return { at: last.end, flight: null };
}

// How long a callout stays up.
export const CALLOUT_SECONDS = 2.5;

/** The callout showing at t, if any: the latest one that started within CALLOUT_SECONDS. */
export function calloutAt(scene: Scene, t: number): Callout | null {
  let showing: Callout | null = null;
  for (const c of scene.callouts) {
    if (c.t <= t && t < c.t + CALLOUT_SECONDS && (!showing || c.t >= showing.t)) {
      showing = c;
    }
  }
  return showing;
}

/** Points along a flight, for drawing its path. */
export function flightPath(flight: Flight, points = 24): BallPoint[] {
  return Array.from({ length: points + 1 }, (_, i) => ballAt(flight, i / points));
}

/** "0:03.5" */
export function clock(seconds: number): string {
  const whole = Math.floor(seconds);
  const tenths = Math.floor((seconds - whole) * 10);
  return `0:${String(whole).padStart(2, "0")}.${String(tenths)}`;
}

export type View = "3d" | "above";

/** Which view to open with: 3D, unless it can't be drawn or the device asks for less motion. */
export function firstView(webgl: boolean, reducedMotion: boolean): View {
  return webgl && !reducedMotion ? "3d" : "above";
}
