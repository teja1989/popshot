"use client";

import { useState } from "react";

import { applyTheme, readTheme, type ThemeChoice } from "@/lib/theme";

import { useSignedIn } from "./auth";
import { CrewPointsSection } from "./crew-points-section";
import { EditNameSheet } from "./edit-name-sheet";
import { FocusSection } from "./focus-section";
import { MyStatsSection } from "./my-stats-section";
import { SignOutButton } from "./sign-out-button";
import { Avatar } from "./ui/avatar";

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
          <h1 className="truncate text-[28px] leading-tight font-extrabold [font-stretch:110%]">
            {me?.display_name ?? "You"}
          </h1>
          <p className="text-[15px] text-muted">Signed in with Google</p>
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

      <fieldset className="flex animate-rise flex-col gap-3 [animation-delay:120ms]">
        <legend className="mb-3 text-xs font-bold tracking-[0.1em] text-muted uppercase">Appearance</legend>
        <div className="grid grid-cols-3 gap-1 rounded-xl bg-chip p-1">
          {THEMES.map((option) => (
            <label
              key={option.value}
              className="flex min-h-11 cursor-pointer items-center justify-center rounded-[10px] px-2 text-center text-[15px] font-bold text-muted has-[:checked]:bg-surface has-[:checked]:text-ink has-[:checked]:shadow-sm has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-primary"
            >
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

      <SignOutButton className="self-start" />
    </main>
  );
}
