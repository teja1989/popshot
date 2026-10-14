"use client";

import { useEffect, useRef, type RefObject } from "react";
import {
  BufferGeometry,
  CapsuleGeometry,
  CircleGeometry,
  DoubleSide,
  Color,
  DirectionalLight,
  Group,
  HemisphereLight,
  Line,
  LineBasicMaterial,
  LineDashedMaterial,
  Material,
  Mesh,
  MeshBasicMaterial,
  MeshLambertMaterial,
  PerspectiveCamera,
  PlaneGeometry,
  Scene as ThreeScene,
  SphereGeometry,
  Vector3,
  WebGLRenderer,
  type Object3D,
} from "three";

import {
  actorAt,
  BALL_RADIUS,
  ballAtTime,
  COURT_LENGTH,
  COURT_WIDTH,
  flightPath,
  isNear,
  KITCHEN,
  NET_MIDDLE,
  NET_POST,
  NET_Y,
  POST_OUTSIDE,
  type ActorId,
  type Camera,
  type Scene,
} from "@/lib/shot-scene";

// Court feet to three.js: x across from the middle, y up, z toward the near baseline.
const world = (x: number, y: number, z: number) => new Vector3(x - COURT_WIDTH / 2, z, NET_Y - y);

// Real court colours rather than the app theme: these read as a court in light and dark.
const COLOURS = {
  surround: "#3f7d5c",
  court: "#2f6aa3",
  kitchen: "#3c7cbd",
  line: "#ffffff",
  net: "#1b2229",
  ball: "#d7ea4c",
  shadow: "#000000",
  path: "#ffffff",
} as const;
const PLAYER: Record<ActorId, string> = {
  you: "#f28c38",
  partner: "#f6b26b",
  them_1: "#9aa5b1",
  them_2: "#c3cbd3",
};

const CAMERAS: Record<Camera, { at: Vector3; look: Vector3; up: Vector3 }> = {
  behind: { at: world(10, -15, 10), look: world(10, 21, 0), up: new Vector3(0, 1, 0) },
  side: { at: world(58, 22, 17), look: world(10, 22, 0), up: new Vector3(0, 1, 0) },
  // The near baseline at the bottom of the screen, like the diagram.
  top: { at: world(10, 22, 70), look: world(10, 22, 0), up: new Vector3(0, 0, -1) },
};

const BODY_HEIGHT = 3.2;
const HEAD = 0.45;
// Drawn a little bigger than life so it can be followed.
const BALL_SIZE = BALL_RADIUS * 2.2;

function flat(width: number, length: number, colour: string, x: number, y: number, lift: number): Mesh {
  const mesh = new Mesh(new PlaneGeometry(width, length), new MeshLambertMaterial({ color: colour }));
  mesh.rotation.x = -Math.PI / 2;
  mesh.position.copy(world(x, y, lift));
  return mesh;
}

function courtLine(x0: number, y0: number, x1: number, y1: number): Mesh {
  const width = 0.17;
  const along = x0 === x1;
  return flat(
    along ? width : Math.abs(x1 - x0) + width,
    along ? Math.abs(y1 - y0) + width : width,
    COLOURS.line,
    (x0 + x1) / 2,
    (y0 + y1) / 2,
    0.02,
  );
}

