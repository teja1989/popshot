"use client";

import Link from "next/link";

import { shortDate } from "@/lib/admin";
import { LEVEL_LABEL, shotState, STATE_LABEL, type AdminShot, type ShotRow, type ShotState } from "@/lib/admin-learn";

import { AdminGate, AdminMain, Section } from "./admin-ui";
import { ShotPlayer } from "./shot-player";
import { useApiGet } from "./use-api";

interface FocusOption {
  id: string;
  label: string;
}

const STATE_CHIP: Record<ShotState, string> = {
  draft: "bg-chip text-muted",
  published: "bg-win text-on-win",
  changed: "bg-ball text-on-ball",
};

function StateChip({ state }: { state: ShotState }) {
  return (
    <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-meta font-bold ${STATE_CHIP[state]}`}>
      {STATE_LABEL[state]}
    </span>
  );
}

/** Every Learn shot, drafts included. Admin only: the API answers 404 to anyone else. */
export function AdminLearnView() {
  const shots = useApiGet<ShotRow[]>("/v1/admin/learn/shots");
  const status = shots.result.kind === "error" ? shots.result.status : null;
  return (
    <AdminGate status={status} onSignedIn={shots.reload}>
      <AdminMain>
        <header className="flex animate-rise flex-col gap-1">
          <Link href="/admin" className="self-start text-small font-bold text-primary">
            ← Admin
          </Link>
          <h1 className="text-title-lg leading-tight font-extrabold">Learn</h1>
          <p className="text-body text-muted">
            Shots for the Learn pages. Open one to preview it in 3D. Only published shots are public, and only while the
            Public Learn pages switch is on for everyone.
          </p>
        </header>
        {shots.result.kind === "loading" && <p className="text-muted">Loading shots…</p>}
        {shots.result.kind === "error" && status !== 404 && status !== 403 && (
          <p role="alert" className="text-warn">
            We couldn&apos;t load the shots just now.
          </p>
        )}
        {shots.result.kind === "ready" &&
          (shots.result.data.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-line p-4 text-body text-muted">No shots yet.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {shots.result.data.map((shot) => (
                <li key={shot.id}>
                  <Link
                    href={`/admin/learn/${shot.id}`}
                    className="flex items-center justify-between gap-3 rounded-2xl border border-line bg-surface p-4 text-ink no-underline transition-colors duration-150 hover:border-primary"
                  >
                    <span className="flex min-w-0 flex-col gap-0.5">
                      <span className="truncate text-title-sm font-extrabold font-display">{shot.title}</span>
                      <span className="truncate text-small text-muted">
                        /{shot.slug} · {LEVEL_LABEL[shot.level]} · saved {shortDate(shot.updated_at)}
                        {shot.updated_by ? ` by ${shot.updated_by}` : ""}
                      </span>
                    </span>
                    <StateChip state={shotState(shot)} />
                  </Link>
                </li>
              ))}
            </ul>
          ))}
      </AdminMain>
    </AdminGate>
  );
}

/** One shot as saved now (not necessarily as published), with what stops it being published. */
export function AdminShotView({ shotId }: { shotId: string }) {
  const shot = useApiGet<AdminShot>(`/v1/admin/learn/shots/${shotId}`);
  const focus = useApiGet<FocusOption[]>("/v1/focus-options");
  const status = shot.result.kind === "error" ? shot.result.status : null;
  const labels = new Map(focus.result.kind === "ready" ? focus.result.data.map((o) => [o.id, o.label]) : []);

  return (
    <AdminGate status={status} onSignedIn={shot.reload}>
      <AdminMain>
        <Link href="/admin/learn" className="self-start text-small font-bold text-primary">
          ← Learn
        </Link>
        {shot.result.kind === "loading" && <p className="text-muted">Loading the shot…</p>}
        {shot.result.kind === "error" && status !== 404 && status !== 403 && (
          <p role="alert" className="text-warn">
            We couldn&apos;t load this shot just now.
          </p>
        )}
        {shot.result.kind === "ready" && (
          <>
            <header className="flex animate-rise flex-col gap-2">
              <div className="flex items-start justify-between gap-3">
                <h1 className="text-title-lg leading-tight font-extrabold">{shot.result.data.title}</h1>
                <StateChip state={shotState(shot.result.data)} />
              </div>
              <p className="text-body text-muted">{shot.result.data.summary}</p>
              <p className="text-small text-muted">
                /learn/{shot.result.data.slug} · {LEVEL_LABEL[shot.result.data.level]} · version{" "}
                {shot.result.data.version}
                {shot.result.data.published_version !== null &&
                  ` (published: version ${String(shot.result.data.published_version)})`}
              </p>
              <p className="text-small text-muted">
                {shot.result.data.focus_ids.map((id) => labels.get(id) ?? id).join(" · ")}
              </p>
            </header>
            {shot.result.data.problems.length > 0 && (
              <div role="status" className="flex flex-col gap-1 rounded-2xl border border-warn p-4">
                <p className="text-body font-bold">Fix these before publishing:</p>
                <ul className="list-disc pl-5 text-body">
                  {shot.result.data.problems.map((p) => (
                    <li key={`${p.code}-${String(p.flight)}-${String(p.actor)}`}>{p.message}</li>
                  ))}
                </ul>
              </div>
            )}
            {shot.result.data.scene ? (
              <ShotPlayer scene={shot.result.data.scene} title={shot.result.data.title} />
            ) : (
              <p className="text-body text-warn">
                This shot&apos;s scene was saved under older rules and can&apos;t be shown. Save it again to fix it.
              </p>
            )}
            <Section title="Tips">
              {shot.result.data.tips.length === 0 ? (
                <p className="text-body text-muted">No tips yet.</p>
              ) : (
                <ul className="list-disc pl-5 text-body">
                  {shot.result.data.tips.map((tip, i) => (
                    <li key={`tip-${String(i)}`}>{tip}</li>
                  ))}
                </ul>
              )}
            </Section>
            <Section title="Drill">
              {shot.result.data.drill_steps.length === 0 ? (
                <p className="text-body text-muted">No drill yet.</p>
              ) : (
                <ol className="list-decimal pl-5 text-body">
                  {shot.result.data.drill_steps.map((step, i) => (
                    <li key={`step-${String(i)}`}>{step}</li>
                  ))}
                </ol>
              )}
            </Section>
          </>
        )}
      </AdminMain>
    </AdminGate>
  );
}
