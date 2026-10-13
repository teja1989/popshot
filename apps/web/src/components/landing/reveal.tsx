"use client";

import { motion, useReducedMotion, type MotionProps, type TargetAndTransition, type Transition } from "motion/react";
import type { ReactNode } from "react";

/**
 * Props that bring an element in the first time it scrolls into view, starting from `from`.
 * For people who reduce motion it's simply there: no fade-in that waits for scrolling.
 */
export function useEntrance(
  from: TargetAndTransition,
  transition: Transition = {},
  amount = 0.25,
): Pick<MotionProps, "initial" | "whileInView" | "viewport" | "transition"> {
  const reduce = useReducedMotion();
  if (reduce) {
    return {};
  }
  const to = Object.fromEntries(
    Object.keys(from).map((key) => [key, key === "opacity" || key === "scale" ? 1 : 0]),
  ) as TargetAndTransition;
  return { initial: from, whileInView: to, viewport: { once: true, amount }, transition };
}

/** Fades and lifts its content in the first time it scrolls into view. */
export function Reveal({
  children,
  delay = 0,
  className = "",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  const entrance = useEntrance({ opacity: 0, y: 28 }, { duration: 0.6, delay, ease: [0.3, 0.7, 0.2, 1] });
  return (
    <motion.div className={className} {...entrance}>
      {children}
    </motion.div>
  );
}