function buildCourt(): Group {
  const court = new Group();
  court.add(flat(COURT_WIDTH + 20, COURT_LENGTH + 24, COLOURS.surround, COURT_WIDTH / 2, NET_Y, 0));
  court.add(flat(COURT_WIDTH, COURT_LENGTH, COLOURS.court, COURT_WIDTH / 2, NET_Y, 0.005));
  court.add(flat(COURT_WIDTH, KITCHEN * 2, COLOURS.kitchen, COURT_WIDTH / 2, NET_Y, 0.01));
  for (const [x0, y0, x1, y1] of [
    [0, 0, COURT_WIDTH, 0],
    [0, COURT_LENGTH, COURT_WIDTH, COURT_LENGTH],
    [0, 0, 0, COURT_LENGTH],
    [COURT_WIDTH, 0, COURT_WIDTH, COURT_LENGTH],
    [0, NET_Y - KITCHEN, COURT_WIDTH, NET_Y - KITCHEN],
    [0, NET_Y + KITCHEN, COURT_WIDTH, NET_Y + KITCHEN],
    [COURT_WIDTH / 2, 0, COURT_WIDTH / 2, NET_Y - KITCHEN],
    [COURT_WIDTH / 2, NET_Y + KITCHEN, COURT_WIDTH / 2, COURT_LENGTH],
  ] as const) {
    court.add(courtLine(x0, y0, x1, y1));
  }
  // The net sags to 34" in the middle from 36" at the posts: two panels meeting there.
  const netMaterial = new MeshBasicMaterial({
    color: COLOURS.net,
    transparent: true,
    opacity: 0.55,
    side: DoubleSide,
  });
  const half = COURT_WIDTH / 2 + POST_OUTSIDE;
  for (const side of [-1, 1]) {
    const geometry = new BufferGeometry().setFromPoints([
      new Vector3(0, 0, 0),
      new Vector3(0, NET_MIDDLE, 0),
      new Vector3(side * half, NET_POST, 0),
      new Vector3(0, 0, 0),
      new Vector3(side * half, NET_POST, 0),
      new Vector3(side * half, 0, 0),
    ]);
    court.add(new Mesh(geometry, netMaterial));
  }
  const tape = new Line(
    new BufferGeometry().setFromPoints([
      new Vector3(-half, NET_POST, 0),
      new Vector3(0, NET_MIDDLE, 0),
      new Vector3(half, NET_POST, 0),
    ]),
    new LineBasicMaterial({ color: COLOURS.line }),
  );
  court.add(tape);
  return court;
}

function buildPlayer(id: ActorId): Group {
  const player = new Group();
  const material = new MeshLambertMaterial({ color: PLAYER[id] });
  // No faces: a body and a plain head.
  const body = new Mesh(new CapsuleGeometry(0.7, BODY_HEIGHT - 1.4, 4, 12), material);
  body.position.y = BODY_HEIGHT / 2;
  const head = new Mesh(new SphereGeometry(HEAD, 16, 12), material);
  head.position.y = BODY_HEIGHT + HEAD + 0.1;
  player.add(body, head);
  return player;
}

function dispose(root: Object3D) {
  root.traverse((child) => {
    if (child instanceof Mesh || child instanceof Line) {
      const geometry: unknown = child.geometry;
      const material: unknown = child.material;
      if (geometry instanceof BufferGeometry) {
        geometry.dispose();
      }
      for (const each of Array.isArray(material) ? (material as unknown[]) : [material]) {
        if (each instanceof Material) {
          each.dispose();
        }
      }
    }
  });
}

/**
 * The 3D view of a shot. Time comes from `time` (seconds), read every frame, so the controls
 * can move it without re-rendering React. Draws only while `active` and only when something
 * changed. Loaded on its own (next/dynamic), so three.js is only fetched where it's shown.
 */
