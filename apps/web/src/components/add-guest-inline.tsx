"use client";

import { useId, useState } from "react";

import { apiPost, ApiError } from "@/lib/api-client";
import { NAME_MAX, type Player } from "@/lib/games";

import { useSignedIn } from "./auth";
import { buttonClass } from "./ui/button";

/** Add someone who isn't on Popshot to the crew as a guest, right where you are. */
export function AddGuestInline({
  groupId,
  onAdded,
  label = "Add a guest",
}: {
  groupId: string;
  onAdded: (player: Player) => Promise<void> | void;
  label?: string;
}) {
  const { user } = useSignedIn();
  const id = useId();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const trimmed = name.trim();

  async function add() {
    if (!trimmed || busy) {
      return;
    }
    setBusy(true);
    setProblem(null);
    try {
      const player = await apiPost<Player>(user, `/v1/groups/${groupId}/players`, { display_name: trimmed });
      await onAdded(player);
      setName("");
    } catch (error) {
      setProblem(error instanceof ApiError && error.detail ? error.detail : "That guest wasn't added just now.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-small font-bold">
        {label}
      </label>
      <div className="flex gap-2">
        <input
          id={id}
          value={name}
          maxLength={NAME_MAX}
          autoComplete="off"
          placeholder="Their name"
          onChange={(event) => {
            setName(event.target.value);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              void add();
            }
          }}
          className="min-h-11 grow rounded-xl border border-line bg-surface px-3 text-field"
        />
        <button
          type="button"
          disabled={!trimmed || busy}
          className={buttonClass("quiet", "min-h-11")}
          onClick={() => void add()}
        >
          {busy ? "Adding…" : "Add"}
        </button>
      </div>
      <p role="alert" className="text-small text-warn empty:hidden">
        {problem}
      </p>
    </div>
  );
}
