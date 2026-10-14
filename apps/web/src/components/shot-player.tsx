"use client";

import dynamic from "next/dynamic";
import { useEffect, useId, useRef, useState } from "react";

import {
  CAMERA_LABEL,
  calloutAt,
  clock,
  firstView,
  FLIGHT_LABEL,
  type Camera,
  type Scene,
  type View,
} from "@/lib/shot-scene";

import { ShotDiagram } from "./shot-diagram";
import { segmentOption, segmentTrack } from "./ui/segmented";

// three.js is only fetched where a shot is shown.
const ShotPlayer3D = dynamic(() => import("./shot-player-3d"), {
  ssr: false,
  loading: () => <p className="grid size-full place-items-center text-body text-muted">Loading the 3D view…</p>,
});

type Speed = 0.5 | 1;

/** Whether this browser can draw 3D. False on old devices and where WebGL is switched off. */
export function canDraw3d(): boolean {
  try {
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl2") ?? canvas.getContext("webgl");
    // Hand the context back straight away: browsers allow only a few at once.
    gl?.getExtension("WEBGL_lose_context")?.loseContext();
    return gl !== null;
  } catch {
    return false;
  }
}

/**
 * A shot's scene with play, pause, a timeline and speed, in 3D or from above. Nothing plays
 * until asked. Pauses when scrolled out of sight.
 */
export function ShotPlayer({ scene, title }: { scene: Scene; title: string }) {
  const name = useId();
  const [webgl, setWebgl] = useState<boolean | null>(null);
  const [view, setView] = useState<View>("above");
  const [camera, setCamera] = useState<Camera>(scene.camera);
  const [speed, setSpeed] = useState<Speed>(1);
  const [playing, setPlaying] = useState(false);
  const [t, setT] = useState(0);
  const [onScreen, setOnScreen] = useState(true);
  const time = useRef(0);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const can = canDraw3d();
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    setWebgl(can);
    setView(firstView(can, reduced));
  }, []);

  useEffect(() => {
    const element = box.current;
    if (!element) {
      return;
    }
    const watcher = new IntersectionObserver(([entry]) => {
      setOnScreen(entry?.isIntersecting ?? true);
    });
    watcher.observe(element);
    return () => {
      watcher.disconnect();
    };
  }, []);

  useEffect(() => {
    if (!playing || !onScreen) {
      return;
    }
    let last = performance.now();
    let frame = requestAnimationFrame(function step(now) {
      const next = Math.min(scene.duration, time.current + ((now - last) / 1000) * speed);
      last = now;
      time.current = next;
      setT(next);
      if (next >= scene.duration) {
        setPlaying(false);
        return;
      }
      frame = requestAnimationFrame(step);
    });
    return () => {
      cancelAnimationFrame(frame);
    };
  }, [playing, onScreen, speed, scene.duration]);

  function seek(to: number) {
    time.current = to;
    setT(to);
  }

  function togglePlay() {
    if (!playing && time.current >= scene.duration) {
      seek(0);
    }
    setPlaying(!playing);
  }

  const atEnd = t >= scene.duration;
  const callout = calloutAt(scene, t);
  const shots = scene.flights.map((f) => FLIGHT_LABEL[f.kind]).join(", ");

  return (
    <div className="flex flex-col gap-3">
      <div
        ref={box}
        className={`relative overflow-hidden rounded-2xl border border-line bg-surface ${
          view === "3d" ? "aspect-[4/3] sm:aspect-[16/10]" : "flex justify-center p-2"
        }`}
      >
        {view === "3d" && webgl ? (
          <ShotPlayer3D
            scene={scene}
            time={time}
            camera={camera}
            active={onScreen}
            label={`${title}, in 3D. ${shots ? `Shots in order: ${shots}.` : ""}`}
            onLost={() => {
              setWebgl(false);
              setView("above");
            }}
          />
        ) : (
          <ShotDiagram scene={scene} t={t} className="max-h-[70vh] w-full max-w-sm" />
        )}
      </div>
      <p aria-live="polite" className="min-h-6 text-center text-body font-bold">
        {callout?.text ?? ""}
      </p>
      <div className="flex items-center gap-3">
        <button
          type="button"
          className="grid size-12 shrink-0 cursor-pointer place-items-center rounded-xl bg-primary text-on-primary transition-transform duration-150 ease-court hover:-translate-y-px active:translate-y-px"
          aria-label={playing ? "Pause" : atEnd ? "Play again" : "Play"}
          onClick={togglePlay}
        >
          {playing ? (
            <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true" className="fill-current">
              <rect x="4.5" y="3.5" width="4" height="13" rx="1" />
              <rect x="11.5" y="3.5" width="4" height="13" rx="1" />
            </svg>
          ) : (
            <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true" className="fill-current">
              <path d="M6 3.8v12.4a1 1 0 0 0 1.5.86l10-6.2a1 1 0 0 0 0-1.72l-10-6.2A1 1 0 0 0 6 3.8z" />
            </svg>
          )}
        </button>
        <input
          type="range"
          aria-label="Time"
          aria-valuetext={clock(t)}
          min={0}
          max={scene.duration}
          step={0.1}
          value={t}
          onChange={(event) => {
            setPlaying(false);
            seek(Number(event.target.value));
          }}
          className="min-h-11 grow accent-primary"
        />
        <span className="w-14 shrink-0 text-right text-small text-muted tabular-nums">{clock(t)}</span>
      </div>
      <div className="flex flex-wrap gap-2">
        <fieldset className={`${segmentTrack} grid-cols-2`}>
          <legend className="sr-only">Speed</legend>
          {(
            [
              [0.5, "Slow"],
              [1, "Normal"],
            ] as const
          ).map(([value, label]) => (
            <label key={value} className={segmentOption}>
              <input
                type="radio"
                name={`${name}-speed`}
                className="sr-only"
                checked={speed === value}
                onChange={() => {
                  setSpeed(value);
                }}
              />
              {label}
            </label>
          ))}
        </fieldset>
        {webgl && (
          <fieldset className={`${segmentTrack} grid-cols-2`}>
            <legend className="sr-only">View</legend>
            {(
              [
                ["3d", "3D"],
                ["above", "From above"],
              ] as const
            ).map(([value, label]) => (
              <label key={value} className={segmentOption}>
                <input
                  type="radio"
                  name={`${name}-view`}
                  className="sr-only"
                  checked={view === value}
                  onChange={() => {
                    setView(value);
                  }}
                />
                {label}
              </label>
            ))}
          </fieldset>
        )}
        {webgl && view === "3d" && (
          <fieldset className={`${segmentTrack} grid-cols-3`}>
            <legend className="sr-only">Camera</legend>
            {(["behind", "side", "top"] as const).map((value) => (
              <label key={value} className={segmentOption}>
                <input
                  type="radio"
                  name={`${name}-camera`}
                  className="sr-only"
                  checked={camera === value}
                  onChange={() => {
                    setCamera(value);
                  }}
                />
                {CAMERA_LABEL[value]}
              </label>
            ))}
          </fieldset>
        )}
      </div>
      {webgl === false && (
        <p className="text-small text-muted">
          This device can&apos;t show 3D, so you&apos;re seeing the court from above.
        </p>
      )}
    </div>
  );
}
