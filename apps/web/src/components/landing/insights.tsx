"use client";

import { animate, motion, useInView, useReducedMotion, useScroll, useTransform } from "motion/react";
import { useEffect, useRef, type ReactNode } from "react";

import { useEntrance } from "./reveal";

// Example crew insights and personal stats, shaped like the app's own Crew and You pages.

const CREW: { label: string; who: string; value: number; unit: string; hint?: string }[] = [
  { label: "Most games", who: "Jo", value: 14, unit: "games" },
  { label: "Best partnership", who: "Alex and Riley", value: 6, unit: "of 7", hint: "won together" },
  { label: "Welcome to the crew", who: "Pat and Kim", value: 2, unit: "new" },
  { label: "Longest win streak", who: "Riley", value: 4, unit: "wins" },
];

export function CrewInsights() {
  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {CREW.map((item, i) => (
        <InsightItem key={item.label} index={i}>
          <span className="flex min-w-0 flex-col">
            <span className="text-small font-bold text-muted">{item.label}</span>
            <span className="truncate text-lead font-bold">{item.who}</span>
          </span>
          <span className="shrink-0 text-right">
            <span className="text-title-lg leading-none font-extrabold font-numeral">
              <CountUp to={item.value} /> {item.unit}
            </span>
            {item.hint && <span className="block text-meta font-bold text-muted">{item.hint}</span>}
          </span>
        </InsightItem>
      ))}
    </ul>
  );
}

function InsightItem({ index, children }: { index: number; children: ReactNode }) {
  const entrance = useEntrance({ opacity: 0, y: 20 }, { delay: index * 0.08, duration: 0.5 }, 0.4);
  return (
    <motion.li
      className="flex items-center justify-between gap-4 rounded-3xl border border-transparent bg-surface shadow-card p-5"
      {...entrance}
    >
      {children}
    </motion.li>
  );
}

/** Counts up from 0 the first time it's on screen. Writes the text directly, no re-renders. */
function CountUp({ to }: { to: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const seen = useInView(ref, { once: true });
  const reduce = useReducedMotion();
  useEffect(() => {
    const node = ref.current;
    if (!seen || !node || reduce) {
      return;
    }
    const controls = animate(0, to, {
      duration: 1.1,
      ease: "easeOut",
      onUpdate: (value) => {
        node.textContent = String(Math.round(value));
      },
    });
    return () => {
      controls.stop();
    };
  }, [seen, to, reduce]);
  return <span ref={ref}>{to}</span>;
}

const FORM = ["W", "W", "L", "W", "W"] as const;

// Crew points over a month, as a line that draws itself as you scroll past.
const TREND = "M8 92 C 50 88, 70 70, 110 72 S 170 40, 210 52 S 270 30, 312 18";

export function YourStats() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 0.9", "center 0.5"] });
  // Reduced motion: the line is simply drawn.
  const still = useReducedMotion() === true;
  const draw = useTransform(scrollYProgress, [0, 1], still ? [1, 1] : [0, 1]);
  // The end dot lands as the line reaches it.
  const arrive = useTransform(scrollYProgress, [0.85, 1], still ? [1, 1] : [0, 1]);

  return (
    <div
      ref={ref}
      className="flex flex-col gap-3 rounded-3xl border border-transparent bg-surface shadow-card p-5 sm:p-6"
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-small font-bold text-muted">Crew points</p>
          <p className="text-display-sm leading-none font-extrabold font-numeral">3.42</p>
        </div>
        <p className="text-small font-bold text-win">▲ 0.21 in 30 days</p>
      </div>
      <svg viewBox="0 0 320 100" className="w-full overflow-visible" aria-hidden="true">
        <path d="M8 96H312" className="stroke-line" strokeWidth="1.5" fill="none" />
        <motion.path
          d={TREND}
          fill="none"
          strokeWidth="3.5"
          strokeLinecap="round"
          className="stroke-primary"
          style={{ pathLength: draw }}
        />
        <motion.circle
          cx="312"
          cy="18"
          r="6"
          className="fill-ball stroke-primary"
          strokeWidth="2.5"
          style={{ opacity: arrive }}
        />
      </svg>
      <div className="flex items-center gap-2">
        <span className="text-small font-bold text-muted">Form</span>
        {FORM.map((result, i) => (
          <FormChip key={i} result={result} index={i} />
        ))}
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Stat label="Close games" value="5–2" note="won–lost" />
        <Stat label="Best partner" value="Alex" note="9–2 together" />
      </div>
    </div>
  );
}

function FormChip({ result, index }: { result: "W" | "L"; index: number }) {
  const entrance = useEntrance(
    { opacity: 0, scale: 0.6 },
    { delay: 0.2 + index * 0.07, type: "spring", stiffness: 400, damping: 18 },
  );
  return (
    <motion.span
      className={`flex size-7 items-center justify-center rounded-md text-meta font-extrabold ${
        result === "W" ? "bg-win text-on-win" : "border border-dashed border-loss text-muted"
      }`}
      {...entrance}
    >
      {result}
    </motion.span>
  );
}

function Stat({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="rounded-xl bg-bg p-3">
      <p className="text-meta font-bold text-muted">{label}</p>
      <p className="text-title font-extrabold font-numeral">{value}</p>
      <p className="text-meta text-muted">{note}</p>
    </div>
  );
}
