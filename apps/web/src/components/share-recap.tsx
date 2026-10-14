"use client";

import { useState } from "react";

import { apiDelete, apiPost, ApiError } from "@/lib/api-client";
import { shareUrl, type NewShare, type ShareStatus } from "@/lib/shares";

import { useSignedIn } from "./auth";
import { useApiGet } from "./use-api";
import { buttonClass } from "./ui/button";

/**
 * Share this recap as a link anyone can open: the phone's share sheet where there is one,
 * otherwise the link to copy. The link is made on the first tap and reused after that.
 */
export function ShareRecap({ groupId, recapKey, headline }: { groupId: string; recapKey: string; headline: string }) {
  const { user } = useSignedIn();
  const path = `/v1/groups/${groupId}/recaps/${recapKey}/share` as const;
  const status = useApiGet<ShareStatus>(path);
  const [link, setLink] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

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

  async function send(url: string) {
    if (typeof navigator.share === "function") {
      try {
        await navigator.share({ title: headline, text: headline, url });
        return;
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          return; // Closed the share sheet.
        }
        // Some browsers refuse a share that didn't follow a tap straight away (we fetched
        // the link first). The link is on screen now; tapping again shares it.
        if (error instanceof DOMException && error.name === "NotAllowedError") {
          return;
        }
      }
    }
    await copy(url);
  }

  async function copy(url: string) {
    try {
      await navigator.clipboard.writeText(url);
      setNote("Link copied.");
    } catch {
      setNote("Copy the link above to share it.");
    }
  }

  async function share() {
    await run(async () => {
      let url = link;
      if (url === null) {
        const made = await apiPost<NewShare>(user, path, {});
        url = shareUrl(window.location.origin, made.token);
        setLink(url);
        status.reload();
      }
      await send(url);
    });
  }

  async function turnOff() {
    await run(async () => {
      await apiDelete(user, path);
      setLink(null);
      status.reload();
      setNote("Links you can turn off are off now.");
    });
  }

  const canTurnOff = status.result.kind === "ready" && status.result.data.yours_to_turn_off > 0;

  return (
    <section
      aria-labelledby="share-heading"
      className="flex flex-col gap-3 rounded-3xl border border-transparent bg-surface shadow-card p-5"
    >
      <h2 id="share-heading" className="text-lead font-extrabold">
        Share this recap
      </h2>
      <p className="text-body text-muted">
        Anyone with the link can see it for 30 days, no sign-in needed. It shows first names and scores, not where you
        played. Anyone who&apos;d rather not be named shows as &ldquo;Crew member&rdquo;.
      </p>
      {link && (
        <input
          readOnly
          aria-label="Share link"
          value={link}
          onFocus={(event) => {
            event.target.select();
          }}
          className="min-h-12 w-full rounded-xl border border-line bg-bg px-4 text-body text-ink"
        />
      )}
      <div className="flex flex-wrap gap-2">
        <button type="button" className={buttonClass("primary")} disabled={busy} onClick={() => void share()}>
          Share
        </button>
        {link && (
          <button type="button" className={buttonClass("quiet")} disabled={busy} onClick={() => void copy(link)}>
            Copy link
          </button>
        )}
        {canTurnOff && (
          <button type="button" className={buttonClass("quiet")} disabled={busy} onClick={() => void turnOff()}>
            Turn off links
          </button>
        )}
      </div>
      <p role="status" className="text-body text-muted empty:hidden">
        {note}
      </p>
    </section>
  );
}
