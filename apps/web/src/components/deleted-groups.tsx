"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { apiPost, ApiError } from "@/lib/api-client";
import { timeLeft, type DeletedGroup, type GroupDetail } from "@/lib/groups";

import { useSignedIn } from "./auth";
import { useApiGet } from "./use-api";
import { buttonClass } from "./ui/button";

/** Groups you lead that were deleted recently, with a way back. Hidden when there are none. */
export function DeletedGroups() {
  const { user } = useSignedIn();
  const router = useRouter();
  const { result, reload } = useApiGet<DeletedGroup[]>("/v1/groups/deleted");
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  if (result.kind !== "ready" || result.data.length === 0) {
    return null;
  }

  async function restore(group: DeletedGroup) {
    setBusy(group.id);
    setProblem(null);
    try {
      const restored = await apiPost<GroupDetail>(user, `/v1/groups/${group.id}/restore`, {});
      router.push(`/groups/${restored.id}`);
    } catch (error) {
      setProblem(error instanceof ApiError && error.detail ? error.detail : "We couldn't restore it just now.");
      setBusy(null);
      reload();
    }
  }

  return (
    <section aria-labelledby="deleted-heading" className="flex animate-rise flex-col gap-2">
      <h2 id="deleted-heading" className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
        Recently deleted
      </h2>
      <ul className="overflow-hidden rounded-2xl border border-dashed border-line">
        {result.data.map((group) => (
          <li key={group.id} className="flex min-h-16 items-center gap-3 border-b border-line px-4 py-3 last:border-b-0">
            <span className="flex min-w-0 grow flex-col">
              <span className="truncate text-[17px] font-bold">{group.name}</span>
              <span className="text-[14px] text-muted">{timeLeft(group.restorable_until)} left to restore</span>
            </span>
            <button
              type="button"
              aria-label={`Restore ${group.name}`}
              className={buttonClass("quiet", "min-h-11 shrink-0 px-4 text-[15px]")}
              disabled={busy === group.id}
              onClick={() => void restore(group)}
            >
              Restore
            </button>
          </li>
        ))}
      </ul>
      <p role="alert" className="text-[15px] text-warn empty:hidden">
        {problem}
      </p>
    </section>
  );
}
