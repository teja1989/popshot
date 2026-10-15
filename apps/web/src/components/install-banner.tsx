"use client";

import { useState, useSyncExternalStore } from "react";

import { canPromptInstall, dismissInstall, installDismissed, promptInstall, subscribeInstall } from "@/lib/install";
import { isIos, isStandalone } from "@/lib/push";

import { buttonClass } from "./ui/button";
import { Sheet } from "./ui/sheet";

/** "Put Popshot on your home screen", for people in a group who haven't installed it yet. */
export function InstallBanner() {
  const promptable = useSyncExternalStore(subscribeInstall, canPromptInstall, () => false);
  // Read once on mount (the app shell renders in the browser only).
  const [hidden, setHidden] = useState(() => isStandalone() || installDismissed());
  const [howOpen, setHowOpen] = useState(false);
  const ios = isIos();
  if (hidden || (!promptable && !ios)) {
    return null;
  }

  function notNow() {
    dismissInstall();
    setHidden(true);
  }

  return (
    <section
      aria-labelledby="install-heading"
      className="flex animate-rise flex-col gap-3 rounded-3xl border border-transparent bg-surface shadow-card p-4 sm:flex-row sm:items-center"
    >
      <div className="flex grow flex-col gap-0.5">
        <h2 id="install-heading" className="text-lead font-extrabold">
          Put Popshot on your home screen
        </h2>
        <p className="text-body text-muted">It opens like an app, and can remind you before games.</p>
      </div>
      <div className="flex shrink-0 gap-2">
        {promptable ? (
          <button
            type="button"
            className={buttonClass("primary", "min-h-11 px-4 text-body")}
            onClick={() => {
              void promptInstall().then((installed) => {
                if (installed) {
                  setHidden(true);
                }
              });
            }}
          >
            Install
          </button>
        ) : (
          <Sheet
            trigger={
              <button type="button" className={buttonClass("primary", "min-h-11 px-4 text-body")}>
                Show me how
              </button>
            }
            open={howOpen}
            onOpenChange={setHowOpen}
            title="Add Popshot to your home screen"
            description="In Safari:"
          >
            <ol className="flex list-decimal flex-col gap-2 pl-5 text-lead">
              <li>Tap the Share button (the square with an arrow).</li>
              <li>
                Scroll down and tap <strong>Add to Home Screen</strong>.
              </li>
              <li>Open Popshot from your home screen, then turn on notifications in You → Settings.</li>
            </ol>
          </Sheet>
        )}
        <button type="button" className={buttonClass("quiet", "min-h-11 px-4 text-body")} onClick={notNow}>
          Not now
        </button>
      </div>
    </section>
  );
}
