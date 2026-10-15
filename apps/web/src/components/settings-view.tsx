"use client";

import Link from "next/link";
import { useState } from "react";

import { applyTheme, readTheme, type ThemeChoice } from "@/lib/theme";

import { InviteCodeSection } from "./invite-code-section";
import { LegalLinks } from "./legal-page";
import { NotificationsSection } from "./notifications-section";
import { SharedCardsSection } from "./shared-cards-section";
import { SignOutButton } from "./sign-out-button";
import { YourDataSection } from "./your-data-section";
import { BackIcon } from "./ui/icons";
import { segmentOption, segmentTrack } from "./ui/segmented";

const THEMES: { value: ThemeChoice; label: string }[] = [
  { value: "system", label: "Match device" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

/**
 * You → Settings: how Popshot works for you, as opposed to how you play (that's You). Where an
 * app keeps its settings, behind the profile, so the tab bar stays at five.
 */
export function SettingsView() {
  // Rendered in the browser only (inside the app shell), so storage can be read up front.
  const [theme, setTheme] = useState<ThemeChoice>(readTheme);

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-6 px-5 pt-6 pb-12 lg:max-w-2xl lg:px-8 lg:pt-10">
      <Link
        href="/you"
        className="-ml-1 flex min-h-11 items-center gap-1.5 self-start text-body font-bold text-primary no-underline"
      >
        <BackIcon />
        You
      </Link>
      <h1 className="text-display-sm leading-tight font-extrabold tracking-[-0.02em] font-display">Settings</h1>

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
