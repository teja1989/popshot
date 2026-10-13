"use client";

import { useState } from "react";

import { apiGet, apiPost, ApiError } from "@/lib/api-client";

import { useAuth, useSignedIn, type Me } from "./auth";
import { buttonClass } from "./ui/button";
import { Sheet } from "./ui/sheet";

export function deletionDate(iso: string, locale?: string): string {
  return new Date(iso).toLocaleDateString(locale, { weekday: "long", month: "long", day: "numeric" });
}

/** Download a copy of your data, or delete your account (with 7 days to change your mind). */
export function YourDataSection() {
  const { user, me } = useSignedIn();
  const { updateMe } = useAuth();
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  async function download() {
    setBusy(true);
    setNote(null);
    try {
      const data = await apiGet<unknown>(user, "/v1/me/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `popshot-data-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      URL.revokeObjectURL(url);
      setNote("Downloaded.");
    } catch {
      setNote("We couldn't get your data just now. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function keep() {
    setBusy(true);
    setNote(null);
    try {
      updateMe(await apiPost<Me>(user, "/v1/me/delete/cancel", {}));
      setNote("Your account stays. Glad you're here.");
    } catch {
      setNote("That didn't work just now. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="data-heading" className="flex animate-rise flex-col gap-3">
      <h2 id="data-heading" className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
        Your data
      </h2>
      <div className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-5">
        <p className="text-[15px] text-muted">
          A copy of everything Popshot keeps about you: your profile, crews, games, meetup answers, focus and notes.
        </p>
        <button
          type="button"
          className={buttonClass("quiet", "self-start")}
          disabled={busy}
          onClick={() => void download()}
        >
          Download my data
        </button>
        <div className="border-t border-line pt-4">
          {me?.delete_on ? (
            <div className="flex flex-col items-start gap-2">
              <p className="font-bold">Your account will be deleted on {deletionDate(me.delete_on)}.</p>
              <button type="button" className={buttonClass("primary")} disabled={busy} onClick={() => void keep()}>
                Keep my account
              </button>
            </div>
          ) : (
            <DeleteAccountSheet onRequested={updateMe} />
          )}
        </div>
        <p role="status" className="text-[15px] text-muted empty:hidden">
          {note}
        </p>
      </div>
    </section>
  );
}

function DeleteAccountSheet({ onRequested }: { onRequested: (me: Me) => void }) {
  const { user } = useSignedIn();
  const [open, setOpen] = useState(false);
  const [sure, setSure] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function request() {
    setBusy(true);
    setProblem(null);
    try {
      onRequested(await apiPost<Me>(user, "/v1/me/delete", {}));
      setOpen(false);
    } catch (error) {
      setProblem(error instanceof ApiError && error.detail ? error.detail : "That didn't work just now. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet
      trigger={
        <button type="button" className={buttonClass("danger", "self-start")}>
          Delete my account
        </button>
      }
      open={open}
      onOpenChange={(next) => {
        setSure(false);
        setProblem(null);
        setOpen(next);
      }}
      title="Delete your account?"
      description="You'll have 7 days to change your mind."
    >
      <div className="flex flex-col gap-4">
        <ul className="flex list-disc flex-col gap-1 pl-5 text-[15px]">
          <li>After 7 days, your sign-in, name, photo, notes, settings and devices are deleted for good.</li>
          <li>
            In your crews&apos; past games you&apos;ll show as &ldquo;Former player&rdquo;. The scores stay, so their
            history still adds up.
          </li>
          <li>A crew where you&apos;re the only member is deleted too.</li>
          <li>Want a copy first? Use Download my data.</li>
        </ul>
        <label className="flex min-h-11 cursor-pointer items-center gap-3">
          <input
            type="checkbox"
            checked={sure}
            onChange={(event) => {
              setSure(event.target.checked);
            }}
            className="size-5"
          />
          <span className="font-bold">I understand</span>
        </label>
        <button
          type="button"
          className={buttonClass("danger", "h-14 w-full")}
          disabled={!sure || busy}
          onClick={() => void request()}
        >
          Delete my account in 7 days
        </button>
        <p role="alert" className="min-h-6 text-[15px] text-warn">
          {problem}
        </p>
      </div>
    </Sheet>
  );
}

/** On Home while the account waits to be deleted: when, and the way back. */
export function DeletionNotice() {
  const { me } = useSignedIn();
  if (!me?.delete_on) {
    return null;
  }
  return (
    <p role="status" className="rounded-2xl border border-warn bg-surface p-4 text-[15px]">
      Your account will be deleted on <strong>{deletionDate(me.delete_on)}</strong>. Changed your mind?{" "}
      <a href="/you" className="font-bold text-primary">
        Keep my account
      </a>
    </p>
  );
}
