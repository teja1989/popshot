"use client";

import { useState } from "react";

import { apiPost, ApiError } from "@/lib/api-client";
import { reauthenticate } from "@/lib/firebase-client";

import { useSignedIn } from "./auth";
import { buttonClass } from "./ui/button";
import { Sheet } from "./ui/sheet";

const REASON_MIN = 10;
const REASON_MAX = 500;
const STALE = "Sign in again to make changes.";

/**
 * Support makes an active member the crew's lead; whoever was lead becomes a co-lead. Needs
 * a reason (kept with the change) and the crew's name typed out, and a sign-in from the last
 * 15 minutes: when it's older, the sheet asks for one and then tries again.
 */
export function MakeLeadSheet({
  crewId,
  crewName,
  person,
  currentLead,
  onDone,
}: {
  crewId: string;
  crewName: string;
  person: { id: string; name: string };
  currentLead: string | null;
  onDone: () => void;
}) {
  const { user } = useSignedIn();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [stale, setStale] = useState(false);

  const trimmed = reason.trim();
  const ready =
    trimmed.length >= REASON_MIN &&
    trimmed.length <= REASON_MAX &&
    typed.trim().toLowerCase() === crewName.trim().toLowerCase();

  async function submit() {
    setBusy(true);
    setProblem(null);
    try {
      await apiPost(user, `/v1/admin/groups/${crewId}/lead`, { user_id: person.id, reason: trimmed });
      setOpen(false);
      setReason("");
      setTyped("");
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
      title={`Make ${person.name} the lead`}
      description={`${person.name} becomes the lead of ${crewName}${
        currentLead ? `, and ${currentLead} becomes a co-lead` : ""
      }. Your reason is kept with the change.`}
      trigger={
        <button type="button" className={buttonClass("quiet", "min-h-10 shrink-0 px-3 text-[15px] whitespace-nowrap")}>
          Make lead
        </button>
      }
    >
      <form
        className="mt-5 flex flex-col gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          if (ready && !busy) {
            void submit();
          }
        }}
      >
        <label className="flex flex-col gap-1.5">
          <span className="font-bold">Why</span>
          <textarea
            value={reason}
            onChange={(event) => {
              setReason(event.target.value);
            }}
            rows={3}
            maxLength={REASON_MAX}
            placeholder="Who asked, and what happened"
            className="rounded-xl border border-line bg-bg px-4 py-3 text-[17px]"
          />
          <span className="text-[13px] text-muted">
            At least {REASON_MIN} characters · {trimmed.length}/{REASON_MAX}
          </span>
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="font-bold">Type the crew&apos;s name to confirm</span>
          <input
            value={typed}
            onChange={(event) => {
              setTyped(event.target.value);
            }}
            autoComplete="off"
            placeholder={crewName}
            className="min-h-12 rounded-xl border border-line bg-bg px-4 text-[17px]"
          />
        </label>
        {stale ? (
          <div className="flex flex-col gap-2 rounded-xl bg-chip p-4">
            <p className="text-[15px]">Changes need a sign-in from the last 15 minutes.</p>
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
          <button type="submit" disabled={!ready || busy} className={buttonClass("primary", "self-start")}>
            {busy ? "Saving…" : `Make ${person.name} the lead`}
          </button>
        )}
        <p role="alert" className="text-[15px] text-warn empty:hidden">
          {problem}
        </p>
      </form>
    </Sheet>
  );
}
