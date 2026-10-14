"use client";

import { useState } from "react";

import { apiDelete, apiPost, ApiError } from "@/lib/api-client";
import type { InviteBlock } from "@/lib/direct-invites";

import { useSignedIn } from "./auth";
import { useApiGet } from "./use-api";
import { buttonClass } from "./ui/button";

/** Your Popshot code, for a lead to invite you, and the crews you've stopped inviting you. */
export function InviteCodeSection() {
  const { user } = useSignedIn();
  const code = useApiGet<{ code: string }>("/v1/me/invite-code");
  const blocks = useApiGet<InviteBlock[]>("/v1/me/invite-blocks");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const canShare = typeof navigator.share === "function";

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setNote(null);
    try {
      await action();
    } catch (error) {
      setNote(error instanceof ApiError && error.detail ? error.detail : "That didn't work just now. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function copy(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setNote("Copied.");
    } catch {
      setNote("Select the code and copy it yourself.");
    }
  }

  async function share(value: string) {
    try {
      await navigator.share({ text: `My Popshot code is ${value}. Use it to invite me to your crew.` });
    } catch {
      // Closing the share sheet counts as an error; nothing to tell anyone.
    }
  }

  async function changeCode() {
    await run(async () => {
      code.replace(await apiPost<{ code: string }>(user, "/v1/me/invite-code", {}));
      setNote("New code made. The old one doesn't work any more.");
    });
  }

  async function allow(block: InviteBlock) {
    await run(async () => {
      await apiDelete(user, `/v1/me/invite-blocks/${block.group_id}`);
      blocks.reload();
      setNote(`${block.group_name} can invite you again.`);
    });
  }

  return (
    <section aria-labelledby="code-heading" className="flex animate-rise flex-col gap-3">
      <h2 id="code-heading" className="text-title-sm font-bold text-ink">
        Your Popshot code
      </h2>
      <div className="flex flex-col gap-3 rounded-3xl border border-transparent bg-surface shadow-card p-5">
        <p className="text-body text-muted">
          Give it to a crew&apos;s lead so they can invite you. You choose whether to join. Nobody can find you without
          it, unless you&apos;ve been in a crew together.
        </p>
        {code.result.kind === "ready" && (
          <>
            <p className="font-mono text-display-sm font-bold tracking-[0.12em]" aria-label="Your code">
              {code.result.data.code}
            </p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className={buttonClass("action")}
                onClick={() => {
                  if (code.result.kind === "ready") {
                    void copy(code.result.data.code);
                  }
                }}
              >
                Copy
              </button>
              {canShare && (
                <button
                  type="button"
                  className={buttonClass("quiet")}
                  onClick={() => {
                    if (code.result.kind === "ready") {
                      void share(code.result.data.code);
                    }
                  }}
                >
                  Share…
                </button>
              )}
              <button type="button" className={buttonClass("quiet")} disabled={busy} onClick={() => void changeCode()}>
                Get a new code
              </button>
            </div>
          </>
        )}
        {code.result.kind === "error" && <p className="text-body text-warn">We couldn&apos;t load your code.</p>}

        {blocks.result.kind === "ready" && blocks.result.data.length > 0 && (
          <div className="flex flex-col gap-2 border-t border-line pt-4">
            <h3 className="text-lead font-extrabold">Crews that can&apos;t invite you</h3>
            <ul className="flex flex-col divide-y divide-line">
              {blocks.result.data.map((block) => (
                <li key={block.group_id} className="flex min-h-12 items-center justify-between gap-3 py-2">
                  <span className="min-w-0 truncate font-bold">{block.group_name}</span>
                  <button
                    type="button"
                    className={buttonClass("quiet", "min-h-11 shrink-0 px-4 text-body")}
                    disabled={busy}
                    onClick={() => void allow(block)}
                  >
                    Allow invites
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        <p role="status" className="text-body text-muted empty:hidden">
          {note}
        </p>
      </div>
    </section>
  );
}
