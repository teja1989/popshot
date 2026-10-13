"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";

import { apiDelete, apiPatch, apiPost, ApiError } from "@/lib/api-client";
import { ROLE_LABEL, type GroupDetail, type Member, type Role } from "@/lib/groups";
import type { MemberAction } from "@/lib/invites";
import { gamesCount, memberLine, type Guest } from "@/lib/members";

import { useSignedIn } from "./auth";
import { InvitePanel } from "./invite-panel";
import { InvitePeople } from "./invite-people";
import { useApiGet } from "./use-api";
import { Avatar } from "./ui/avatar";
import { buttonClass } from "./ui/button";
import { BackIcon } from "./ui/icons";
import { Sheet } from "./ui/sheet";

/** Everyone in a crew, its guests, and for leads and co-leads: who's waiting, and who's left. */
export function MembersView({ groupId }: { groupId: string }) {
  const { result, reload, replace } = useApiGet<GroupDetail>(`/v1/groups/${groupId}`);

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-5 px-5 pt-6 pb-12 lg:max-w-2xl lg:px-8 lg:pt-10">
      <Link
        href={`/groups/${groupId}`}
        className="-ml-1 flex min-h-11 items-center gap-1.5 self-start text-body font-bold text-primary no-underline"
      >
        <BackIcon />
        {result.kind === "ready" ? result.data.name : "Back to the group"}
      </Link>

      {result.kind === "loading" && <p className="text-muted">Loading the members…</p>}
      {result.kind === "error" && result.status === 404 && (
        <h1 className="text-title-lg font-extrabold font-display">We couldn&apos;t find that group.</h1>
      )}
      {result.kind === "error" && result.status !== 404 && (
        <div role="alert" className="flex flex-col items-start gap-3 rounded-2xl border border-line bg-surface p-5">
          <p>We couldn&apos;t load the members just now.</p>
          <button type="button" className={buttonClass("quiet")} onClick={reload}>
            Try again
          </button>
        </div>
      )}
      {result.kind === "ready" && result.data.my_status === "pending" && (
        <p className="text-muted">You&apos;ll see the members once the lead or a co-lead lets you in.</p>
      )}
      {result.kind === "ready" && result.data.my_status === "active" && (
        <Members group={result.data} onChange={replace} onStale={reload} />
      )}
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

function Members({
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
  const isAdmin = group.my_role === "lead" || group.my_role === "co_lead";
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  async function act(member: Pick<Member, "user_id">, action: MemberAction): Promise<boolean> {
    setBusy(member.user_id);
    setProblem(null);
    setNote(null);
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

  async function inviteBack(person: { user_id: string; display_name: string }) {
    setBusy(person.user_id);
    setProblem(null);
    setNote(null);
    try {
      await apiPost(user, `/v1/groups/${group.id}/direct-invites`, { user_id: person.user_id });
      setNote(`Invite sent to ${person.display_name}. They'll see it on their Home screen.`);
    } catch (error) {
      setProblem(
        error instanceof ApiError && error.detail
          ? error.detail
          : "We couldn't send that invite. Try again in a moment.",
      );
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <section className="flex animate-rise flex-col gap-1">
        <h1 className="text-display-sm leading-[1.08] font-extrabold tracking-[-0.02em] font-display">Members</h1>
        <p className="text-body text-muted">
          {active.length === 1 ? "1 member" : `${String(active.length)} members`} of {group.name}
        </p>
      </section>

      <p role="alert" className="rounded-xl border border-line bg-surface p-3 text-warn empty:hidden">
        {problem}
      </p>
      <p role="status" className="rounded-xl border border-line bg-surface p-3 empty:hidden">
        {note}
      </p>

      {isAdmin && waiting.length > 0 && (
        <section aria-labelledby="waiting-heading" className="flex animate-rise flex-col gap-2">
          <h2 id="waiting-heading" className="text-label font-bold tracking-[0.1em] text-muted uppercase">
            Asking to join · {waiting.length}
          </h2>
          <ul className="overflow-hidden rounded-2xl border border-line bg-surface">
            {waiting.map((member) => (
              <MemberRow key={member.user_id} member={member} isMe={false}>
                <div className="grid basis-full grid-cols-2 gap-2 sm:basis-auto sm:shrink-0">
                  <button
                    type="button"
                    aria-label={`Let ${member.display_name} in`}
                    className={buttonClass("primary", "min-h-11 px-4 text-body")}
                    disabled={busy === member.user_id}
                    onClick={() => void act(member, "approve")}
                  >
                    Let in
                  </button>
                  <button
                    type="button"
                    aria-label={`Decline ${member.display_name}`}
                    className={buttonClass("quiet", "min-h-11 px-4 text-body")}
                    disabled={busy === member.user_id}
                    onClick={() => void act(member, "decline")}
                  >
                    Decline
                  </button>
                </div>
              </MemberRow>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="members-heading" className="flex animate-rise flex-col gap-2 [animation-delay:60ms]">
        <h2 id="members-heading" className="text-label font-bold tracking-[0.1em] text-muted uppercase">
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

      <GuestsSection groupId={group.id} isAdmin={isAdmin} />

      {isAdmin && (
        <>
          <InvitePeople groupId={group.id} />
          <InvitePanel groupId={group.id} groupName={group.name} />
        </>
      )}
      {!isAdmin && (
        <p className="animate-rise text-body text-muted [animation-delay:120ms]">
          Want someone else in? Ask the lead or a co-lead to invite them.
        </p>
      )}

      {isAdmin && group.former_members.length > 0 && (
        <section aria-labelledby="former-heading" className="flex animate-rise flex-col gap-2 [animation-delay:90ms]">
          <h2 id="former-heading" className="text-label font-bold tracking-[0.1em] text-muted uppercase">
            Removed or declined · {group.former_members.length}
          </h2>
          <ul className="overflow-hidden rounded-2xl border border-line bg-surface">
            {group.former_members.map((person) => (
              <li
                key={person.user_id}
                className="flex min-h-16 flex-wrap items-center gap-3 border-b border-line px-4 py-3 last:border-b-0 sm:flex-nowrap"
              >
                <Avatar name={person.display_name} photoUrl={person.avatar_url} />
                <span className="min-w-0 grow truncate text-lead font-bold text-muted">{person.display_name}</span>
                <div className="grid basis-full grid-cols-2 gap-2 sm:basis-auto sm:shrink-0">
                  <button
                    type="button"
                    aria-label={`Restore ${person.display_name}`}
                    className={buttonClass("quiet", "min-h-11 px-4 text-body")}
                    disabled={busy === person.user_id}
                    onClick={() => void act(person, "restore")}
                  >
                    Restore
                  </button>
                  <button
                    type="button"
                    aria-label={`Invite ${person.display_name} back`}
                    className={buttonClass("quiet", "min-h-11 px-4 text-body")}
                    disabled={busy === person.user_id}
                    onClick={() => void inviteBack(person)}
                  >
                    Invite back
                  </button>
                </div>
              </li>
            ))}
          </ul>
          <p className="text-small text-muted">
            Restoring puts them straight back in. Inviting back lets them choose.
          </p>
        </section>
      )}
    </>
  );
}

function MemberRow({ member, isMe, children }: { member: Member; isMe: boolean; children?: ReactNode }) {
  return (
    <li className="flex min-h-16 flex-wrap items-center gap-3 border-b border-line px-4 py-3 last:border-b-0 sm:flex-nowrap">
      <Avatar name={member.display_name} photoUrl={member.avatar_url} tone={member.role === "lead" ? "ball" : "chip"} />
      <span className="flex min-w-0 grow flex-col">
        <span className="truncate text-lead font-bold">
          {member.display_name}
          {isMe && <span className="font-normal text-muted"> (you)</span>}
        </span>
        {member.status === "active" && <span className="text-small text-muted">{memberLine(member)}</span>}
      </span>
      {member.status === "active" && member.role !== "member" && (
        <span className="shrink-0 rounded-full bg-chip px-2.5 py-1 text-meta font-bold">
          {ROLE_LABEL[member.role]}
        </span>
      )}
      {children}
    </li>
  );
}

/** The crew's guests. Leads and co-leads rename them, or remove one who isn't in any game. */
function GuestsSection({ groupId, isAdmin }: { groupId: string; isAdmin: boolean }) {
  const { result, reload } = useApiGet<Guest[]>(`/v1/groups/${groupId}/guests`);
  if (result.kind !== "ready" || result.data.length === 0) {
    return null;
  }
  return (
    <section aria-labelledby="guests-heading" className="flex animate-rise flex-col gap-2 [animation-delay:90ms]">
      <h2 id="guests-heading" className="text-label font-bold tracking-[0.1em] text-muted uppercase">
        Guests · {result.data.length}
      </h2>
      <ul className="overflow-hidden rounded-2xl border border-line bg-surface">
        {result.data.map((guest) => (
          <li
            key={guest.id}
            className="flex min-h-16 items-center gap-3 border-b border-line px-4 py-3 last:border-b-0"
          >
            <Avatar name={guest.display_name} />
            <span className="flex min-w-0 grow flex-col">
              <span className="truncate text-lead font-bold">{guest.display_name}</span>
              <span className="text-small text-muted">Guest · {gamesCount(guest.games)}</span>
            </span>
            {isAdmin && <GuestSheet groupId={groupId} guest={guest} onChanged={reload} />}
          </li>
        ))}
      </ul>
      <p className="text-small text-muted">Guests are people added to games by name who haven&apos;t signed up.</p>
    </section>
  );
}

function GuestSheet({ groupId, guest, onChanged }: { groupId: string; guest: Guest; onChanged: () => void }) {
  const { user } = useSignedIn();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(guest.display_name);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setProblem(null);
    try {
      await action();
      setOpen(false);
      onChanged();
    } catch (error) {
      setProblem(error instanceof ApiError && error.detail ? error.detail : "That didn't work just now. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet
      trigger={
        <button
          type="button"
          aria-label={`Edit ${guest.display_name}`}
          className={buttonClass("quiet", "min-h-11 shrink-0 px-4 text-body")}
        >
          Edit
        </button>
      }
      open={open}
      onOpenChange={(next) => {
        setName(guest.display_name);
        setProblem(null);
        setOpen(next);
      }}
      title={guest.display_name}
      description={`Guest · ${gamesCount(guest.games)}`}
      fullOnPhone
    >
      <form
        className="flex flex-col gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          void run(() => apiPatch(user, `/v1/groups/${groupId}/guests/${guest.id}`, { display_name: name.trim() }));
        }}
      >
        <label className="flex flex-col gap-2">
          <span className="text-body font-bold">Name</span>
          <input
            value={name}
            onChange={(event) => {
              setName(event.target.value);
            }}
            maxLength={80}
            autoComplete="off"
            className="min-h-12 rounded-xl border border-line bg-bg px-4 text-field text-ink"
          />
        </label>
        <button type="submit" className={buttonClass("primary", "h-14 w-full")} disabled={busy || !name.trim()}>
          Save name
        </button>
      </form>
      <div className="mt-6 flex flex-col gap-2 border-t border-line pt-5">
        {guest.games === 0 ? (
          <button
            type="button"
            className={buttonClass("danger", "self-start")}
            disabled={busy}
            onClick={() => void run(() => apiDelete(user, `/v1/groups/${groupId}/guests/${guest.id}`))}
          >
            Remove guest
          </button>
        ) : (
          <p className="text-small text-muted">
            {guest.display_name} is in games, so they stay on the record. You can still change the name.
          </p>
        )}
      </div>
      <p role="alert" className="mt-3 min-h-6 text-body text-warn">
        {problem}
      </p>
    </Sheet>
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
          className={buttonClass("quiet", "min-h-11 shrink-0 px-4 text-body")}
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
              <p className="text-body text-muted">
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
            <p className="text-body text-muted">
              Their past games stay on the record. They lose access and can&apos;t rejoin with an invite link, but a
              lead or co-lead can restore them later.
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
      <span className="text-lead font-bold">{title}</span>
      <span className="text-small text-muted">{body}</span>
    </button>
  );
}