export default function ShotPlayer3D({
  scene,
  time,
  camera,
  active,
  onLost,
  label,
}: {
  scene: Scene;
  time: RefObject<number>;
  camera: Camera;
  active: boolean;
  onLost: () => void;
  label: string;
}) {
  const host = useRef<HTMLDivElement>(null);
  const cameraRef = useRef<{ set: (c: Camera) => void } | null>(null);
  const activeRef = useRef<{ set: (on: boolean) => void } | null>(null);

  useEffect(() => {
    const element = host.current;
    if (!element) {
      return;
    }
    let renderer: WebGLRenderer;
    try {
      renderer = new WebGLRenderer({ antialias: true, powerPreference: "low-power" });
    } catch {
      onLost();
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    const canvas = renderer.domElement;
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", label);
    canvas.className = "block h-full w-full";
    element.append(canvas);

    const world3d = new ThreeScene();
    world3d.background = new Color(COLOURS.surround);
    world3d.add(new HemisphereLight(0xffffff, 0x445544, 1.6));
    const sun = new DirectionalLight(0xffffff, 1.4);
    sun.position.set(-12, 30, 18);
    world3d.add(sun);
    world3d.add(buildCourt());

    const players = new Map(scene.actors.map((a) => [a.id, buildPlayer(a.id)]));
    for (const p of players.values()) {
      world3d.add(p);
    }

    const ball = new Mesh(new SphereGeometry(BALL_SIZE, 16, 12), new MeshLambertMaterial({ color: COLOURS.ball }));
    const shadow = new Mesh(
      new CircleGeometry(BALL_SIZE * 1.2, 16),
      new MeshBasicMaterial({ color: COLOURS.shadow, transparent: true, opacity: 0.3 }),
    );
    shadow.rotation.x = -Math.PI / 2;
    world3d.add(ball, shadow);

    const paths = scene.flights.map((f) => {
      const line = new Line(
        new BufferGeometry().setFromPoints(flightPath(f, 40).map((p) => world(p.x, p.y, p.z))),
        new LineDashedMaterial({ color: COLOURS.path, dashSize: 0.5, gapSize: 0.35, transparent: true }),
      );
      line.computeLineDistances();
      world3d.add(line);
      return line;
    });

    const view = new PerspectiveCamera(42, 1, 0.5, 300);
    let dirty = true;
    function aim(which: Camera) {
      const preset = CAMERAS[which];
      view.position.copy(preset.at);
      view.up.copy(preset.up);
      view.lookAt(preset.look);
      dirty = true;
    }
    aim(camera);
    cameraRef.current = { set: aim };

    const resize = () => {
      const { clientWidth, clientHeight } = element;
      if (clientWidth === 0 || clientHeight === 0) {
        return;
      }
      renderer.setSize(clientWidth, clientHeight, false);
      view.aspect = clientWidth / clientHeight;
      view.updateProjectionMatrix();
      dirty = true;
    };

    resize();
    const watcher = new ResizeObserver(resize);
    watcher.observe(element);

    let shown = Number.NaN;
    function frame() {
      const t = time.current;
      if (t === shown && !dirty) {
        return;
      }
      shown = t;
      dirty = false;
      for (const actor of scene.actors) {
        const pose = actorAt(actor, t);
        const player = players.get(actor.id);
        if (player) {
          player.position.copy(world(pose.x, pose.y, pose.stance === "split" ? 0.25 : 0));
          player.scale.y = pose.stance === "low" ? 0.82 : 1;
          // Face the net.
          player.rotation.y = isNear(actor.id) ? 0 : Math.PI;
        }
      }
      const where = ballAtTime(scene, t);
      ball.visible = shadow.visible = where !== null;
      if (where) {
        ball.position.copy(world(where.at.x, where.at.y, where.at.z + BALL_SIZE));
        shadow.position.copy(world(where.at.x, where.at.y, 0.03));
      }
      paths.forEach((line, i) => {
        line.material.opacity = where?.flight === i ? 1 : 0.35;
      });
      renderer.render(world3d, view);
    }
    function run(on: boolean) {
      renderer.setAnimationLoop(on ? frame : null);
      if (on) {
        dirty = true;
      }
    }
    activeRef.current = { set: run };
    run(active);

    function lost(event: Event) {
      event.preventDefault();
      onLost();
    }
    canvas.addEventListener("webglcontextlost", lost);

    return () => {
      canvas.removeEventListener("webglcontextlost", lost);
      watcher.disconnect();
      renderer.setAnimationLoop(null);
      dispose(world3d);
      renderer.dispose();
      canvas.remove();
      cameraRef.current = null;
      activeRef.current = null;
    };
    // Built once per scene; camera and active are applied below without rebuilding.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scene]);

  useEffect(() => {
    cameraRef.current?.set(camera);
  }, [camera]);
  useEffect(() => {
    activeRef.current?.set(active);
  }, [active]);

  return <div ref={host} className="size-full" />;
}
