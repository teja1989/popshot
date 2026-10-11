"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";

import { apiPatch, ApiError } from "@/lib/api-client";
import { describeRules, ROLE_LABEL, type GroupDetail, type Member, type Role } from "@/lib/groups";
import type { MemberAction } from "@/lib/invites";

import { useSignedIn } from "./auth";
import { GroupExit } from "./group-exit";
import { GroupSettingsSheet } from "./group-settings-sheet";
import { InvitePanel } from "./invite-panel";
import { PlayNightsSection } from "./play-nights-section";
import { useApiGet } from "./use-api";
import { Avatar } from "./ui/avatar";
import { buttonClass } from "./ui/button";
import { BackIcon, PlusIcon } from "./ui/icons";
import { Sheet } from "./ui/sheet";

export function GroupView({ groupId }: { groupId: string }) {
  const { result, reload, replace } = useApiGet<GroupDetail>(`/v1/groups/${groupId}`);

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-5 px-5 pt-6 pb-12 lg:max-w-2xl lg:px-8 lg:pt-10">
      <Link
        href="/"
        className="-ml-1 flex min-h-11 items-center gap-1.5 self-start text-[15px] font-bold text-primary no-underline"
      >
        <BackIcon />
        Your groups
      </Link>

      {result.kind === "loading" && <p className="text-muted">Loading the group…</p>}

      {result.kind === "error" && result.status === 404 && (
        <section className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-5">
          <h1 className="text-[26px] font-extrabold [font-stretch:108%]">We couldn&apos;t find that group.</h1>
          <p className="text-muted">
            It may have been deleted, or you&apos;re not in it. Ask its lead for an invite.
          </p>
        </section>
      )}

      {result.kind === "error" && result.status !== 404 && (
        <div role="alert" className="flex flex-col items-start gap-3 rounded-2xl border border-line bg-surface p-5">
          <p>We couldn&apos;t load this group just now.</p>
          <button type="button" className={buttonClass("quiet")} onClick={reload}>
            Try again
          </button>
        </div>
      )}

      {result.kind === "ready" && <Group group={result.data} onChange={replace} onStale={reload} />}
    </main>
  );
}

/** Whether you can change `member`'s membership. Matches the API's rules. */
function canManage(myRole: Role, member: Member, isMe: boolean): boolean {
  if (isMe || member.role === "lead") {
    return false;
  }
  return myRole === "lead" || (myRole === "co_lead" && member.role === "member");
}

