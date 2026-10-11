"use client";

import { points } from "@/lib/board";
import { playedWhen, teamNames } from "@/lib/games";
import type { GroupSummary } from "@/lib/groups";
import { record, streakText, type MyStats, type RecordOut } from "@/lib/stats";

import { GroupSwitcher } from "./group-switcher";
import { useApiGet } from "./use-api";
import { useCurrentGroup } from "./use-current-group";

const H2H_SHOWN = 5;

/** Your head-to-head and fun stats, one group at a time. */
export function MyStatsSection() {
  const { result } = useApiGet<GroupSummary[]>("/v1/groups");
  const groups = result.kind === "ready" ? result.data.filter((g) => g.my_status === "active") : [];
  const { current, choose } = useCurrentGroup(groups);
  if (!current) {
    return null;
  }

  return (
    <section aria-labelledby="stats-heading" className="flex animate-rise flex-col gap-3 [animation-delay:45ms]">
      <h2 id="stats-heading" className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
        Your stats
      </h2>
      {groups.length > 1 && <GroupSwitcher groups={groups} current={current} onChange={choose} />}
      <GroupStats key={current.id} group={current} />
    </section>
  );
}

function GroupStats({ group }: { group: GroupSummary }) {
  const { result, reload } = useApiGet<MyStats>(`/v1/groups/${group.id}/stats/me`);
  if (result.kind === "loading") {
    return <p className="text-muted">Loading your stats…</p>;
  }
  if (result.kind === "error") {
    return (
      <p role="alert" className="text-muted">
        We couldn&apos;t load your stats just now.{" "}
        <button type="button" className="font-bold text-primary underline" onClick={reload}>
          Try again
        </button>
      </p>
    );
  }
  const s = result.data;
  if (s.matches === 0) {
    return (
      <p className="rounded-2xl border border-line bg-surface p-5 text-muted">
        Your stats in {group.name} show up after your first game.
      </p>
    );
  }
  const streak = streakText(s.current_streak);
  const opponents = s.head_to_head.slice(0, H2H_SHOWN);

  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-line bg-surface p-5">
      <p className="text-[16px]">
        <span className="font-bold">{group.name}</span>
        <span className="text-muted">
          {" "}
          · {s.matches} games · {record(s.wins, s.matches - s.wins)}
          {streak && ` · ${streak}`}
        </span>
      </p>

      <dl className="grid grid-cols-2 gap-2">
        <Tile label="Close games" value={record(s.close_won, s.close_lost)} hint="won–lost" />
        <Tile label="Skunks" value={record(s.skunks_given, s.skunks_taken)} hint="given–taken" />
        <Tile label="Upset wins" value={String(s.upset_wins)} hint="vs higher-rated teams" />
        <Tile label="Best win streak" value={String(s.longest_win_streak)} hint="wins in a row" />
      </dl>

      <div className="grid gap-2 sm:grid-cols-2">
        <Pairing
          label="Best partner"
          found={s.best_partner}
          describe={(r) => `Won ${String(r.won)} of ${String(r.played)} together`}
          empty={`Shows up once you've played ${String(s.min_pairing)} games with the same partner.`}
        />
        <Pairing
          label="Nemesis"
          found={s.nemesis}
          describe={(r) => `You've won ${String(r.won)} of ${String(r.played)}`}
          empty="Nobody has your number yet."
        />
      </div>

      {s.biggest_upset && (
        <p className="rounded-xl bg-chip px-3 py-2 text-[15px]">
          Your biggest upset: you beat {teamNames(s.biggest_upset.losers.map((p) => p.display_name))} from{" "}
          {points(s.biggest_upset.gap)} points behind ({playedWhen(s.biggest_upset.played_at)}).
        </p>
      )}

      {opponents.length > 0 && (
        <div className="flex flex-col gap-2">
          <h3 className="text-[16px] font-extrabold">Head to head</h3>
          <ul aria-label="Head to head" className="flex flex-col">
            {opponents.map((r) => (
              <li key={r.player.player_id} className="flex items-center justify-between gap-3 border-b border-line py-2 last:border-b-0">
                <span className="min-w-0 truncate font-bold">
                  {r.player.display_name}
                  {r.player.is_guest && <span className="text-[12px] font-semibold text-muted"> · guest</span>}
                </span>
                <span className="text-[15px] text-muted tabular-nums">
                  <span className="font-bold text-ink">{record(r.won, r.played - r.won)}</span> won–lost
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Tile({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-xl bg-bg px-3 py-2">
      <dt className="text-[13px] font-bold text-muted">{label}</dt>
      <dd className="text-[24px] leading-none font-extrabold tabular-nums [font-stretch:75%]">{value}</dd>
      <dd className="text-[12px] text-muted">{hint}</dd>
    </div>
  );
}

function Pairing({
  label,
  found,
  describe,
  empty,
}: {
  label: string;
  found: RecordOut | null;
  describe: (r: RecordOut) => string;
  empty: string;
}) {
  return (
    <div className="flex flex-col gap-0.5 rounded-xl border border-line px-3 py-2">
      <span className="text-[13px] font-bold text-muted">{label}</span>
      {found ? (
        <>
          <span className="truncate text-[17px] font-extrabold">{found.player.display_name}</span>
          <span className="text-[14px] text-muted">{describe(found)}</span>
        </>
      ) : (
        <span className="text-[14px] text-muted">{empty}</span>
      )}
    </div>
  );
}
