"use client";

import { useEffect, useState } from "react";

import { apiPost, apiPut, ApiError } from "@/lib/api-client";
import {
  CATEGORY_LABEL,
  knownCategories,
  currentSubscription,
  pushSupport,
  turnOff,
  turnOn,
  type Category,
  type NotificationSettings,
  type PushConfig,
} from "@/lib/push";

import { useSignedIn } from "./auth";
import { useApiGet } from "./use-api";
import { buttonClass } from "./ui/button";

type DeviceState = "checking" | "on" | "off" | "blocked";

/** Turning notifications on for this device, and choosing what you hear about. */
export function NotificationsSection() {
  const { result: config } = useApiGet<PushConfig>("/v1/push/config");
  if (config.kind !== "ready" || !config.data.public_key) {
    // Push isn't set up on this server.
    return null;
  }
  return <Notifications publicKey={config.data.public_key} />;
}

function Notifications({ publicKey }: { publicKey: string }) {
  const { user } = useSignedIn();
  const settings = useApiGet<NotificationSettings>("/v1/me/notifications");
  const [support] = useState(pushSupport);
  const [device, setDevice] = useState<DeviceState>(() =>
    support.kind === "ready" && Notification.permission === "denied" ? "blocked" : "checking",
  );
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (support.kind !== "ready" || Notification.permission === "denied") {
      return;
    }
    void currentSubscription().then((sub) => {
      setDevice(sub && Notification.permission === "granted" ? "on" : "off");
    });
  }, [support.kind]);

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

  async function enable() {
    await run(async () => {
      const outcome = await turnOn(user, publicKey);
      setDevice(outcome === "on" ? "on" : "blocked");
      settings.reload();
    });
  }

  async function disable() {
    await run(async () => {
      await turnOff(user);
      setDevice("off");
      settings.reload();
    });
  }

  async function test() {
    await run(async () => {
      await apiPost(user, "/v1/me/push-test", {});
      setNote("Sent. It should arrive in a few seconds.");
    });
  }

  async function toggle(category: Category, on: boolean) {
    if (settings.result.kind !== "ready") {
      return;
    }
    const muted = settings.result.data.muted.filter((c) => c !== category);
    await run(async () => {
      settings.replace(
        await apiPut<NotificationSettings>(user, "/v1/me/notifications", { muted: on ? muted : [...muted, category] }),
      );
    });
  }

  return (
    <section aria-labelledby="notify-heading" className="flex animate-rise flex-col gap-3">
      <h2 id="notify-heading" className="text-title-sm font-bold text-ink">
        Notifications
      </h2>
      <div className="flex flex-col gap-4 rounded-3xl border border-transparent bg-surface shadow-card p-5">
        {support.kind === "install-first" && (
          <p className="text-body text-muted">
            On iPhone, notifications work once Popshot is on your home screen: tap Share, then{" "}
            <strong>Add to Home Screen</strong>, and open it from there.
          </p>
        )}
        {support.kind === "unsupported" && (
          <p className="text-body text-muted">This browser can&apos;t show notifications.</p>
        )}
        {support.kind === "ready" && device === "blocked" && (
          <p className="text-body text-muted">
            Notifications are blocked for Popshot. Allow them in your browser or phone settings, then come back here.
          </p>
        )}
        {support.kind === "ready" && device === "off" && (
          <div className="flex flex-col items-start gap-2">
            <p className="text-body text-muted">Hear when games are logged, and get reminders before you play.</p>
            <button type="button" className={buttonClass("primary")} disabled={busy} onClick={() => void enable()}>
              Turn on notifications
            </button>
          </div>
        )}
        {support.kind === "ready" && device === "on" && (
          <div className="flex flex-wrap items-center gap-2">
            <p className="grow text-body font-bold">On for this device</p>
            <button
              type="button"
              className={buttonClass("quiet", "min-h-11 px-4 text-body")}
              disabled={busy}
              onClick={() => void test()}
            >
              Send a test
            </button>
            <button
              type="button"
              className={buttonClass("quiet", "min-h-11 px-4 text-body")}
              disabled={busy}
              onClick={() => void disable()}
            >
              Turn off
            </button>
          </div>
        )}

        {settings.result.kind === "ready" && settings.result.data.devices > 0 && (
          <fieldset className="flex flex-col gap-2 border-t border-line pt-4">
            <legend className="mb-1 text-lead font-extrabold">What you hear about</legend>
            {knownCategories(settings.result.data.categories).map((category) => {
              const on = settings.result.kind === "ready" && !settings.result.data.muted.includes(category);
              return (
                <label
                  key={category}
                  className="grid min-h-12 cursor-pointer grid-cols-[1fr_auto] items-center gap-x-3"
                >
                  <span className="font-bold">{CATEGORY_LABEL[category].title}</span>
                  <input
                    type="checkbox"
                    role="switch"
                    checked={on}
                    disabled={busy}
                    onChange={(event) => void toggle(category, event.target.checked)}
                    className="relative row-span-2 h-[26px] w-11 shrink-0 cursor-pointer appearance-none rounded-full bg-line transition-colors duration-200 before:absolute before:top-[3px] before:left-[3px] before:size-5 before:rounded-full before:bg-surface before:shadow-sm before:transition-transform before:duration-200 before:ease-court checked:bg-primary checked:before:translate-x-[18px]"
                  />
                  <span className="text-meta text-muted">{CATEGORY_LABEL[category].body}</span>
                </label>
              );
            })}
          </fieldset>
        )}
        <p role="status" className="text-body text-muted empty:hidden">
          {note}
        </p>
      </div>
    </section>
  );
}
