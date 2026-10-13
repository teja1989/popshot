"use client";

import { useState, type ReactNode } from "react";

import { ApiError } from "@/lib/api-client";
import { reauthenticate } from "@/lib/firebase-client";

import { useSignedIn } from "./auth";
import { buttonClass } from "./ui/button";
import { Sheet } from "./ui/sheet";

const REASON_MIN = 10;
const REASON_MAX = 500;
const STALE = "Sign in again to make changes.";

/**
 * An admin change that needs a reason (kept with the change) and a sign-in from the last
 * 15 minutes: when it's older, the sheet asks for one and then tries again. `fields` are
 * any choices the change needs; `ready` says whether they're filled in.
 */
export function ChangeSheet({
  trigger,
  title,
  description,
  confirm,
  fields,
  ready = true,
  save,
  onDone,
}: {
  trigger: ReactNode;
  title: string;
  description: string;
  confirm: string;
  fields?: ReactNode;
  ready?: boolean;
  save: (reason: string) => Promise<void>;
  onDone: () => void;
}) {
  const { user } = useSignedIn();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [stale, setStale] = useState(false);

  const trimmed = reason.trim();
  const canSave = ready && trimmed.length >= REASON_MIN && trimmed.length <= REASON_MAX;

  async function submit() {
    setBusy(true);
    setProblem(null);
    try {
      await save(trimmed);
      setOpen(false);
      setReason("");
      onDone();
    } catch (error) {
      if (error instanceof ApiError && error.status === 403 && error.detail === STALE) {
        setStale(true);
      } else {
        setProblem(error instanceof ApiError && error.detail ? error.detail : "That didn't go through just now.");
      }
    } finally {
      setBusy(false);
    }
  }

  async function signInAndRetry() {
    setBusy(true);
    setProblem(null);
    try {
      await reauthenticate(user);
      setStale(false);
    } catch {
      setProblem("Sign-in didn't finish. Use the same Google account you're signed in with.");
      setBusy(false);
      return;
    }
    await submit();
  }

  return (
    <Sheet
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) {
          setProblem(null);
          setStale(false);
        }
      }}
      fullOnPhone
      title={title}
      description={description}
      trigger={trigger}
    >
      <form
        className="mt-5 flex flex-col gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          if (canSave && !busy) {
            void submit();
          }
        }}
      >
        {fields}
        <label className="flex flex-col gap-1.5">
          <span className="font-bold">Why</span>
          <textarea
            value={reason}
            onChange={(event) => {
              setReason(event.target.value);
            }}
            rows={3}
            maxLength={REASON_MAX}
            placeholder="Who asked, and what it's for"
            className="rounded-xl border border-line bg-bg px-4 py-3 text-field"
          />
          <span className="text-meta text-muted">
            At least {REASON_MIN} characters · {trimmed.length}/{REASON_MAX}
          </span>
        </label>
        {stale ? (
          <div className="flex flex-col gap-2 rounded-xl bg-chip p-4">
            <p className="text-body">Changes need a sign-in from the last 15 minutes.</p>
            <button
              type="button"
              disabled={busy}
              className={buttonClass("primary", "self-start")}
              onClick={() => void signInAndRetry()}
            >
              Sign in with Google
            </button>
          </div>
        ) : (
          <button type="submit" disabled={!canSave || busy} className={buttonClass("primary", "self-start")}>
            {busy ? "Saving…" : confirm}
          </button>
        )}
        <p role="alert" className="text-body text-warn empty:hidden">
          {problem}
        </p>
      </form>
    </Sheet>
  );
}
