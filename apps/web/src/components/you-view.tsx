"use client";

import Link from "next/link";

import { useSignedIn } from "./auth";
import { CrewPointsSection } from "./crew-points-section";
import { EditNameSheet } from "./edit-name-sheet";
import { FocusSection } from "./focus-section";
import { GameMapSection } from "./game-map-section";
import { MyStatsSection } from "./my-stats-section";
import { YouTabs } from "./you-tabs";
import { Avatar } from "./ui/avatar";
import { SettingsIcon } from "./ui/icons";

/** You: how you play. How Popshot works for you is one tap away, in Settings. */
export function YouView() {
  const { me } = useSignedIn();

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-6 px-5 pt-6 pb-12 lg:max-w-2xl lg:px-8 lg:pt-10">
      <YouTabs />
      <section className="flex animate-rise items-center gap-4">
        <Avatar name={me?.display_name} photoUrl={me?.avatar_url} size="lg" />
        <div className="min-w-0 grow">
          <h1 className="truncate text-title-lg leading-tight font-extrabold font-display">
            {me?.display_name ?? "You"}
          </h1>
          <p className="text-body text-muted">Signed in with Google</p>
          {me && (
            <div className="mt-2">
              <EditNameSheet />
            </div>
          )}
        </div>
        <Link
          href="/you/settings"
          aria-label="Settings"
          className="flex size-12 shrink-0 items-center justify-center self-start rounded-full text-muted no-underline hover:bg-surface-high hover:text-ink"
        >
          <SettingsIcon />
        </Link>
      </section>

      <GameMapSection />

      <CrewPointsSection />

      <MyStatsSection />

      <FocusSection />
    </main>
  );
}
