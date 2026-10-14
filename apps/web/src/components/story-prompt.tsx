"use client";

import { useState } from "react";

import { apiPut } from "@/lib/api-client";
import { COPY, FEATURE, shouldAskForStory, type Journey } from "@/lib/journey";

import { useSignedIn } from "./auth";
import { useYouFeature } from "./features";
import { StorySheet } from "./story-sheet";
import { useApiGet } from "./use-api";
import { buttonClass } from "./ui/button";

/** On Home: "What's your pickleball story?", until you write it or say not now. */
export function StoryPrompt() {
  const on = useYouFeature(FEATURE);
  return on ? <Prompt /> : null;
}

function Prompt() {
  const { user } = useSignedIn();
  const journey = useApiGet<Journey>("/v1/me/journey");
  const [open, setOpen] = useState(false);
  const [hidden, setHidden] = useState(false);
  const data = journey.result.kind === "ready" ? journey.result.data : null;
  if (hidden || !shouldAskForStory(data)) {
    return null;
  }

  function notNow() {
    setHidden(true);
    // Remembered on the server, so no device asks again. If it fails, it's only asked again.
    void apiPut(user, "/v1/me/journey/settings", { onboarding: "skipped" }).catch(() => undefined);
  }

  return (
    <section
      aria-labelledby="story-prompt-heading"
      className="flex animate-rise flex-col gap-3 rounded-3xl border border-transparent bg-secondary-container p-5 text-on-secondary-container"
    >
      <h2 id="story-prompt-heading" className="text-title-sm font-extrabold">
        {COPY.promptTitle}
      </h2>
      <p className="text-body">{COPY.promptBody}</p>
      <div className="flex flex-wrap gap-2">
        <StorySheet
          story={null}
          open={open}
          onOpenChange={setOpen}
          onSaved={journey.replace}
          trigger={
            <button type="button" className={buttonClass("primary", "min-h-11 px-5 text-body")}>
              {COPY.promptStart}
            </button>
          }
        />
        <button type="button" className={buttonClass("quiet", "min-h-11 bg-surface px-5 text-body")} onClick={notNow}>
          {COPY.promptLater}
        </button>
      </div>
    </section>
  );
}
