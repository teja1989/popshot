"use client";

import Link from "next/link";
import { useId, useRef, useState, type ReactNode, type SubmitEvent } from "react";

import { apiPatch, ApiError } from "@/lib/api-client";
import { sectionsFor, type SectionId } from "@/lib/crew-settings";
import { describeRules, GROUP_NAME_MAX, type GroupDetail } from "@/lib/groups";

import { useSignedIn } from "./auth";
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
  rules: RulesSection,
  leave: LeaveSection,
};

/** A crew's settings: a column of sections, each saved on its own. */
export function CrewSettingsView({ groupId }: { groupId: string }) {
  const { result, replace } = useApiGet<GroupDetail>(`/v1/groups/${groupId}`);
  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-6 px-5 pt-6 pb-12 lg:max-w-2xl lg:px-8 lg:pt-10">
      <Link
        href={`/groups/${groupId}`}
        className="flex items-center gap-1 self-start text-[15px] font-bold text-primary"
      >
        <BackIcon />
        {result.kind === "ready" ? result.data.name : "Back"}
      </Link>
      <h1 className="text-[32px] leading-[1.08] font-extrabold tracking-[-0.02em] [font-stretch:110%]">Settings</h1>
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
        <h2 id={id} className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
          {title}
        </h2>
        {description && <p className="text-[14px] text-muted">{description}</p>}
      </div>
      <div className="flex flex-col gap-4 rounded-2xl border border-line bg-surface p-5">{children}</div>
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
    <p role="status" className={`text-[15px] ${problem ? "text-warn" : "text-muted"} empty:hidden`}>
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
          <span className="text-[15px] font-bold">Group name</span>
          <input
            ref={nameRef}
            value={name}
            onChange={(event) => {
              setName(event.target.value);
              clearSaved();
            }}
            maxLength={GROUP_NAME_MAX}
            autoComplete="off"
            className="min-h-12 rounded-xl border border-line bg-bg px-4 text-[17px] text-ink"
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
