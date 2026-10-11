"use client";

import type { GroupDetail } from "@/lib/groups";

import { useSignedIn } from "./auth";
import { GroupScoped } from "./group-scoped";
import { useApiGet } from "./use-api";
import { Avatar } from "./ui/avatar";

export function BoardView() {
  return <GroupScoped title="Leaderboard">{(group) => <Roster key={group.id} groupId={group.id} />}</GroupScoped>;
}

// Until games are confirmed nobody has a rating, so the board lists the crew, unranked.
function Roster({ groupId }: { groupId: string }) {
  const { me } = useSignedIn();
  const { result } = useApiGet<GroupDetail>(`/v1/groups/${groupId}`);
  if (result.kind === "loading") {
    return <p className="text-muted">Loading the crew…</p>;
  }
  if (result.kind === "error") {
    return <p role="alert">We couldn&apos;t load this group just now.</p>;
  }
  const active = result.data.members.filter((m) => m.status === "active");
  return (
    <>
      <p className="text-[16px] leading-relaxed text-muted">
        Everyone starts unranked. Crew ratings come from confirmed games only, and count who you
        played with and against.
      </p>
      <ol aria-label="Players, not yet ranked" className="animate-rise overflow-hidden rounded-2xl border border-line bg-surface">
        {active.map((member) => (
          <li key={member.user_id} className="flex min-h-16 items-center gap-3 border-b border-line px-4 py-3 last:border-b-0">
            <span aria-hidden="true" className="w-6 text-center text-[20px] font-extrabold text-loss [font-stretch:72%]">
              –
            </span>
            <Avatar name={member.display_name} photoUrl={member.avatar_url} />
            <span className="min-w-0 grow truncate text-[17px] font-bold">
              {member.display_name}
              {member.user_id === me?.id && <span className="font-normal text-muted"> (you)</span>}
            </span>
            <span className="text-[14px] text-muted">Unrated</span>
          </li>
        ))}
      </ol>
    </>
  );
}
