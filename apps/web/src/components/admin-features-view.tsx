"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { shortDate, type AdminGroup } from "@/lib/admin";
import {
  AREA_LABEL,
  areasOf,
  filterFeatures,
  planState,
  reachText,
  ROLLOUT_LABEL,
  ROLLOUTS,
  SOURCE_LABEL,
  type CrewAccess,
  type Feature,
  type FeatureCrew,
  type PlanRow,
  type PlanSource,
  type Rollout,
} from "@/lib/admin-features";
import { apiPost, apiPut } from "@/lib/api-client";

import { ChangeSheet } from "./admin-change-sheet";
import { AdminGate, AdminMain, Section } from "./admin-ui";
import { useSignedIn } from "./auth";
import { buttonClass } from "./ui/button";
import { segmentOption, segmentTrack } from "./ui/segmented";
import { useApiGet } from "./use-api";

type Tab = "switches" | "plans";

const SMALL_BUTTON = "min-h-10 shrink-0 px-3 text-body whitespace-nowrap";

/**
 * Feature switches and crew plans. Changes apply on the next request, need a reason, and are
 * kept in the admin log. Admin only: the API answers 404 to anyone else.
 */
export function AdminFeaturesView() {
  const features = useApiGet<Feature[]>("/v1/admin/features");
  const status = features.result.kind === "error" ? features.result.status : null;
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const tab: Tab = params.get("tab") === "plans" ? "plans" : "switches";

  function setParam(name: string, value: string | null) {
    const next = new URLSearchParams(params.toString());
    if (value === null) {
      next.delete(name);
    } else {
      next.set(name, value);
    }
    const query = next.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }

  return (
    <AdminGate status={status} onSignedIn={features.reload}>
      <AdminMain>
        <header className="flex animate-rise flex-col gap-1">
          <Link href="/admin" className="self-start text-small font-bold text-primary">
            ← Admin
          </Link>
          <h1 className="text-title-lg leading-tight font-extrabold">Features</h1>
          <p className="text-body text-muted">
            Switch features on for crews, and give crews a plan. Changes apply straight away, and each one is kept in
            the admin log with your reason.
          </p>
        </header>
        <fieldset className={`${segmentTrack} grid-cols-2 self-start`}>
          <legend className="sr-only">Show</legend>
          {(
            [
              ["switches", "Switches"],
              ["plans", "Crew plans"],
            ] as const
          ).map(([value, label]) => (
            <label key={value} className={segmentOption}>
              <input
                type="radio"
                name="tab"
                className="sr-only"
                checked={tab === value}
                onChange={() => {
                  setParam("tab", value === "switches" ? null : value);
                }}
              />
              {label}
            </label>
          ))}
        </fieldset>
        {features.result.kind === "loading" && <p className="text-muted">Loading features…</p>}
        {features.result.kind === "error" && status !== 404 && status !== 403 && (
          <p role="alert" className="text-warn">
            We couldn&apos;t load the features just now.
          </p>
        )}
        {features.result.kind === "ready" &&
          (tab === "switches" ? (
            <Switches
              features={features.result.data}
              area={params.get("area")}
              onArea={(area) => {
                setParam("area", area);
              }}
              onChanged={features.reload}
            />
          ) : (
            <Plans />
          ))}
      </AdminMain>
    </AdminGate>
  );
}

