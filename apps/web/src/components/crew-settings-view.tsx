"use client";

import Link from "next/link";
import { useId, useRef, useState, type ReactNode, type SubmitEvent } from "react";

import { apiPatch, apiPut, ApiError } from "@/lib/api-client";
import {
  ABOUT_MAX,
  COURT_MAX,
  COURTS_MAX,
  DAY_LABEL,
  DAYS,
  TIME_LABEL,
  TIMES,
  hasLink,
  type Day,
  type TimeOfDay,
} from "@/lib/crew-profile";
import { sectionsFor, type SectionId } from "@/lib/crew-settings";
import { describeRules, GROUP_NAME_MAX, type GroupDetail } from "@/lib/groups";
import { PLACES_FEATURE } from "@/lib/places";

import { useSignedIn } from "./auth";
import { CourtPicker } from "./court-picker";
import { useFeature } from "./features";
import { GroupExit } from "./group-exit";
import { GroupRulesFields, type Rules } from "./group-rules-fields";
import { buttonClass } from "./ui/button";
import { BackIcon } from "./ui/icons";
import { useApiGet } from "./use-api";

interface SectionProps {
  group: GroupDetail;
  onSaved: (group: GroupDetail) => void;
}

// One component per section in lib/crew-settings.ts. A new section is a new entry in both.
const SECTION_VIEWS: Record<SectionId, (props: SectionProps) => ReactNode> = {
  crew: CrewSection,
  court: CourtSection,
  profile: ProfileSection,
  rules: RulesSection,
  leave: LeaveSection,
};

/** A crew's settings: a column of sections, each saved on its own. */
export function CrewSettingsView({ groupId }: { groupId: string }) {
  const { result, replace } = useApiGet<GroupDetail>(`/v1/groups/${groupId}`);
  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-6 px-5 pt-6 pb-12 lg:max-w-2xl lg:px-8 lg:pt-10">
      <Link href={`/groups/${groupId}`} className="flex items-center gap-1 self-start text-body font-bold text-primary">
        <BackIcon />
        {result.kind === "ready" ? result.data.name : "Back"}
      </Link>
      <h1 className="text-display-sm leading-[1.08] font-extrabold tracking-[-0.02em] font-display">Settings</h1>
      {result.kind === "loading" && <p className="text-muted">Loading…</p>}
      {result.kind === "error" && (
        <p role="alert" className="text-warn">
          {result.status === 404 ? "We couldn't find that group." : "We couldn't load the settings just now."}
        </p>
      )}
      {result.kind === "ready" &&
        sectionsFor(result.data).map((id) => {
          const View = SECTION_VIEWS[id];
          return <View key={id} group={result.data} onSaved={replace} />;
        })}
    </main>
  );
}

function SettingsSection({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="flex animate-rise flex-col gap-3">
      <div className="flex flex-col gap-1">
        <h2 id={id} className="text-title-sm font-bold text-ink">
          {title}
        </h2>
        {description && <p className="text-small text-muted">{description}</p>}
      </div>
      <div className="flex flex-col gap-4 rounded-3xl border border-transparent bg-surface shadow-card p-5">
        {children}
      </div>
    </section>
  );
}

/** Saves part of the crew's settings: the API keeps whatever isn't sent. */
function useSave(group: GroupDetail, onSaved: (group: GroupDetail) => void) {
  const { user } = useSignedIn();
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function save(changes: Record<string, unknown>): Promise<void> {
    setSaving(true);
    setProblem(null);
    setSaved(false);
    try {
      onSaved(await apiPatch<GroupDetail>(user, `/v1/groups/${group.id}`, changes));
      setSaved(true);
    } catch (error) {
      if (error instanceof ApiError && error.status === 422) {
        setProblem("That won't work. Check it and try again.");
      } else {
        setProblem(error instanceof ApiError && error.detail ? error.detail : "We couldn't save that just now.");
      }
    } finally {
      setSaving(false);
    }
  }

  const status = (
    <p role="status" className={`text-body ${problem ? "text-warn" : "text-muted"} empty:hidden`}>
      {problem ?? (saved ? "Saved." : "")}
    </p>
  );
  return {
    save,
    saving,
    status,
    clearSaved: () => {
      setSaved(false);
    },
  };
}