function Group({
  group,
  onChange,
  onStale,
}: {
  group: GroupDetail;
  onChange: (group: GroupDetail) => void;
  onStale: () => void;
}) {
  const { me, user } = useSignedIn();
  const active = group.members.filter((m) => m.status === "active");
  const waiting = group.members.filter((m) => m.status === "pending");
  const isAdmin = group.my_status === "active" && (group.my_role === "lead" || group.my_role === "co_lead");
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  async function act(member: Pick<Member, "user_id">, action: MemberAction): Promise<boolean> {
    setBusy(member.user_id);
    setProblem(null);
    try {
      onChange(await apiPatch<GroupDetail>(user, `/v1/groups/${group.id}/members/${member.user_id}`, { action }));
      return true;
    } catch (error) {
      setProblem(
        error instanceof ApiError && error.detail
          ? error.detail
          : "We couldn't make that change just now. Try again in a moment.",
      );
      // Someone else may have changed things first; show the current state.
      onStale();
      return false;
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <section className="flex animate-rise flex-col gap-1">
        <h1 className="text-[32px] leading-[1.08] font-extrabold tracking-[-0.02em] break-words [font-stretch:110%]">
          {group.name}
        </h1>
        <p className="text-[15px] text-muted">{describeRules(group)}</p>
        {isAdmin && (
          <div className="mt-2">
            <GroupSettingsSheet group={group} onSaved={onChange} />
          </div>
        )}
      </section>

      {group.my_status === "pending" ? (
        <section className="animate-rise rounded-2xl border border-line bg-surface p-5">
          <h2 className="text-[17px] font-bold">Waiting for approval</h2>
          <p className="mt-1 text-muted">
            The group&apos;s lead or a co-lead will let you in. You&apos;ll see the members and games once they do.
          </p>
        </section>
      ) : (
        <>
          <Link href={`/groups/${group.id}/log`} className={buttonClass("action", "h-14 animate-rise")}>
            <PlusIcon />
            Log a game
          </Link>

          <p role="alert" className="empty:hidden rounded-xl border border-line bg-surface p-3 text-warn">
            {problem}
          </p>

          <PlayNightsSection groupId={group.id} />

          {waiting.length > 0 && (
            <section aria-labelledby="waiting-heading" className="flex animate-rise flex-col gap-2">
              <h2 id="waiting-heading" className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
                Asking to join · {waiting.length}
              </h2>
              <ul className="overflow-hidden rounded-2xl border border-line bg-surface">
                {waiting.map((member) => (
                  <MemberRow key={member.user_id} member={member} isMe={false}>
                    {isAdmin && (
                      <div className="grid basis-full grid-cols-2 gap-2 sm:basis-auto sm:shrink-0">
                        <button
                          type="button"
                          aria-label={`Let ${member.display_name} in`}
                          className={buttonClass("primary", "min-h-11 px-4 text-[15px]")}
                          disabled={busy === member.user_id}
                          onClick={() => void act(member, "approve")}
                        >
                          Let in
                        </button>
                        <button
                          type="button"
                          aria-label={`Decline ${member.display_name}`}
                          className={buttonClass("quiet", "min-h-11 px-4 text-[15px]")}
                          disabled={busy === member.user_id}
                          onClick={() => void act(member, "decline")}
                        >
                          Decline
                        </button>
                      </div>
                    )}
                  </MemberRow>
                ))}
              </ul>
            </section>
          )}

          <section aria-labelledby="members-heading" className="flex animate-rise flex-col gap-2 [animation-delay:60ms]">
            <h2 id="members-heading" className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
              Members · {active.length}
            </h2>
            <ul className="overflow-hidden rounded-2xl border border-line bg-surface">
              {active.map((member) => {
                const isMe = member.user_id === me?.id;
                return (
                  <MemberRow key={member.user_id} member={member} isMe={isMe}>
                    {canManage(group.my_role, member, isMe) && (
                      <ManageSheet myRole={group.my_role} member={member} onAction={(action) => act(member, action)} />
                    )}
                  </MemberRow>
                );
              })}
            </ul>
          </section>

          {isAdmin && group.former_members.length > 0 && (
            <section aria-labelledby="former-heading" className="flex animate-rise flex-col gap-2 [animation-delay:90ms]">
              <h2 id="former-heading" className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
                Removed or declined · {group.former_members.length}
              </h2>
              <ul className="overflow-hidden rounded-2xl border border-line bg-surface">
                {group.former_members.map((person) => (
                  <li
                    key={person.user_id}
                    className="flex min-h-16 items-center gap-3 border-b border-line px-4 py-3 last:border-b-0"
                  >
                    <Avatar name={person.display_name} photoUrl={person.avatar_url} />
                    <span className="min-w-0 grow truncate text-[17px] font-bold text-muted">{person.display_name}</span>
                    <button
                      type="button"
                      aria-label={`Restore ${person.display_name}`}
                      className={buttonClass("quiet", "min-h-11 shrink-0 px-4 text-[15px]")}
                      disabled={busy === person.user_id}
                      onClick={() => void act(person, "restore")}
                    >
                      Restore
                    </button>
                  </li>
                ))}
              </ul>
              <p className="text-[14px] text-muted">Restoring puts them straight back in as a member.</p>
            </section>
          )}

          {isAdmin ? (
            <InvitePanel groupId={group.id} groupName={group.name} />
          ) : (
            <p className="animate-rise text-[15px] text-muted [animation-delay:120ms]">
              Want someone else in? Ask the lead or a co-lead for an invite link.
            </p>
          )}
        </>
      )}

      <GroupExit group={group} />
    </>
  );
}

function MemberRow({ member, isMe, children }: { member: Member; isMe: boolean; children?: ReactNode }) {
  return (
    <li className="flex min-h-16 flex-wrap items-center gap-3 border-b border-line px-4 py-3 last:border-b-0 sm:flex-nowrap">
      <Avatar
        name={member.display_name}
        photoUrl={member.avatar_url}
        tone={member.role === "lead" ? "ball" : "chip"}
      />
      <span className="min-w-0 grow truncate text-[17px] font-bold">
        {member.display_name}
        {isMe && <span className="font-normal text-muted"> (you)</span>}
      </span>
      {member.status === "active" && member.role !== "member" && (
        <span className="shrink-0 rounded-full bg-chip px-2.5 py-1 text-[13px] font-bold">
          {ROLE_LABEL[member.role]}
        </span>
      )}
      {children}
    </li>
  );
}

function ManageSheet({
  myRole,
  member,
  onAction,
}: {
  myRole: Role;
  member: Member;
  onAction: (action: MemberAction) => Promise<boolean>;
}) {
  const [open, setOpen] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [confirmLead, setConfirmLead] = useState(false);
  const [busy, setBusy] = useState(false);

  async function run(action: MemberAction) {
    setBusy(true);
    const done = await onAction(action);
    setBusy(false);
    if (done) {
      setOpen(false);
    }
  }

  return (
    <Sheet
      trigger={
        <button
          type="button"
          aria-label={`Manage ${member.display_name}`}
          className={buttonClass("quiet", "min-h-11 shrink-0 px-4 text-[15px]")}
        >
          Manage
        </button>
      }
      open={open}
      onOpenChange={(next) => {
        setConfirmRemove(false);
        setConfirmLead(false);
        setOpen(next);
      }}
      title={member.display_name}
      description={`${ROLE_LABEL[member.role]} of this group.`}
    >
      <div className="flex flex-col gap-3">
        {myRole === "lead" && member.role === "member" && (
          <ActionButton
            title="Make co-lead"
            body="Co-leads can make invite links, let people in, and remove members."
            disabled={busy}
            onClick={() => void run("make_co_lead")}
          />
        )}
        {myRole === "lead" && member.role === "co_lead" && (
          <ActionButton
            title="Make a regular member"
            body="They keep playing, but can't invite or manage people any more."
            disabled={busy}
            onClick={() => void run("make_member")}
          />
        )}
        {myRole === "lead" &&
          (confirmLead ? (
            <div className="flex flex-col gap-3 rounded-2xl border border-line p-4">
              <p className="font-bold">Make {member.display_name} the lead?</p>
              <p className="text-[15px] text-muted">
                You become a co-lead. Only the new lead can change that, delete the group or hand it on again.
              </p>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  className={buttonClass("quiet")}
                  onClick={() => {
                    setConfirmLead(false);
                  }}
                >
                  Not now
                </button>
                <button
                  type="button"
                  className={buttonClass("primary")}
                  disabled={busy}
                  onClick={() => void run("make_lead")}
                >
                  Make lead
                </button>
              </div>
            </div>
          ) : (
            <ActionButton
              title="Make lead"
              body="Hand the group over. You'll stay on as a co-lead."
              disabled={busy}
              onClick={() => {
                setConfirmLead(true);
              }}
            />
          ))}
        {confirmRemove ? (
          <div className="flex flex-col gap-3 rounded-2xl border border-warn p-4">
            <p className="font-bold">Remove {member.display_name} from the group?</p>
            <p className="text-[15px] text-muted">
              Their past games stay on the record. They lose access and can&apos;t rejoin with an
              invite link, but a lead or co-lead can restore them later.
            </p>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                className={buttonClass("quiet")}
                onClick={() => {
                  setConfirmRemove(false);
                }}
              >
                Keep
              </button>
              <button
                type="button"
                className={buttonClass("danger")}
                disabled={busy}
                onClick={() => void run("remove")}
              >
                Remove
              </button>
            </div>
          </div>
        ) : (
          <ActionButton
            title="Remove from group"
            body="Their past games stay on the record."
            disabled={busy}
            onClick={() => {
              setConfirmRemove(true);
            }}
          />
        )}
      </div>
    </Sheet>
  );
}

function ActionButton({
  title,
  body,
  disabled,
  onClick,
}: {
  title: string;
  body: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="flex min-h-16 cursor-pointer flex-col items-start gap-0.5 rounded-2xl border border-line bg-bg px-4 py-3 text-left disabled:cursor-progress disabled:opacity-60"
      disabled={disabled}
      onClick={onClick}
    >
      <span className="text-[17px] font-bold">{title}</span>
      <span className="text-[14px] text-muted">{body}</span>
    </button>
  );
}
