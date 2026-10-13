"use client";

import { AnimatePresence, motion, useInView, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";

import { DEMO_RALLIES, demoScore } from "@/lib/landing-demo";

// A made-up doubles game playing out on a court: the ball goes back and forth, the score
// ticks up to 11–9, then it's logged and the recap's ready. Then it plays again. Only runs
// while on screen, and shows the finished game instead for people who reduce motion.

const RALLY_MS = 900;
const PAUSE_AFTER_GAME_MS = 3800;

type Phase = "playing" | "logged";

export function RallyDemo() {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const visible = useInView(ref, { amount: 0.3 });
  const [rallies, setRallies] = useState(0);
  const [current, setPhase] = useState<Phase>("playing");
  // Reduced motion: the finished game, still.
  const played = reduce ? DEMO_RALLIES.length : rallies;
  const phase: Phase = reduce ? "logged" : current;

  useEffect(() => {
    if (reduce || !visible) {
      return;
    }
    if (phase === "logged") {
      const restart = setTimeout(() => {
        setRallies(0);
        setPhase("playing");
      }, PAUSE_AFTER_GAME_MS);
      return () => {
        clearTimeout(restart);
      };
    }
    const next = setTimeout(() => {
      if (rallies >= DEMO_RALLIES.length) {
        setPhase("logged");
      } else {
        setRallies(rallies + 1);
      }
    }, RALLY_MS);
    return () => {
      clearTimeout(next);
    };
  }, [reduce, visible, phase, rallies]);

  const score = demoScore(played);
  const lastWinner = played > 0 ? DEMO_RALLIES[played - 1] : null;
  // The ball travels toward whoever is about to hit it: alternate each rally.
  const toRight = played % 2 === 0;

  return (
    <div ref={ref} aria-hidden="true" className="relative mx-auto w-full max-w-[440px]">
      <div className="rounded-[28px] bg-surface p-4 text-ink shadow-[0_30px_80px_-30px_rgb(0_0_0/0.6)] sm:p-5">
        <div className="flex items-center justify-between">
          <span className="text-meta font-bold tracking-[0.12em] text-muted uppercase">Tuesday doubles</span>
          <span className="rounded-full bg-chip px-2.5 py-0.5 text-micro font-bold text-muted">Example</span>
        </div>

        <div className="mt-3 grid grid-cols-[1fr_auto_1fr] items-center gap-3">
          <Team name="You & Alex" won={lastWinner === "A" && phase === "playing"} />
          <div className="flex items-center gap-2 text-display leading-none font-extrabold font-numeral">
            <Digit value={score.a} />
            <span className="text-muted">–</span>
            <Digit value={score.b} />
          </div>
          <Team name="Riley & Sam" won={lastWinner === "B" && phase === "playing"} right />
        </div>

        <div className="relative mt-4 overflow-hidden rounded-2xl bg-hero">
          <svg viewBox="0 0 400 200" className="block w-full stroke-on-hero/50">
            <rect x="10" y="10" width="380" height="180" rx="6" fill="none" strokeWidth="3" />
            <path d="M140 10v180M260 10v180M10 100h130M260 100h130" fill="none" strokeWidth="2" />
            <path d="M200 6v188" className="stroke-on-hero" fill="none" strokeWidth="5" />
          </svg>
          <Paddle side="left" active={!toRight && phase === "playing"} />
          <Paddle side="right" active={toRight && phase === "playing"} />
          {phase === "playing" && (
            <motion.span
              className="absolute top-1/2 left-0 size-4 -translate-y-1/2 rounded-full bg-ball shadow-[0_6px_10px_rgb(0_0_0/0.35)] sm:size-5"
              initial={false}
              animate={{
                left: toRight ? "82%" : "15%",
                scale: [1, 1.45, 1],
                top: toRight ? ["62%", "40%", "38%"] : ["38%", "55%", "62%"],
              }}
              transition={{ duration: RALLY_MS / 1000, ease: "easeInOut" }}
            />
          )}
          <AnimatePresence>
            {phase === "logged" && (
              <motion.div
                className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-hero/85 text-on-hero"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <motion.span
                  className="flex size-11 items-center justify-center rounded-full bg-ball text-title font-extrabold text-on-ball"
                  initial={{ scale: 0.4 }}
                  animate={{ scale: 1 }}
                  transition={{ type: "spring", stiffness: 380, damping: 16 }}
                >
                  ✓
                </motion.span>
                <span className="text-title-sm font-extrabold font-display">Logged. 11–9.</span>
                <span className="text-small text-on-hero-muted">Your crew sees it straight away.</span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <AnimatePresence>
          {phase === "logged" && (
            <motion.div
              className="mt-3 flex items-center gap-3 rounded-2xl border border-line bg-bg p-3"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ delay: 0.5 }}
            >
              <span className="rounded-lg bg-ball px-2 py-1 text-micro font-extrabold tracking-[0.08em] text-on-ball uppercase">
                Recap
              </span>
              <span className="text-small font-bold">Close Call for You &amp; Alex: won by two.</span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

function Team({ name, won, right = false }: { name: string; won: boolean; right?: boolean }) {
  return (
    <span className={`flex flex-col gap-1 ${right ? "items-end text-right" : ""}`}>
      <span className="text-small leading-tight font-bold">{name}</span>
      <motion.span
        className="h-1 w-8 rounded-full bg-ball"
        initial={false}
        animate={{ opacity: won ? 1 : 0, scaleX: won ? 1 : 0.3 }}
      />
    </span>
  );
}

function Digit({ value }: { value: number }) {
  return (
    // Old and new digits share one grid cell while they swap. (Not AnimatePresence's
    // popLayout mode: it adds a <style> element, which the CSP blocks.)
    <span className="inline-grid min-w-[1.1ch] justify-items-center overflow-hidden">
      <AnimatePresence initial={false}>
        <motion.span
          key={value}
          className="col-start-1 row-start-1"
          initial={{ y: "-60%", opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: "60%", opacity: 0 }}
          transition={{ type: "spring", stiffness: 420, damping: 30 }}
        >
          {value}
        </motion.span>
      </AnimatePresence>
    </span>
  );
}

function Paddle({ side, active }: { side: "left" | "right"; active: boolean }) {
  return (
    <motion.span
      className={`absolute top-1/2 h-12 w-3 -translate-y-1/2 rounded-full bg-on-hero sm:h-14 ${side === "left" ? "left-[8%]" : "right-[8%]"}`}
      initial={false}
      animate={{ rotate: active ? (side === "left" ? 18 : -18) : 0, opacity: active ? 1 : 0.7 }}
      transition={{ type: "spring", stiffness: 300, damping: 18 }}
    />
  );
}
