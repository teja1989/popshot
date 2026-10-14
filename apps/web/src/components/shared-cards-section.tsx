"use client";

import { useState } from "react";

import { apiPut, ApiError } from "@/lib/api-client";

import { useAuth, useSignedIn, type Me } from "./auth";

/** Whether your name appears on recaps your crew shares outside the app. */
export function SharedCardsSection() {
  const { user, me } = useSignedIn();
  const { updateMe } = useAuth();
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  if (!me) {
    return null;
  }
  const named = !me.hide_on_shared_cards;

  async function toggle(show: boolean) {
    setBusy(true);
    setNote(null);
    try {
      updateMe(await apiPut<Me>(user, "/v1/me/shared-cards", { hide_on_shared_cards: !show }));
    } catch (error) {
      setNote(error instanceof ApiError && error.detail ? error.detail : "That didn't work just now. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="sharing-heading" className="flex animate-rise flex-col gap-3">
      <h2 id="sharing-heading" className="text-title-sm font-bold text-ink">
        Shared recaps
      </h2>
      <div className="flex flex-col gap-2 rounded-3xl border border-transparent bg-surface shadow-card p-5">
        <label className="grid min-h-12 cursor-pointer grid-cols-[1fr_auto] items-center gap-x-3">
          <span className="font-bold">Show my first name</span>
          <input
            type="checkbox"
            role="switch"
            checked={named}
            disabled={busy}
            onChange={(event) => void toggle(event.target.checked)}
            className="relative row-span-2 h-[26px] w-11 shrink-0 cursor-pointer appearance-none rounded-full bg-line transition-colors duration-200 before:absolute before:top-[3px] before:left-[3px] before:size-5 before:rounded-full before:bg-surface before:shadow-sm before:transition-transform before:duration-200 before:ease-court checked:bg-primary checked:before:translate-x-[18px]"
          />
          <span className="text-meta text-muted">
            When someone in your crew shares a recap link. Off, you show as &ldquo;Crew member&rdquo;. Inside Popshot,
            your crew still sees your name.
          </span>
        </label>
        <p role="status" className="text-body text-muted empty:hidden">
          {note}
        </p>
      </div>
    </section>
  );
}
