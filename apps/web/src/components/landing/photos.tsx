"use client";

import { motion, useReducedMotion, useScroll, useTransform } from "motion/react";
import { useRef } from "react";

import { COURT_AERIAL, PADDLE_AND_BALLS } from "@/lib/landing-photos";

import aerial1600 from "./photos/court-aerial-1600.webp";
import aerial800 from "./photos/court-aerial-800.webp";
import paddle1600 from "./photos/paddle-and-balls-1600.webp";
import paddle800 from "./photos/paddle-and-balls-800.webp";

// The landing page's two photos. Plain <img> with a srcset of files bundled into
// /_next/static, so they're served like the app's other assets (cached, no image proxy).

/** The court from above, behind the hero, under a court-blue wash so the words stay clear. */
export function HeroPhoto() {
  const reduce = useReducedMotion();
  const { scrollY } = useScroll();
  // A slow push-in as the page scrolls.
  const scale = useTransform(scrollY, [0, 700], reduce ? [1.05, 1.05] : [1.05, 1.18]);
  return (
    <div aria-hidden="true" className="absolute inset-0 -z-10 overflow-hidden">
      <motion.img
        src={aerial1600.src}
        srcSet={`${aerial800.src} 800w, ${aerial1600.src} 1600w`}
        sizes="100vw"
        alt=""
        width={aerial1600.width}
        height={aerial1600.height}
        className="h-full w-full object-cover"
        style={{ scale }}
      />
      <div className="absolute inset-0 bg-hero/80" />
    </div>
  );
}

/** A wide photo band that drifts a little slower than the page as you scroll past. */
export function PhotoBand() {
  const ref = useRef<HTMLElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end start"] });
  const y = useTransform(scrollYProgress, [0, 1], reduce ? ["0%", "0%"] : ["-8%", "8%"]);
  return (
    <section
      ref={ref}
      aria-labelledby="courts-heading"
      className="relative isolate mx-auto mt-16 flex min-h-[340px] max-w-6xl items-end overflow-hidden px-6 py-8 sm:mx-6 sm:min-h-[420px] sm:rounded-[32px] sm:px-10 lg:mx-auto lg:min-h-[480px] lg:px-14 lg:py-12"
    >
      <motion.img
        src={paddle1600.src}
        srcSet={`${paddle800.src} 800w, ${paddle1600.src} 1600w`}
        sizes="(min-width: 1152px) 1152px, 100vw"
        alt={PADDLE_AND_BALLS.alt}
        width={paddle1600.width}
        height={paddle1600.height}
        loading="lazy"
        className="absolute inset-0 -z-10 h-[116%] w-full -translate-y-[8%] object-cover"
        style={{ y }}
      />
      {/* A dark scrim at the bottom so the words read over the court. */}
      <div
        aria-hidden="true"
        className="absolute inset-0 -z-10 bg-linear-to-t from-[#06140f]/85 via-[#06140f]/30 to-transparent"
      />
      <div className="max-w-xl text-on-hero">
        <h2 id="courts-heading" className="text-display-sm font-extrabold tracking-[-0.02em] lg:text-display">
          Made for the courts you already play on.
        </h2>
        <p className="mt-3 text-lead text-on-hero-muted">
          Park courts, school gyms, the club on Thursday nights. Wherever your crew plays, Popshot keeps the score.
        </p>
      </div>
    </section>
  );
}

/** The same court in full colour, for the "Play" step. */
export function CourtPhoto() {
  return (
    <img
      src={aerial1600.src}
      srcSet={`${aerial800.src} 800w, ${aerial1600.src} 1600w`}
      sizes="(min-width: 1024px) 560px, 100vw"
      alt={COURT_AERIAL.alt}
      width={aerial1600.width}
      height={aerial1600.height}
      loading="lazy"
      className="block h-auto w-full rounded-3xl"
    />
  );
}
