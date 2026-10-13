"use client";

import { useReducedMotion } from "motion/react";
import Image from "next/image";
import { useState } from "react";

import { LANDING_PHOTOS } from "@/lib/landing-photos";

import { PauseIcon, PlayIcon } from "../ui/icons";

// A slow, endless strip of photos from courts. The list runs twice so the loop has no seam.
// It pauses on hover and has its own pause button (moving content needs one); reduced
// motion swaps it for a row you can swipe. Nothing shows until there are photos.
export function PhotoStrip() {
  const reduce = useReducedMotion();
  const [paused, setPaused] = useState(false);
  if (LANDING_PHOTOS.length === 0) {
    return null;
  }
  const tiles = (copy: number) =>
    LANDING_PHOTOS.map((photo, i) => (
      <figure
        key={`${String(copy)}-${photo.src}`}
        aria-hidden={copy > 0 ? true : undefined}
        className={`relative h-56 w-72 shrink-0 overflow-hidden rounded-3xl sm:h-72 sm:w-96 ${i % 2 === 1 ? "sm:mt-10" : ""}`}
      >
        <Image
          src={photo.src}
          alt={copy > 0 ? "" : photo.alt}
          fill
          sizes="(min-width: 640px) 384px, 288px"
          className="object-cover"
        />
      </figure>
    ));

  if (reduce) {
    return <div className="flex snap-x gap-4 overflow-x-auto px-6 pb-2">{tiles(0)}</div>;
  }
  return (
    <div className="relative">
      <div className="group overflow-hidden">
        <div
          className={`flex w-max animate-marquee gap-4 group-hover:[animation-play-state:paused] ${
            paused ? "[animation-play-state:paused]" : ""
          }`}
        >
          {tiles(0)}
          {tiles(1)}
        </div>
      </div>
      <button
        type="button"
        onClick={() => {
          setPaused(!paused);
        }}
        aria-label={paused ? "Play photos" : "Pause photos"}
        className="absolute right-6 bottom-3 flex size-11 cursor-pointer items-center justify-center rounded-full bg-surface/90 text-ink shadow"
      >
        {paused ? <PlayIcon /> : <PauseIcon />}
      </button>
    </div>
  );
}
