"use client";

import { GroupScoped } from "./group-scoped";
import { CourtArt } from "./ui/court-art";

export function GamesView() {
  return (
    <GroupScoped title="Games">
      {(group) => (
        <section className="flex animate-rise flex-col gap-4 rounded-2xl border border-line bg-surface p-5">
          <CourtArt className="w-40" />
          <h2 className="text-[20px] font-extrabold">No games in {group.name} yet</h2>
          <p className="text-[16px] leading-relaxed text-muted">
            Logging games comes in the next updates: pick who played, enter the score, and someone
            on the other team confirms it. Every game will show up here.
          </p>
        </section>
      )}
    </GroupScoped>
  );
}
