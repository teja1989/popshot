"use client";

import { useEffect, useState } from "react";

import { PauseIcon, PlayIcon } from "./ui/icons";

// Example cards on the sign-in screen: what Popshot tells you once your crew logs games.
// They advance on their own (unless "reduce motion" is on), and can be paused or picked,
// as anything that moves by itself for more than five seconds must (WCAG 2.2.2).

const ADVANCE_MS = 4500;

const EXAMPLES = [
  {
    label: "Your form",
    title: "3-game win streak",
    detail: "Last five games, oldest first",
    kind: "streak" as const,
  },
  {
    label: "Your nemesis",
    title: "Priya",
    detail: "2–5 against her this season",
    kind: "rival" as const,
  },
  {
    label: "Best partner",
    title: "Dev",
    detail: "9–2 when you play together",
    kind: "partner" as const,
  },
];

const STREAK = ["W", "L", "W", "W", "W"] as const;

export function ExampleCards() {
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => {
      setReducedMotion(query.matches);
    };
    update();
    query.addEventListener("change", update);
    return () => {
      query.removeEventListener("change", update);
    };
  }, []);

  const playing = !paused && !reducedMotion;
  useEffect(() => {
    if (!playing) {
      return;
    }
    const timer = window.setInterval(() => {
      setIndex((i) => (i + 1) % EXAMPLES.length);
    }, ADVANCE_MS);
    return () => {
      window.clearInterval(timer);
    };
  }, [playing]);

  const example = EXAMPLES[index] ?? EXAMPLES[0];
  if (!example) {
    return null;
  }

  return (
    <section
      aria-roledescription="carousel"
      aria-label="Examples of what Popshot shows you"
      className="flex flex-col gap-3"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-bold tracking-[0.1em] text-muted uppercase">What you&apos;ll see</h2>
        {!reducedMotion && (
          <button
            type="button"
            onClick={() => {
              setPaused((p) => !p);
            }}
            className="flex min-h-11 min-w-11 cursor-pointer items-center justify-center gap-1.5 rounded-full px-3 text-[13px] font-bold text-muted"
          >
            {paused ? <PlayIcon /> : <PauseIcon />}
            {paused ? "Play" : "Pause"}
          </button>
        )}
      </div>

      <div
        key={example.kind}
        aria-live={playing ? "off" : "polite"}
        aria-roledescription="slide"
        aria-label={`${String(index + 1)} of ${String(EXAMPLES.length)}`}
        className="relative flex min-h-[148px] animate-rise flex-col gap-3 rounded-2xl border border-line bg-surface p-5"
      >
        <span className="absolute top-4 right-4 rounded-full bg-chip px-2.5 py-0.5 text-[12px] font-bold text-muted">
          Example
        </span>
        <span className="text-xs font-bold tracking-[0.1em] text-muted uppercase">{example.label}</span>
        <span className="text-[24px] leading-tight font-extrabold [font-stretch:108%]">{example.title}</span>
        {example.kind === "streak" ? (
          <span className="flex gap-1.5" role="img" aria-label="Win, loss, win, win, win">
            {STREAK.map((result, i) => (
              <span
                key={`${result}-${String(i)}`}
                className={
                  result === "W"
                    ? "flex size-8 items-center justify-center rounded-lg bg-win text-[13px] font-extrabold text-on-win"
                    : "flex size-8 items-center justify-center rounded-lg border-[1.5px] border-dashed border-loss text-[13px] font-extrabold text-muted"
                }
              >
                {result}
              </span>
            ))}
          </span>
        ) : (
          <span className="text-[15px] text-muted">{example.detail}</span>
        )}
      </div>

      <div className="flex justify-center gap-1">
        {EXAMPLES.map((item, i) => (
          <button
            key={item.kind}
            type="button"
            aria-label={`Show example ${String(i + 1)} of ${String(EXAMPLES.length)}: ${item.label}`}
            aria-current={i === index ? "true" : undefined}
            onClick={() => {
              setIndex(i);
              setPaused(true);
            }}
            className="flex size-11 cursor-pointer items-center justify-center"
          >
            <span
              className={`block h-2 rounded-full transition-all duration-300 ease-court ${i === index ? "w-6 bg-primary" : "w-2 bg-line"}`}
            />
          </button>
        ))}
      </div>
    </section>
  );
}