function CrewSection({ group, onSaved }: SectionProps) {
  const [name, setName] = useState(group.name);
  const nameRef = useRef<HTMLInputElement>(null);
  const { save, saving, status, clearSaved } = useSave(group, onSaved);
  const unchanged = name.trim() === group.name;

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) {
      nameRef.current?.focus();
      return;
    }
    void save({ name });
  }

  return (
    <SettingsSection title="Group">
      <form className="flex flex-col gap-4" onSubmit={submit} noValidate>
        <label className="flex flex-col gap-2">
          <span className="text-body font-bold">Group name</span>
          <input
            ref={nameRef}
            value={name}
            onChange={(event) => {
              setName(event.target.value);
              clearSaved();
            }}
            maxLength={GROUP_NAME_MAX}
            autoComplete="off"
            className="min-h-12 rounded-xl border border-line bg-bg px-4 text-field text-ink"
          />
        </label>
        <div className="flex items-center gap-3">
          <button type="submit" className={buttonClass("primary")} disabled={saving || unchanged || !name.trim()}>
            {saving ? "Saving…" : "Save name"}
          </button>
          {status}
        </div>
      </form>
    </SettingsSection>
  );
}

function CourtSection({ group, onSaved }: SectionProps) {
  if (!useFeature(PLACES_FEATURE, group.id)) {
    return null;
  }
  return (
    <SettingsSection
      title="Court on the map"
      description="Where your crew usually plays, found on Google Maps. Only members see it."
    >
      <CourtPicker group={group} onSaved={onSaved} />
    </SettingsSection>
  );
}

