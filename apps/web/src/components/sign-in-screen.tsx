"use client";

import { useAuth } from "./auth";
import { ArrowIcon, LockIcon } from "./ui/icons";
import { Brand } from "./ui/brand";
import { buttonClass } from "./ui/button";
import { CourtArt } from "./ui/court-art";

export function SignInScreen() {
  const { busy, notice, signIn } = useAuth();
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col px-7 pt-14 pb-9">
      <Brand />
      <CourtArt className="mt-11 w-full" />
      <h1 className="mt-10 animate-rise text-[36px] leading-[1.08] font-[780] tracking-[-0.02em] [animation-delay:200ms] [font-stretch:108%]">
        Your crew&apos;s games, kept between you.
      </h1>
      <p className="mt-4 animate-rise text-[17px] leading-relaxed text-muted [animation-delay:300ms]">
        Log a game when you walk off the court. Popshot keeps the streaks, the rivalries and the
        partner you click with.
      </p>
      <div className="min-h-10 grow" />
      <button
        type="button"
        className={buttonClass("primary", "h-14 w-full")}
        onClick={() => void signIn()}
        disabled={busy}
      >
        Continue with Google
        <ArrowIcon />
      </button>
      <p role="status" className="mt-3 min-h-6 text-center text-[15px] text-warn">
        {notice}
      </p>
      <p className="mt-1 flex items-center justify-center gap-2 text-sm text-muted">
        <LockIcon />
        Private by default. Only your crew sees your games.
      </p>
    </main>
  );
}
