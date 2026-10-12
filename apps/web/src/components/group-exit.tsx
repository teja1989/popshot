"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { apiDelete, apiPost, ApiError } from "@/lib/api-client";
import type { GroupDetail } from "@/lib/groups";

import { useSignedIn } from "./auth";
import { buttonClass } from "./ui/button";
import { Sheet } from "./ui/sheet";

const RESTORE_DAYS = 30;

/** Leaving a group (or cancelling a request to join), and deleting it for its lead. */
export function GroupExit({ group }: { group: GroupDetail }) {
  const isLead = group.my_status === "active" && group.my_role === "lead";
  return (
    <div className="flex flex-col items-start gap-3">
      {isLead ? (
        <>
          <p className="text-[15px] text-muted">
            To leave, make someone else the lead first (Manage, next to their name).
          </p>
          <DeleteGroup group={group} />
        </>
      ) : (
        <LeaveGroup group={group} />
      )}
    </div>
  );
}

function LeaveGroup({ group }: { group: GroupDetail }) {
  const { user } = useSignedIn();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const pending = group.my_status === "pending";

  async function leave() {
    setBusy(true);
    setProblem(null);
    try {
      await apiPost(user, `/v1/groups/${group.id}/leave`, {});
      router.push("/");
    } catch (error) {
      setProblem(error instanceof ApiError && error.detail ? error.detail : "We couldn't do that just now.");
      setBusy(false);
    }
  }

  return (
    <Sheet
      trigger={
        <button type="button" className={buttonClass("quiet", "min-h-11 px-4 text-[15px]")}>
          {pending ? "Cancel your request" : "Leave group"}
        </button>
      }
      open={open}
      onOpenChange={setOpen}
      title={pending ? `Cancel your request to join ${group.name}?` : `Leave ${group.name}?`}
      description={
        pending
          ? "You can ask again later with an invite link."
          : "Your games stay on the group's record. To come back, ask for a new invite link."
      }
    >
      <div className="flex flex-col gap-3">
        <p role="alert" className="text-[15px] text-warn empty:hidden">
          {problem}
        </p>
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            className={buttonClass("quiet")}
            onClick={() => {
              setOpen(false);
            }}
          >
            Stay
          </button>
          <button type="button" className={buttonClass("danger")} disabled={busy} onClick={() => void leave()}>
            {pending ? "Cancel request" : "Leave"}
          </button>
        </div>
      </div>
    </Sheet>
  );
}

function DeleteGroup({ group }: { group: GroupDetail }) {
  const { user } = useSignedIn();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const matches = typed.trim() === group.name;

  async function remove() {
    setBusy(true);
    setProblem(null);
    try {
      await apiDelete(user, `/v1/groups/${group.id}`);
      router.push("/");
    } catch (error) {
      setProblem(error instanceof ApiError && error.detail ? error.detail : "We couldn't delete it just now.");
      setBusy(false);
    }
  }

  return (
    <Sheet
      trigger={
        <button type="button" className={buttonClass("danger", "min-h-11 px-4 text-[15px]")}>
          Delete group
        </button>
      }
      open={open}
      onOpenChange={(next) => {
        setTyped("");
        setProblem(null);
        setOpen(next);
      }}
      title={`Delete ${group.name}?`}
      description={`It disappears for everyone, games included. You can restore it from Home for ${String(RESTORE_DAYS)} days; after that it's gone for good.`}
    >
      <div className="flex flex-col gap-4">
        <label className="flex flex-col gap-2">
          <span className="text-[15px] font-bold">Type the group&apos;s name to confirm</span>
          <input
            value={typed}
            onChange={(event) => {
              setTyped(event.target.value);
            }}
            autoComplete="off"
            placeholder={group.name}
            className="min-h-12 rounded-xl border border-line bg-bg px-4 text-[17px] text-ink placeholder:text-muted"
          />
        </label>
        <p role="alert" className="text-[15px] text-warn empty:hidden">
          {problem}
        </p>
        <button
          type="button"
          className={buttonClass("danger", "h-14 w-full")}
          disabled={!matches || busy}
          onClick={() => void remove()}
        >
          {busy ? "Deleting…" : "Delete group"}
        </button>
      </div>
    </Sheet>
  );
}
