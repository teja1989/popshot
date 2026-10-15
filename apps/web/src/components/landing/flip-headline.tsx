"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useState } from "react";

import { FIRST, HEADLINES, HOLD_MS, headlineOrder, headlineText, type Headline } from "@/lib/headlines";

// A scoreboard for the landing headline: every letter flips over, left to right, to the next
// line about pickleball and staying well. Screen readers and search engines get one steady
// heading (the first line); the flipping board beside it is decoration. With "reduce motion"
// the board stays on the first line. It rests while the tab is hidden.

const FLIP = { duration: 0.32, ease: [0.3, 0.7, 0.2, 1] } as const;
const STAGGER = 0.028;
// The old line clears faster than the new one arrives.
const OUT = { duration: 0.2, ease: [0.4, 0, 1, 1] } as const;
const OUT_STAGGER = 0.012;

export function FlipHeadline({ className = "" }: { className?: string }) {
  const still = useReducedMotion() === true;
  // Shuffled once, in the browser (this page renders client-side only), always opening with
  // the first line.
  const [order] = useState<Headline[]>(() => headlineOrder());
  const [index, setIndex] = useState(0);
  const [hidden, setHidden] = useState(() => document.visibilityState === "hidden");

  useEffect(() => {
    const update = () => {
      setHidden(document.visibilityState === "hidden");
    };
    document.addEventListener("visibilitychange", update);
    return () => {
      document.removeEventListener("visibilitychange", update);
    };
  }, []);

  useEffect(() => {
    if (still || hidden || order.length < 2) {
      return;
    }
    const timer = window.setTimeout(() => {
      setIndex((i) => (i + 1) % order.length);
    }, HOLD_MS);
    return () => {
      window.clearTimeout(timer);
    };
  }, [still, hidden, order.length, index]);

  const current = (still ? FIRST : order[index]) ?? FIRST;

  return (
    <div className={className}>
      <h1 className="sr-only">{headlineText(FIRST)}</h1>
      <p aria-hidden="true" className="grid [perspective:800px]" data-headline={headlineText(current)}>
        {/* Every line, invisible, in the same cell: the board is as tall as the tallest one,
            so nothing below it jumps when a shorter or longer line flips in. */}
        {HEADLINES.map((line) => (
          <span key={headlineText(line)} className="invisible [grid-area:1/1]">
            <Line line={line} />
          </span>
        ))}
        <AnimatePresence initial={false} mode="wait">
          <span key={`${String(index)}-${headlineText(current)}`} className="[grid-area:1/1]">
            <Line line={current} flip={!still} />
          </span>
        </AnimatePresence>
      </p>
    </div>
  );
}

/** One line, split into words that never break apart; with `flip`, each letter flips. */
function Line({ line, flip = false }: { line: Headline; flip?: boolean }) {
  let n = 0;
  const words = (text: string, accent: boolean) =>
    text.split(" ").map((word, w) => (
      <span key={`${String(accent)}-${String(w)}`}>
        {w > 0 && " "}
        <span className={`inline-block whitespace-nowrap ${accent ? "text-ball" : ""}`}>
          {/* Our own plain-ASCII lines (headlines.ts): one character is one letter. */}
          {/* eslint-disable-next-line @typescript-eslint/no-misused-spread */}
          {[...word].map((char, c) => {
            const i = n++;
            return flip ? (
              <motion.span
                key={c}
                className="inline-block origin-center [backface-visibility:hidden]"
                initial={{ rotateX: -90, opacity: 0 }}
                animate={{ rotateX: 0, opacity: 1, transition: { ...FLIP, delay: i * STAGGER } }}
                exit={{ rotateX: 90, opacity: 0, transition: { ...OUT, delay: i * OUT_STAGGER } }}
              >
                {char}
              </motion.span>
            ) : (
              <span key={c}>{char}</span>
            );
          })}
        </span>
      </span>
    ));
  return (
    <>
      {words(line.lead, false)} {words(line.accent, true)}
    </>
  );
}
