"use client";

import { useState } from "react";

import { apiPut, ApiError } from "@/lib/api-client";
import { ANSWERS, type Answer, type Night } from "@/lib/nights";

import { useSignedIn } from "./auth";
import { segmentOption, segmentTrack } from "./ui/segmented";

/** I'm in / Maybe / Can't make it, saved as soon as you tap. */
export function RsvpButtons({ night, onChange }: { night: Night; onChange: (night: Night) => void }) {
  const { user } = useSignedIn();
  const [picked, setPicked] = useState<Answer | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const shown = picked ?? night.my_answer;

  async function answer(next: Answer) {
    setPicked(next);
    setProblem(null);
    try {
      onChange(await apiPut<Night>(user, `/v1/groups/${night.group_id}/nights/${night.id}/rsvp`, { answer: next }));
    } catch (error) {
      setProblem(error instanceof ApiError && error.detail ? error.detail : "We couldn't save that just now.");
    } finally {
      setPicked(null);
    }
  }

  return (
    <fieldset className="flex flex-col gap-1">
      <legend className="sr-only">Are you coming to {night.venue}?</legend>
      <div className={`${segmentTrack} grid-cols-3`}>
        {ANSWERS.map((option) => (
          <label key={option.value} className={`${segmentOption} px-1 text-small`}>
            <input
              type="radio"
              name={`rsvp-${night.id}`}
              checked={shown === option.value}
              onChange={() => void answer(option.value)}
              className="sr-only"
            />
            {option.label}
          </label>
        ))}
      </div>
      <p role="alert" className="text-small text-warn empty:hidden">
        {problem}
      </p>
    </fieldset>
  );
}
