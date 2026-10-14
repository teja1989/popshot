"use client";

import { useState } from "react";

import { applyTheme, readTheme, type ThemeChoice } from "@/lib/theme";

import { useSignedIn } from "./auth";
import { CrewPointsSection } from "./crew-points-section";
import { EditNameSheet } from "./edit-name-sheet";
import { FocusSection } from "./focus-section";
import { InviteCodeSection } from "./invite-code-section";
import { MyStatsSection } from "./my-stats-section";
import { NotificationsSection } from "./notifications-section";
import { LegalLinks } from "./legal-page";
import { SharedCardsSection } from "./shared-cards-section";
import { SignOutButton } from "./sign-out-button";
import { YourDataSection } from "./your-data-section";
import { Avatar } from "./ui/avatar";
import { segmentOption, segmentTrack } from "./ui/segmented";

const THEMES: { value: ThemeChoice; label: string }[] = [
  { value: "system", label: "Match device" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

export function YouView() {
  const { me } = useSignedIn();
  // Rendered in the browser only (inside the app shell), so storage can be read up front.
  const [theme, setTheme] = useState<ThemeChoice>(readTheme);

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-6 px-5 pt-6 pb-12 lg:max-w-2xl lg:px-8 lg:pt-10">
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
      </section>

      <CrewPointsSection />

      <MyStatsSection />

      <FocusSection />

      <NotificationsSection />

      <InviteCodeSection />

      <SharedCardsSection />

      <fieldset className="flex animate-rise flex-col gap-3 [animation-delay:120ms]">
        <legend className="mb-3 text-title-sm font-bold text-ink">Appearance</legend>
        <div className={`${segmentTrack} grid-cols-3`}>
          {THEMES.map((option) => (
            <label key={option.value} className={`${segmentOption} text-center`}>
              <input
                type="radio"
                name="theme"
                value={option.value}
                checked={theme === option.value}
                onChange={() => {
                  setTheme(option.value);
                  applyTheme(option.value);
                }}
                className="sr-only"
              />
              {option.label}
            </label>
          ))}
        </div>
      </fieldset>

      <YourDataSection />

      <SignOutButton className="self-start" />
      <LegalLinks className="text-body" />
    </main>
  );
}
