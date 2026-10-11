"use client";

import { useAuth } from "./auth";
import { ExampleCards } from "./example-cards";
import { ArrowIcon, HandshakeIcon, PrivateIcon, StopwatchIcon } from "./ui/icons";
import { Brand } from "./ui/brand";
import { buttonClass } from "./ui/button";
import { CourtArt } from "./ui/court-art";

const PROMISES = [
  {
    icon: <StopwatchIcon />,
    title: "Log a game in 15 seconds",
    body: "Pick who played and the score, right at the fence.",
  },
  {
    icon: <HandshakeIcon />,
    title: "Fair records",
    body: "Someone on the other team confirms every score.",
  },
  {
    icon: <PrivateIcon />,
    title: "Private to your crew",
    body: "No public profiles, no search. Only your group sees its games.",
  },
];

export function SignInScreen() {
  const { busy, notice, signIn } = useAuth();
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col px-6 pt-12 pb-10">
      <Brand />
      <CourtArt rally className="mt-9 w-full" />
      <h1 className="mt-9 animate-rise text-[36px] leading-[1.08] font-[780] tracking-[-0.02em] [animation-delay:200ms] [font-stretch:108%]">
        Your crew&apos;s games, kept between you.
      </h1>
      <p className="mt-4 animate-rise text-[17px] leading-relaxed text-muted [animation-delay:300ms]">
        Log a game when you walk off the court. Popshot keeps the streaks, the rivalries and the
        partner you click with.
      </p>
      <button
        type="button"
        className={buttonClass("primary", "mt-8 h-14 w-full animate-rise [animation-delay:400ms]")}
        onClick={() => void signIn()}
        disabled={busy}
      >
        Continue with Google
        <ArrowIcon />
      </button>
      <p role="status" className="mt-3 min-h-6 text-center text-[15px] text-warn">
        {notice}
      </p>

      <div className="mt-6 animate-rise [animation-delay:500ms]">
        <ExampleCards />
      </div>

      <ul className="mt-8 flex flex-col gap-5" aria-label="How Popshot works">
        {PROMISES.map((promise) => (
          <li key={promise.title} className="flex gap-4">
            <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-chip text-primary">
              {promise.icon}
            </span>
            <span className="flex flex-col">
              <span className="text-[17px] font-bold">{promise.title}</span>
              <span className="text-[15px] text-muted">{promise.body}</span>
            </span>
          </li>
        ))}
      </ul>
    </main>
  );
}
