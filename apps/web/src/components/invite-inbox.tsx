"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { apiPost, ApiError } from "@/lib/api-client";
import { inviteLine, type InviteAnswer, type MyInvite } from "@/lib/direct-invites";
import { describeExpiry } from "@/lib/invites";

import { useSignedIn } from "./auth";
import { CrewProfileSummary } from "./crew-profile-summary";
import { useHomeRefresh } from "./home-refresh";
import { useApiGet } from "./use-api";
import { buttonClass } from "./ui/button";

/** Invites to crews, waiting for your answer. Nothing when there are none. */
export function InviteInbox({ onJoined }: { onJoined: () => void }) {
  const { user } = useSignedIn();
  const router = useRouter();
  const { result, reload } = useApiGet<MyInvite[]>("/v1/me/invites");
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  useHomeRefresh(reload);

  if (result.kind !== "ready" || result.data.length === 0) {
    return note ? (
      <p role="status" className="text-[15px] text-muted">
        {note}
      </p>
    ) : null;
  }

  async function answer(invite: MyInvite, what: InviteAnswer) {
    setBusy(invite.id);
    setNote(null);
    try {
      await apiPost(user, `/v1/me/invites/${invite.id}`, { answer: what });
      if (what === "accept") {
        onJoined();
        router.push(`/groups/${invite.group_id}`);
        return;
      }
      setNote(
        what === "block"
          ? `Declined. ${invite.group_name} can't invite you again unless you allow it on your You page.`
          : "Declined. Nobody is told.",
      );
    } catch (error) {
      setNote(
        error instanceof ApiError && error.status === 404
          ? "That invite isn't open any more."
          : "That didn't work just now. Try again.",
      );
    } finally {
      setBusy(null);
      reload();
    }
  }

  return (
    <section aria-labelledby="invites-heading" className="flex animate-rise flex-col gap-3">
      <h2 id="invites-heading" className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
        Invites for you
      </h2>
      <ul className="flex flex-col gap-3">
        {result.data.map((invite) => (
          <li key={invite.id} className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-5">
            <div>
              <p className="text-[19px] font-extrabold">{invite.group_name}</p>
              <p className="text-[15px] text-muted">
                {inviteLine(invite)} · {describeExpiry(invite.expires_at)}
              </p>
            </div>
            <CrewProfileSummary profile={invite} />
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className={buttonClass("primary")}
                disabled={busy !== null}
                onClick={() => void answer(invite, "accept")}
              >
                Join {invite.group_name}
              </button>
              <button
                type="button"
                className={buttonClass("quiet")}
                disabled={busy !== null}
                onClick={() => void answer(invite, "decline")}
              >
                No thanks
              </button>
            </div>
            <button
              type="button"
              className="self-start text-[14px] font-bold text-muted underline underline-offset-2"
              disabled={busy !== null}
              onClick={() => void answer(invite, "block")}
            >
              No thanks, and don&apos;t invite me again
            </button>
          </li>
        ))}
      </ul>
      <p role="status" className="text-[15px] text-muted empty:hidden">
        {note}
      </p>
    </section>
  );
}
