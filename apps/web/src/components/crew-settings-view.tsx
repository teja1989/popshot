"use client";

import Link from "next/link";
import { useId, useMemo, useRef, useState, type ReactNode, type SubmitEvent } from "react";

import { apiPatch, apiPut, ApiError } from "@/lib/api-client";
import { ABOUT_MAX, DAY_LABEL, DAYS, TIME_LABEL, TIMES, hasLink, type Day, type TimeOfDay } from "@/lib/crew-profile";
import { sectionsFor, type SectionId } from "@/lib/crew-settings";
import { describeRules, GROUP_NAME_MAX, type GroupDetail } from "@/lib/groups";
import { MEMBERS_DEFAULT, MEMBERS_MAX, MEMBERS_MIN, OPEN_FEATURE } from "@/lib/open-crews";
import { knownZones, zoneChoices, zoneLabel } from "@/lib/time-zone";

import { useSignedIn } from "./auth";
import { CrewCourts } from "./crew-courts";
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
  open: OpenSection,
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
      <TimeZoneForm group={group} onSaved={onSaved} />
    </SettingsSection>
  );
}

function TimeZoneForm({ group, onSaved }: SectionProps) {
  const [zone, setZone] = useState(group.time_zone);
  const choices = useMemo(() => zoneChoices(group.time_zone, knownZones()), [group.time_zone]);
  // The API keeps a zone's current name (Asia/Calcutta is kept as Asia/Kolkata): show that.
  const { save, saving, status, clearSaved } = useSave(group, (saved) => {
    setZone(saved.time_zone);
    onSaved(saved);
  });

  return (
    <form
      className="flex flex-col gap-4 border-t border-line pt-4"
      onSubmit={(event) => {
        event.preventDefault();
        void save({ time_zone: zone });
      }}
    >
      <label className="flex flex-col gap-2">
        <span className="text-body font-bold">Time zone</span>
        <span className="text-small text-muted">Your crew&apos;s days and recaps follow this clock.</span>
        <select
          value={zone}
          onChange={(event) => {
            setZone(event.target.value);
            clearSaved();
          }}
          className="min-h-12 rounded-xl border border-line bg-bg px-4 text-field text-ink"
        >
          {choices.map((name) => (
            <option key={name} value={name}>
              {zoneLabel(name)}
            </option>
          ))}
        </select>
      </label>
      <div className="flex items-center gap-3">
        <button type="submit" className={buttonClass("primary")} disabled={saving || zone === group.time_zone}>
          {saving ? "Saving…" : "Save time zone"}
        </button>
        {status}
      </div>
    </form>
  );
}

function CourtSection({ group, onSaved }: SectionProps) {
  return (
    <SettingsSection
      title="Courts"
      description="Where your crew plays. The default is picked first for meetups. Only members see these."
    >
      <CrewCourts group={group} onSaved={onSaved} />
    </SettingsSection>
  );
}

function OpenSection({ group, onSaved }: SectionProps) {
  const on = useFeature(OPEN_FEATURE, group.id);
  if (!on) {
    return null;
  }
  return <OpenForm group={group} onSaved={onSaved} />;
}

function OpenForm({ group, onSaved }: SectionProps) {
  const { user } = useSignedIn();
  const [open, setOpen] = useState(group.open_to_all ?? false);
  const [cap, setCap] = useState(String(group.max_members ?? MEMBERS_DEFAULT));
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const capId = useId();
  const onMap = (group.courts ?? []).some((c) => c.is_default && c.google_place_id);
  const capNumber = Number(cap);
  const capOk = Number.isInteger(capNumber) && capNumber >= MEMBERS_MIN && capNumber <= MEMBERS_MAX;
  const unchanged = open === (group.open_to_all ?? false) && capNumber === (group.max_members ?? MEMBERS_DEFAULT);

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!capOk) {
      setProblem(`Pick between ${String(MEMBERS_MIN)} and ${String(MEMBERS_MAX)} players.`);
      return;
    }
    setSaving(true);
    setProblem(null);
    setSaved(false);
    try {
      onSaved(await apiPut<GroupDetail>(user, `/v1/groups/${group.id}/open`, { open, max_members: capNumber }));
      setSaved(true);
    } catch (error) {
      setProblem(error instanceof ApiError && error.detail ? error.detail : "We couldn't save that just now.");
    } finally {
      setSaving(false);
    }
  }

  if (group.unlisted) {
    return (
      <SettingsSection title="Open crew">
        <p className="text-body">
          Popshot&apos;s team took this crew off the listing, so it can&apos;t be opened for now. Write to us if that
          seems wrong.
        </p>
      </SettingsSection>
    );
  }

  return (
    <SettingsSection
      title="Open crew"
      description="Anyone on Popshot can find an open crew near its default court and join straight away."
    >
      {group.closed_for_court && !group.open_to_all && (
        <p role="note" className="rounded-2xl bg-surface-high p-4 text-body">
          Your crew was closed because its default court isn&apos;t one from the map. Make a court from the map the
          default, then open it again.
        </p>
      )}
      <form className="flex flex-col gap-4" onSubmit={(event) => void submit(event)} noValidate>
        <label className="flex min-h-11 items-center justify-between gap-4">
          <span className="text-body font-bold">Open to anyone on Popshot</span>
          <input
            type="checkbox"
            role="switch"
            checked={open}
            disabled={!onMap && !open}
            onChange={(event) => {
              setOpen(event.target.checked);
              setSaved(false);
            }}
            className="size-6 accent-primary"
          />
        </label>
        {!onMap && !open && (
          <p className="text-small text-muted">Make a court from the map your default first (Courts, above).</p>
        )}
        <label htmlFor={capId} className="flex flex-col gap-2">
          <span className="text-body font-bold">Players who can join from the listing</span>
          <input
            id={capId}
            type="number"
            inputMode="numeric"
            min={MEMBERS_MIN}
            max={MEMBERS_MAX}
            value={cap}
            onChange={(event) => {
              setCap(event.target.value);
              setSaved(false);
            }}
            className="min-h-12 w-28 rounded-xl border border-line bg-bg px-4 text-field text-ink"
          />
          <span className="text-small text-muted">Joins stop at this many players. Invites still work as before.</span>
        </label>
        <ul className="flex list-disc flex-col gap-1 pl-5 text-small text-muted">
          <li>The listing shows the crew&apos;s name, about, usual times, default court and how many play.</li>
          <li>Members, games and stats stay for members.</li>
          <li>Members are told when the crew opens, and can leave any time.</li>
        </ul>
        <div className="flex items-center gap-3">
          <button type="submit" className={buttonClass("primary")} disabled={saving || unchanged}>
            {saving ? "Saving…" : "Save"}
          </button>
          <p role="status" className={`text-body ${problem ? "text-warn" : "text-muted"} empty:hidden`}>
            {problem ?? (saved ? "Saved." : "")}
          </p>
        </div>
      </form>
    </SettingsSection>
  );
}

function ProfileSection({ group, onSaved }: SectionProps) {
  const { user } = useSignedIn();
  const [about, setAbout] = useState(group.about ?? "");
  const [days, setDays] = useState<Day[]>(group.usual_days ?? []);
  const [times, setTimes] = useState<TimeOfDay[]>(group.usual_times ?? []);
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
    if (hasLink(about)) {
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
    <SettingsSection title="Crew profile" description="Helps people decide to join. It shows on invites.">
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