function ProfileSection({ group, onSaved }: SectionProps) {
  const { user } = useSignedIn();
  const [about, setAbout] = useState(group.about ?? "");
  const [days, setDays] = useState<Day[]>(group.usual_days ?? []);
  const [times, setTimes] = useState<TimeOfDay[]>(group.usual_times ?? []);
  const [courts, setCourts] = useState<string[]>(() => {
    const given = group.home_courts ?? [];
    return [...given, ...Array<string>(COURTS_MAX - given.length).fill("")];
  });
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  function toggle<T>(list: T[], value: T, on: boolean): T[] {
    return on ? [...list, value] : list.filter((v) => v !== value);
  }

  function changed() {
    setSaved(false);
    setProblem(null);
  }

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    changed();
    if ([about, ...courts].some(hasLink)) {
      setProblem("Leave out links and web or email addresses.");
      return;
    }
    setSaving(true);
    try {
      onSaved(
        await apiPut<GroupDetail>(user, `/v1/groups/${group.id}/profile`, {
          about: about.trim() || null,
          usual_days: days,
          usual_times: times,
          home_courts: courts.map((c) => c.trim()).filter(Boolean),
        }),
      );
      setSaved(true);
    } catch (error) {
      setProblem(
        error instanceof ApiError && error.status === 422
          ? "Check it again: no links, web or email addresses, and keep it short."
          : error instanceof ApiError && error.detail
            ? error.detail
            : "We couldn't save that just now.",
      );
    } finally {
      setSaving(false);
    }
  }

  const chip =
    "flex min-h-11 cursor-pointer items-center justify-center rounded-full border border-line px-4 text-body font-bold text-muted " +
    "has-[:checked]:border-primary has-[:checked]:bg-primary has-[:checked]:text-on-primary " +
    "has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-primary";

  return (
    <SettingsSection
      title="Crew profile"
      description="Helps people decide to join. About and times show on invites; courts only to members."
    >
      <form className="flex flex-col gap-5" onSubmit={(event) => void submit(event)} noValidate>
        <label className="flex flex-col gap-2">
          <span className="text-body font-bold">About</span>
          <textarea
            value={about}
            onChange={(event) => {
              setAbout(event.target.value);
              changed();
            }}
            maxLength={ABOUT_MAX}
            rows={3}
            placeholder="Friendly games, all levels. We rotate partners."
            className="rounded-xl border border-line bg-bg px-4 py-3 text-field text-ink"
          />
          <span className="text-meta text-muted">
            {String(about.length)}/{String(ABOUT_MAX)} · No links or contact details.
          </span>
        </label>

        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 text-body font-bold">Usual days</legend>
          <div className="flex flex-wrap gap-2">
            {DAYS.map((day) => (
              <label key={day} className={chip}>
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={days.includes(day)}
                  onChange={(event) => {
                    setDays(toggle(days, day, event.target.checked));
                    changed();
                  }}
                />
                {DAY_LABEL[day]}
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 text-body font-bold">Usual times</legend>
          <div className="flex flex-wrap gap-2">
            {TIMES.map((time) => (
              <label key={time} className={chip}>
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={times.includes(time)}
                  onChange={(event) => {
                    setTimes(toggle(times, time, event.target.checked));
                    changed();
                  }}
                />
                {TIME_LABEL[time].one}
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-body font-bold">Home courts</legend>
          <p className="text-meta text-muted">A court or park name, not a home address. Only members see these.</p>
          {courts.map((court, index) => (
            <input
              key={index}
              aria-label={`Home court ${String(index + 1)}`}
              value={court}
              onChange={(event) => {
                setCourts(courts.map((c, i) => (i === index ? event.target.value : c)));
                changed();
              }}
              maxLength={COURT_MAX}
              autoComplete="off"
              className="min-h-12 rounded-xl border border-line bg-bg px-4 text-field text-ink"
            />
          ))}
        </fieldset>

        <div className="flex items-center gap-3">
          <button type="submit" className={buttonClass("primary")} disabled={saving}>
            {saving ? "Saving…" : "Save profile"}
          </button>
          <p role="status" className={`text-body ${problem ? "text-warn" : "text-muted"} empty:hidden`}>
            {problem ?? (saved ? "Saved." : "")}
          </p>
        </div>
      </form>
    </SettingsSection>
  );
}

function rulesOf(group: GroupDetail): Rules {
  return { format: group.default_format, pointsTo: group.default_points_to, winByTwo: group.default_win_by_two };
}

function RulesSection({ group, onSaved }: SectionProps) {
  const [rules, setRules] = useState<Rules>(() => rulesOf(group));
  const { save, saving, status, clearSaved } = useSave(group, onSaved);
  const current = rulesOf(group);
  const unchanged =
    rules.format === current.format && rules.pointsTo === current.pointsTo && rules.winByTwo === current.winByTwo;

  return (
    <SettingsSection title="Game rules" description={`Now: ${describeRules(group)}.`}>
      <form
        className="flex flex-col gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          void save({
            default_format: rules.format,
            default_points_to: rules.pointsTo,
            default_win_by_two: rules.winByTwo,
          });
        }}
      >
        <GroupRulesFields
          rules={rules}
          onChange={(next) => {
            setRules(next);
            clearSaved();
          }}
        />
        <div className="flex items-center gap-3">
          <button type="submit" className={buttonClass("primary")} disabled={saving || unchanged}>
            {saving ? "Saving…" : "Save rules"}
          </button>
          {status}
        </div>
      </form>
    </SettingsSection>
  );
}

function LeaveSection({ group }: SectionProps) {
  const isLead = group.my_status === "active" && group.my_role === "lead";
  return (
    <SettingsSection title={isLead ? "Leave or delete" : "Leave"}>
      <GroupExit group={group} />
    </SettingsSection>
  );
}
