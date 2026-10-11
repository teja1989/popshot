"use client";

import { useState } from "react";

import { applyTheme, readTheme, type ThemeChoice } from "@/lib/theme";

import { useSignedIn } from "./auth";
import { SignOutButton } from "./sign-out-button";
import { Avatar } from "./ui/avatar";

const THEMES: { value: ThemeChoice; label: string }[] = [
  { value: "system", label: "Match device" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

const ANALYTICS = [
  { title: "Rating & form", body: "Your crew rating over time, last-10 form, streaks and where you rank." },
  { title: "Partners & rivals", body: "Who lifts your game, head-to-head records, your nemesis and upsets." },
  { title: "Scoring patterns", body: "Winning and losing margins, close games, skunks and deciding game 3s." },
  { title: "Activity", body: "Games per week, your most active days, doubles and singles." },
];

export function YouView() {
  const { me } = useSignedIn();
  // Rendered in the browser only (inside the app shell), so storage can be read up front.
  const [theme, setTheme] = useState<ThemeChoice>(readTheme);

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-6 px-5 pt-6 pb-12 lg:max-w-2xl lg:px-8 lg:pt-10">
      <section className="flex animate-rise items-center gap-4">
        <Avatar name={me?.display_name} photoUrl={me?.avatar_url} size="lg" />
        <div className="min-w-0">
          <h1 className="truncate text-[28px] leading-tight font-extrabold [font-stretch:110%]">
            {me?.display_name ?? "You"}
          </h1>
          <p className="text-[15px] text-muted">Signed in with Google</p>
        </div>
      </section>

      <section aria-labelledby="analytics-heading" className="flex animate-rise flex-col gap-3 [animation-delay:60ms]">
        <h2 id="analytics-heading" className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
          Your analytics
        </h2>
        <p className="text-[15px] text-muted">
          These fill in once your crew has confirmed games. Filter by 30 days, 90 days or all time.
        </p>
        <ul className="grid gap-2 sm:grid-cols-2">
          {ANALYTICS.map((item) => (
            <li key={item.title} className="rounded-2xl border border-dashed border-line p-4">
              <p className="text-[16px] font-bold">{item.title}</p>
              <p className="text-[14px] text-muted">{item.body}</p>
            </li>
          ))}
        </ul>
      </section>

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