function Switches({
  features,
  area,
  onArea,
  onChanged,
}: {
  features: Feature[];
  area: string | null;
  onArea: (area: string | null) => void;
  onChanged: () => void;
}) {
  const [query, setQuery] = useState("");
  const [rollout, setRollout] = useState<Rollout | null>(null);
  const groups = useApiGet<AdminGroup[]>("/v1/admin/groups");
  const areas = areasOf(features);
  const current = area !== null && areas.includes(area) ? area : null;
  const shown = filterFeatures(features, { area: current, query, rollout });

  return (
    <>
      <fieldset className={`${segmentTrack} auto-cols-max grid-flow-col self-start overflow-x-auto`}>
        <legend className="sr-only">Area</legend>
        {[null, ...areas].map((a) => (
          <label key={a ?? "all"} className={segmentOption}>
            <input
              type="radio"
              name="area"
              className="sr-only"
              checked={current === a}
              onChange={() => {
                onArea(a);
              }}
            />
            {a === null ? "All" : (AREA_LABEL[a] ?? a)}
          </label>
        ))}
      </fieldset>
      <div className="flex flex-col gap-3 sm:flex-row">
        <label className="flex grow flex-col gap-1.5">
          <span className="text-small font-bold">Search</span>
          <input
            type="search"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
            }}
            placeholder="Name or key"
            className="min-h-11 rounded-xl border border-line bg-surface px-4 text-field"
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-small font-bold">Rollout</span>
          <select
            value={rollout ?? ""}
            onChange={(event) => {
              setRollout(event.target.value === "" ? null : (event.target.value as Rollout));
            }}
            className="min-h-11 rounded-xl border border-line bg-surface px-3 text-field"
          >
            <option value="">Any</option>
            {ROLLOUTS.map((r) => (
              <option key={r} value={r}>
                {ROLLOUT_LABEL[r]}
              </option>
            ))}
          </select>
        </label>
      </div>
      {shown.length === 0 ? (
        <p className="text-muted">No features match.</p>
      ) : (
        <ul aria-label="Features" className="flex flex-col gap-3">
          {shown.map((f) => (
            <li key={f.key}>
              <FeatureCard
                feature={f}
                groups={groups.result.kind === "ready" ? groups.result.data : []}
                onChanged={onChanged}
              />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function Pill({ children, tone = "plain" }: { children: string; tone?: "plain" | "on" | "off" }) {
  const colors = { plain: "bg-chip text-ink", on: "bg-win text-on-win", off: "bg-chip text-muted" }[tone];
  return <span className={`rounded-full px-2.5 py-0.5 text-meta font-bold ${colors}`}>{children}</span>;
}

function FeatureCard({
  feature,
  groups,
  onChanged,
}: {
  feature: Feature;
  groups: AdminGroup[];
  onChanged: () => void;
}) {
  const [showCrews, setShowCrews] = useState(false);
  return (
    <article
      aria-label={feature.title}
      className="flex flex-col gap-3 rounded-3xl border border-transparent bg-surface shadow-card p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <h3 className="text-title-sm font-extrabold">{feature.title}</h3>
          <code className="text-meta break-all text-muted">{feature.key}</code>
        </div>
        <EditSwitchSheet feature={feature} onDone={onChanged} />
      </div>
      <p className="text-body text-muted">{feature.description}</p>
      <div className="flex flex-wrap gap-1.5">
        <Pill tone={feature.rollout === "off" ? "off" : "on"}>{ROLLOUT_LABEL[feature.rollout]}</Pill>
        <Pill>{feature.needs_plan ? "Organizer" : "Free"}</Pill>
        <Pill>{reachText(feature)}</Pill>
      </div>
      <p className="text-meta text-muted">
        Changed {shortDate(feature.updated_at)}
        {feature.updated_by ? ` by ${feature.updated_by}` : ""}
      </p>
      <div className="flex flex-col gap-2 border-t border-line pt-3">
        <button
          type="button"
          aria-expanded={showCrews}
          className="self-start text-body font-bold text-primary"
          onClick={() => {
            setShowCrews(!showCrews);
          }}
        >
          {showCrews ? "Hide selected crews" : `Selected crews (${String(feature.crews)})`}
        </button>
        {showCrews && <FeatureCrews feature={feature} groups={groups} onChanged={onChanged} />}
      </div>
    </article>
  );
}

function EditSwitchSheet({ feature, onDone }: { feature: Feature; onDone: () => void }) {
  const { user } = useSignedIn();
  const [rollout, setRollout] = useState<Rollout>(feature.rollout);
  const [paid, setPaid] = useState(feature.needs_plan !== null);
  const changed = rollout !== feature.rollout || paid !== (feature.needs_plan !== null);
  return (
    <ChangeSheet
      trigger={
        <button type="button" className={buttonClass("quiet", SMALL_BUTTON)}>
          Change
        </button>
      }
      title={`Change ${feature.title}`}
      description="Who gets it, and whether it needs the Organizer plan. Applies straight away."
      confirm="Save"
      ready={changed}
      fields={
        <>
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1.5 font-bold">Rollout</legend>
            <div className={`${segmentTrack} grid-cols-3`}>
              {ROLLOUTS.map((r) => (
                <label key={r} className={segmentOption}>
                  <input
                    type="radio"
                    name={`rollout-${feature.key}`}
                    className="sr-only"
                    checked={rollout === r}
                    onChange={() => {
                      setRollout(r);
                    }}
                  />
                  {ROLLOUT_LABEL[r]}
                </label>
              ))}
            </div>
            <p className="text-meta text-muted">
              Off beats everything. Selected crews uses the list on the card. Everyone reaches every crew, or every crew
              on Organizer when it needs the plan.
            </p>
          </fieldset>
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1.5 font-bold">Plan</legend>
            <div className={`${segmentTrack} grid-cols-2`}>
              {(
                [
                  [false, "Free"],
                  [true, "Needs Organizer"],
                ] as const
              ).map(([value, label]) => (
                <label key={label} className={segmentOption}>
                  <input
                    type="radio"
                    name={`plan-${feature.key}`}
                    className="sr-only"
                    checked={paid === value}
                    onChange={() => {
                      setPaid(value);
                    }}
                  />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>
        </>
      }
      save={async (reason) => {
        // Keys have dots, which the proxy refuses in a path, so they go in the body.
        const key = feature.key;
        if (rollout !== feature.rollout) {
          await apiPut(user, "/v1/admin/features/rollout", { key, rollout, reason });
        }
        if (paid !== (feature.needs_plan !== null)) {
          await apiPut(user, "/v1/admin/features/plan", { key, needs_plan: paid ? "organizer" : null, reason });
        }
      }}
      onDone={onDone}
    />
  );
}

function FeatureCrews({
  feature,
  groups,
  onChanged,
}: {
  feature: Feature;
  groups: AdminGroup[];
  onChanged: () => void;
}) {
  const { user } = useSignedIn();
  const crews = useApiGet<FeatureCrew[]>(`/v1/admin/features/crews?key=${encodeURIComponent(feature.key)}`);
  const refresh = () => {
    crews.reload();
    onChanged();
  };
  const listed = crews.result.kind === "ready" ? crews.result.data : [];
  return (
    <div className="flex flex-col gap-2">
      {feature.rollout !== "crews" && (
        <p className="text-meta text-muted">This list is used when the rollout is Selected crews.</p>
      )}
      {crews.result.kind === "loading" && <p className="text-small text-muted">Loading…</p>}
      {crews.result.kind === "ready" && listed.length === 0 && (
        <p className="text-small text-muted">No crews on the list.</p>
      )}
      {listed.length > 0 && (
        <ul aria-label={`${feature.title}: selected crews`} className="flex flex-col divide-y divide-line">
          {listed.map((c) => (
            <li key={c.group_id} className="flex items-center justify-between gap-3 py-2">
              <span className="flex min-w-0 flex-col">
                <Link href={`/admin/crews/${c.group_id}`} className="truncate font-bold text-primary">
                  {c.name}
                </Link>
                <span className="text-meta text-muted">
                  Added {shortDate(c.added_at)}
                  {c.added_by ? ` by ${c.added_by}` : ""}
                </span>
              </span>
              <ChangeSheet
                trigger={
                  <button type="button" className={buttonClass("quiet", SMALL_BUTTON)}>
                    Remove
                  </button>
                }
                title={`Take ${c.name} off ${feature.title}`}
                description="The crew comes off this feature's list straight away."
                confirm="Remove"
                save={async (reason) => {
                  await apiPost(user, `/v1/admin/features/crews/${c.group_id}/remove`, { key: feature.key, reason });
                }}
                onDone={refresh}
              />
            </li>
          ))}
        </ul>
      )}
      <AddCrewSheet
        feature={feature}
        groups={groups.filter((g) => !listed.some((c) => c.group_id === g.id))}
        onDone={refresh}
      />
    </div>
  );
}

function CrewPicker({
  groups,
  picked,
  onPick,
  name,
}: {
  groups: AdminGroup[];
  picked: string | null;
  onPick: (id: string) => void;
  name: string;
}) {
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  const matches = q === "" ? [] : groups.filter((g) => g.name.toLowerCase().includes(q)).slice(0, 8);
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-1.5 font-bold">Crew</legend>
      <input
        type="search"
        aria-label="Find a crew"
        value={query}
        onChange={(event) => {
          setQuery(event.target.value);
        }}
        placeholder="Type a crew's name"
        className="min-h-12 rounded-xl border border-line bg-bg px-4 text-field"
      />
      {q !== "" && matches.length === 0 && <p className="text-small text-muted">No crews match.</p>}
      {matches.map((g) => (
        <label
          key={g.id}
          className="flex min-h-11 cursor-pointer items-center gap-3 rounded-xl border border-line px-3 has-[:checked]:border-primary"
        >
          <input
            type="radio"
            name={name}
            checked={picked === g.id}
            onChange={() => {
              onPick(g.id);
            }}
          />
          <span className="grow font-bold">{g.name}</span>
          <span className="text-meta text-muted">
            {g.members} {g.members === 1 ? "member" : "members"} · {g.games} {g.games === 1 ? "game" : "games"}
          </span>
        </label>
      ))}
    </fieldset>
  );
}

function AddCrewSheet({ feature, groups, onDone }: { feature: Feature; groups: AdminGroup[]; onDone: () => void }) {
  const { user } = useSignedIn();
  const [picked, setPicked] = useState<string | null>(null);
  return (
    <ChangeSheet
      trigger={
        <button type="button" className={buttonClass("quiet", `${SMALL_BUTTON} self-start`)}>
          Add a crew
        </button>
      }
      title={`Add a crew to ${feature.title}`}
      description="The crew goes on this feature's list straight away."
      confirm="Add crew"
      ready={picked !== null}
      fields={<CrewPicker groups={groups} picked={picked} onPick={setPicked} name={`add-${feature.key}`} />}
      save={async (reason) => {
        if (picked !== null) {
          await apiPost(user, `/v1/admin/features/crews/${picked}`, { key: feature.key, reason });
        }
      }}
      onDone={() => {
        setPicked(null);
        onDone();
      }}
    />
  );
}

const PLAN_STATE_LABEL = { running: "Running", ended: "Ended", not_started: "Not started" } as const;

function Plans() {
  const plans = useApiGet<PlanRow[]>("/v1/admin/plans");
  const groups = useApiGet<AdminGroup[]>("/v1/admin/groups");
  const now = new Date();
  return (
    <Section title="Crew plans">
      <GrantPlanSheet groups={groups.result.kind === "ready" ? groups.result.data : []} onDone={plans.reload} />
      {plans.result.kind === "loading" && <p className="text-muted">Loading plans…</p>}
      {plans.result.kind === "error" && (
        <p role="alert" className="text-warn">
          We couldn&apos;t load the plans just now.
        </p>
      )}
      {plans.result.kind === "ready" && plans.result.data.length === 0 && (
        <p className="text-muted">No crew has a plan yet.</p>
      )}
      {plans.result.kind === "ready" && plans.result.data.length > 0 && (
        <ul aria-label="Crew plans" className="flex flex-col gap-2">
          {plans.result.data.map((p) => {
            const state = planState(p, now);
            return (
              <li
                key={`${p.group_id}-${p.plan}`}
                className="flex flex-wrap items-center justify-between gap-3 rounded-3xl border border-transparent bg-surface shadow-card p-4"
              >
                <span className="flex min-w-0 flex-col gap-1">
                  <Link href={`/admin/crews/${p.group_id}`} className="truncate font-bold text-primary">
                    {p.name}
                  </Link>
                  <span className="text-meta text-muted">
                    Organizer · {SOURCE_LABEL[p.source]} · since {shortDate(p.starts_at)}
                    {p.ends_at ? ` · ${state === "ended" ? "ended" : "ends"} ${shortDate(p.ends_at)}` : ""}
                    {p.note ? ` · ${p.note}` : ""}
                  </span>
                </span>
                <Pill tone={state === "running" ? "on" : "off"}>{PLAN_STATE_LABEL[state]}</Pill>
              </li>
            );
          })}
        </ul>
      )}
    </Section>
  );
}

/** Give a crew the Organizer plan, or change the one it has. Pass `crew` to fix the crew. */
export function GrantPlanSheet({
  groups = [],
  crew,
  onDone,
}: {
  groups?: AdminGroup[];
  crew?: { id: string; name: string };
  onDone: () => void;
}) {
  const { user } = useSignedIn();
  const [picked, setPicked] = useState<string | null>(null);
  const [source, setSource] = useState<PlanSource>("beta");
  const [ends, setEnds] = useState("");
  const [note, setNote] = useState("");
  const target = crew?.id ?? picked;
  return (
    <ChangeSheet
      trigger={
        <button type="button" className={buttonClass("quiet", `${SMALL_BUTTON} self-start`)}>
          {crew ? "Give or change Organizer" : "Give a crew Organizer"}
        </button>
      }
      title={crew ? `Organizer for ${crew.name}` : "Give a crew Organizer"}
      description="Organizer unlocks the features that need it. It starts straight away; a running plan keeps its start."
      confirm="Save plan"
      ready={target !== null}
      fields={
        <>
          {!crew && <CrewPicker groups={groups} picked={picked} onPick={setPicked} name="grant-plan" />}
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1.5 font-bold">Source</legend>
            <div className={`${segmentTrack} grid-cols-3`}>
              {(Object.keys(SOURCE_LABEL) as PlanSource[]).map((s) => (
                <label key={s} className={segmentOption}>
                  <input
                    type="radio"
                    name="plan-source"
                    className="sr-only"
                    checked={source === s}
                    onChange={() => {
                      setSource(s);
                    }}
                  />
                  {SOURCE_LABEL[s]}
                </label>
              ))}
            </div>
          </fieldset>
          <label className="flex flex-col gap-1.5">
            <span className="font-bold">Ends (optional)</span>
            <input
              type="date"
              value={ends}
              onChange={(event) => {
                setEnds(event.target.value);
              }}
              className="min-h-12 rounded-xl border border-line bg-bg px-4 text-field"
            />
            <span className="text-meta text-muted">Leave empty for no end. It ends at the close of that day.</span>
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="font-bold">Note (optional)</span>
            <input
              value={note}
              maxLength={200}
              onChange={(event) => {
                setNote(event.target.value);
              }}
              className="min-h-12 rounded-xl border border-line bg-bg px-4 text-field"
            />
          </label>
        </>
      }
      save={async (reason) => {
        if (target === null) {
          return;
        }
        await apiPut(user, `/v1/admin/groups/${target}/plans/organizer`, {
          source,
          ends_at: ends ? new Date(`${ends}T23:59:59`).toISOString() : null,
          note: note.trim() || null,
          reason,
        });
      }}
      onDone={() => {
        setPicked(null);
        setEnds("");
        setNote("");
        onDone();
      }}
    />
  );
}

/** The admin crew page: this crew's plan and what's on for it. */
export function CrewAccessSection({
  crewId,
  crewName,
  onChanged,
}: {
  crewId: string;
  crewName: string;
  // The crew page reloads too, so its support history shows the change.
  onChanged: () => void;
}) {
  const { user } = useSignedIn();
  const access = useApiGet<CrewAccess>(`/v1/admin/groups/${crewId}/access`);
  const changed = () => {
    access.reload();
    onChanged();
  };
  const now = new Date();
  const running =
    access.result.kind === "ready" ? access.result.data.plans.find((p) => planState(p, now) === "running") : undefined;
  return (
    <Section title="Plan and features">
      {access.result.kind === "loading" && <p className="text-muted">Loading…</p>}
      {access.result.kind === "error" && (
        <p role="alert" className="text-warn">
          We couldn&apos;t load this crew&apos;s plan just now.
        </p>
      )}
      {access.result.kind === "ready" && (
        <div className="flex flex-col gap-3 rounded-3xl border border-transparent bg-surface shadow-card p-4">
          <p className="text-body">
            {running
              ? `Organizer (${SOURCE_LABEL[running.source]}) since ${shortDate(running.starts_at)}${
                  running.ends_at ? `, ends ${shortDate(running.ends_at)}` : ""
                }.`
              : "No plan running."}
          </p>
          <p className="text-small text-muted">
            On for this crew:{" "}
            {access.result.data.features.length > 0 ? access.result.data.features.join(", ") : "nothing switchable"}
          </p>
          <div className="flex flex-wrap gap-2">
            <GrantPlanSheet crew={{ id: crewId, name: crewName }} onDone={changed} />
            {running && (
              <ChangeSheet
                trigger={
                  <button type="button" className={buttonClass("quiet", SMALL_BUTTON)}>
                    End plan
                  </button>
                }
                title={`End Organizer for ${crewName}`}
                description="Features that need Organizer go away for this crew straight away. Events already running can finish."
                confirm="End plan"
                save={async (reason) => {
                  await apiPost(user, `/v1/admin/groups/${crewId}/plans/organizer/end`, { reason });
                }}
                onDone={changed}
              />
            )}
          </div>
        </div>
      )}
    </Section>
  );
}
