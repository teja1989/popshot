"use client";

import { useState } from "react";

import { apiDelete, apiPost, ApiError } from "@/lib/api-client";
import {
  describeExpiry,
  describeJoined,
  describeUses,
  INVITE_DAYS,
  INVITE_USE_CHOICES,
  inviteUrl,
  type Invite,
  type NewInvite,
} from "@/lib/invites";

import { useSignedIn } from "./auth";
import { useApiGet } from "./use-api";
import { buttonClass } from "./ui/button";
import { PlusIcon } from "./ui/icons";
import { segmentOption } from "./ui/segmented";
import { Sheet } from "./ui/sheet";

/** For leads and co-leads: make invite links and see or cancel the open ones. */
export function InvitePanel({ groupId, groupName }: { groupId: string; groupName: string }) {
  const { user } = useSignedIn();
  const { result, reload } = useApiGet<Invite[]>(`/v1/groups/${groupId}/invites`);
  const [problem, setProblem] = useState<string | null>(null);

  async function cancel(invite: Invite) {
    setProblem(null);
    try {
      await apiDelete(user, `/v1/groups/${groupId}/invites/${invite.id}`);
    } catch (error) {
      // Already gone (used up or cancelled elsewhere) is fine: the list refreshes below.
      if (!(error instanceof ApiError && error.status === 404)) {
        setProblem("We couldn't cancel that link just now. Try again in a moment.");
      }
    }
    reload();
  }

  return (
    <section aria-labelledby="invite-heading" className="flex animate-rise flex-col gap-3 [animation-delay:180ms]">
      <h2 id="invite-heading" className="text-title-sm font-bold text-ink">
        Invite links
      </h2>
      <div className="flex flex-col gap-4 rounded-3xl border border-transparent bg-surface shadow-card p-5">
        <p className="text-muted">
          Share a link in your crew&apos;s chat. Everyone who uses it waits for you or a co-lead to let them in. Links
          last {INVITE_DAYS} days.
        </p>
        <InviteSheet groupId={groupId} groupName={groupName} onMade={reload} />

        {result.kind === "ready" && result.data.length > 0 && (
          <ul className="-mb-2 flex flex-col divide-y divide-line border-t border-line" aria-label="Open invite links">
            {result.data.map((invite) => (
              <li key={invite.id} className="flex items-center justify-between gap-3 py-3">
                <div className="min-w-0">
                  <p className="font-bold">{describeUses(invite)}</p>
                  <p className="text-small text-muted">
                    {describeJoined(invite)} · {describeExpiry(invite.expires_at)}
                  </p>
                  {invite.created_by_name && <p className="text-small text-muted">Made by {invite.created_by_name}</p>}
                </div>
                <button
                  type="button"
                  className={buttonClass("quiet", "min-h-11 shrink-0 px-4 text-body")}
                  onClick={() => void cancel(invite)}
                >
                  Cancel link
                </button>
              </li>
            ))}
          </ul>
        )}
        {result.kind === "error" && (
          <p role="alert" className="text-warn">
            We couldn&apos;t load the open links.
          </p>
        )}
        {problem && (
          <p role="alert" className="text-warn">
            {problem}
          </p>
        )}
      </div>
    </section>
  );
}

function InviteSheet({ groupId, groupName, onMade }: { groupId: string; groupName: string; onMade: () => void }) {
  const { user } = useSignedIn();
  const [open, setOpen] = useState(false);
  const [uses, setUses] = useState<number>(1);
  const [made, setMade] = useState<NewInvite | null>(null);
  const [saving, setSaving] = useState(false);
  const [copied, setCopied] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const link = made ? inviteUrl(window.location.origin, made.token) : null;
  const canShare = typeof navigator.share === "function";

  function reset() {
    setUses(1);
    setMade(null);
    setCopied(false);
    setProblem(null);
  }

  async function make() {
    setSaving(true);
    setProblem(null);
    try {
      setMade(await apiPost<NewInvite>(user, `/v1/groups/${groupId}/invites`, { max_uses: uses }));
      onMade();
    } catch (error) {
      setProblem(
        error instanceof ApiError && error.detail
          ? error.detail
          : "We couldn't make a link just now. Try again in a moment.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      setProblem("Your browser didn't let us copy. Select the link and copy it yourself.");
    }
  }

  async function share(text: string) {
    try {
      await navigator.share({ title: `Join ${groupName} on Popshot`, url: text });
    } catch {
      // Closing the share sheet counts as an error; nothing to tell anyone.
    }
  }

  return (
    <Sheet
      trigger={
        <button type="button" className={buttonClass("primary", "self-start")}>
          <PlusIcon />
          Make an invite link
        </button>
      }
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          reset();
        }
        setOpen(next);
      }}
      title={made ? "Your invite link" : "Make an invite link"}
      description={
        made
          ? `Send it to your crew. It works for ${made.max_uses === 1 ? "1 person" : `up to ${String(made.max_uses)} people`} and expires in ${String(INVITE_DAYS)} days.`
          : "You'll approve everyone who uses it."
      }
    >
      {link ? (
        <div className="flex flex-col gap-4">
          <label className="flex flex-col gap-2">
            <span className="text-body font-bold">Link</span>
            <input
              readOnly
              value={link}
              onFocus={(event) => {
                event.target.select();
              }}
              className="min-h-12 rounded-xl border border-line bg-bg px-4 font-mono text-small text-ink"
            />
          </label>
          <p className="text-small text-muted">
            Anyone with this link can ask to join, so share it only with your crew. You won&apos;t see it again after
            closing this; make a new one if you need it.
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            <button type="button" className={buttonClass("action", "h-14")} onClick={() => void copy(link)}>
              {copied ? "Copied" : "Copy link"}
            </button>
            {canShare && (
              <button type="button" className={buttonClass("quiet", "h-14")} onClick={() => void share(link)}>
                Share…
              </button>
            )}
          </div>
          <p role="status" className="min-h-6 text-body text-warn">
            {problem}
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-5">
          <fieldset>
            <legend className="mb-2 text-body font-bold">How many people can use it?</legend>
            <div className="grid grid-cols-3 gap-1 rounded-xl bg-chip p-1">
              {INVITE_USE_CHOICES.map((value) => (
                <label key={value} className={segmentOption}>
                  <input
                    type="radio"
                    name="max_uses"
                    value={value}
                    checked={uses === value}
                    onChange={() => {
                      setUses(value);
                    }}
                    className="sr-only"
                  />
                  {value === 1 ? "1 person" : `Up to ${String(value)}`}
                </label>
              ))}
            </div>
          </fieldset>
          <p role="alert" className="min-h-6 text-body text-warn">
            {problem}
          </p>
          <button
            type="button"
            className={buttonClass("primary", "h-14 w-full")}
            onClick={() => void make()}
            disabled={saving}
          >
            {saving ? "Making…" : "Make link"}
          </button>
        </div>
      )}
    </Sheet>
  );
}
