"use client";

import { useRef, useState, type SubmitEvent } from "react";

import { apiPost, ApiError } from "@/lib/api-client";
import { NAME_MAX, type Player } from "@/lib/games";

import { useSignedIn } from "./auth";
import { Avatar } from "./ui/avatar";
import { buttonClass } from "./ui/button";
import { PlusIcon } from "./ui/icons";
import { Sheet } from "./ui/sheet";

/** One player slot in a team: shows who's picked, and opens a sheet to pick or add a guest. */
export function PlayerPicker({
  groupId,
  label,
  players,
  selected,
  taken,
  onPick,
  onGuestAdded,
}: {
  groupId: string;
  label: string;
  players: Player[];
  selected: Player | null;
  // Players already in another slot of this game.
  taken: ReadonlySet<string>;
  onPick: (playerId: string | null) => void;
  onGuestAdded: (guest: Player) => void;
}) {
  const { user } = useSignedIn();
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const [guestName, setGuestName] = useState("");
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const filterRef = useRef<HTMLInputElement>(null);

  const query = filter.trim().toLowerCase();
  const shown = players.filter((p) => p.display_name.toLowerCase().includes(query));

  function choose(playerId: string | null) {
    onPick(playerId);
    setOpen(false);
  }

  async function addGuest(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    // The sheet renders in a portal, but React still bubbles events through the component
    // tree: without this, submitting here would also submit the log-a-game form around it.
    event.stopPropagation();
    if (!guestName.trim()) {
      setProblem("Type the guest's name.");
      return;
    }
    setSaving(true);
    setProblem(null);
    try {
      const guest = await apiPost<Player>(user, `/v1/groups/${groupId}/players`, { display_name: guestName });
      onGuestAdded(guest);
      setGuestName("");
      choose(guest.id);
    } catch (error) {
      setProblem(
        error instanceof ApiError && error.status === 422
          ? "That name won't work. Use letters, numbers, spaces and punctuation."
          : error instanceof ApiError && error.detail
            ? error.detail
            : "We couldn't add the guest just now. Try again in a moment.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Sheet
      trigger={
        <button
          type="button"
          aria-label={selected ? `${label}: ${selected.display_name}. Change` : `${label}: pick a player`}
          className="flex min-h-14 w-full cursor-pointer items-center gap-3 rounded-xl border border-line bg-bg px-3 text-left"
        >
          {selected ? (
            <>
              <Avatar name={selected.display_name} photoUrl={selected.avatar_url} size="sm" />
              <span className="min-w-0 grow truncate text-[17px] font-bold">
                {selected.display_name}
                {selected.is_me && <span className="font-normal text-muted"> (you)</span>}
              </span>
              {selected.is_guest && <span className="text-[13px] font-bold text-muted">Guest</span>}
            </>
          ) : (
            <span className="flex grow items-center gap-2 text-[16px] font-bold text-primary">
              <PlusIcon />
              Pick a player
            </span>
          )}
        </button>
      }
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setFilter("");
          setProblem(null);
        }
        setOpen(next);
      }}
      title="Pick a player"
      description={label}
      onOpenAutoFocus={(event) => {
        event.preventDefault();
        filterRef.current?.focus();
      }}
    >
      <div className="flex flex-col gap-4">
        <input
          ref={filterRef}
          value={filter}
          onChange={(event) => {
            setFilter(event.target.value);
          }}
          aria-label="Find a player"
          placeholder="Find a player"
          autoComplete="off"
          className="min-h-12 rounded-xl border border-line bg-bg px-4 text-[17px] text-ink placeholder:text-muted"
        />
        <ul className="flex max-h-[40dvh] flex-col overflow-y-auto rounded-2xl border border-line" aria-label="Players">
          {shown.map((player) => {
            const busy = taken.has(player.id);
            return (
              <li key={player.id} className="border-b border-line last:border-b-0">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    choose(player.id);
                  }}
                  className="flex min-h-14 w-full cursor-pointer items-center gap-3 px-3 text-left disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Avatar name={player.display_name} photoUrl={player.avatar_url} size="sm" />
                  <span className="min-w-0 grow truncate text-[16px] font-bold">
                    {player.display_name}
                    {player.is_me && <span className="font-normal text-muted"> (you)</span>}
                  </span>
                  <span className="text-[13px] text-muted">{busy ? "In this game" : player.is_guest ? "Guest" : ""}</span>
                </button>
              </li>
            );
          })}
          {shown.length === 0 && <li className="p-4 text-muted">Nobody called that yet. Add them as a guest below.</li>}
        </ul>
        {selected && (
          <button
            type="button"
            className={buttonClass("quiet")}
            onClick={() => {
              choose(null);
            }}
          >
            Leave this spot empty
          </button>
        )}

        <form className="flex flex-col gap-2 border-t border-line pt-4" onSubmit={(event) => void addGuest(event)} noValidate>
          <label className="flex flex-col gap-2">
            <span className="text-[15px] font-bold">Add a guest</span>
            <span className="text-[14px] text-muted">
              Someone who isn't on Popshot. Their games count like anyone else's.
            </span>
            <input
              value={guestName}
              onChange={(event) => {
                setGuestName(event.target.value);
              }}
              maxLength={NAME_MAX}
              autoComplete="off"
              placeholder="Their name"
              className="min-h-12 rounded-xl border border-line bg-bg px-4 text-[17px] text-ink placeholder:text-muted"
            />
          </label>
          <p role="alert" className="text-[15px] text-warn empty:hidden">
            {problem}
          </p>
          <button type="submit" className={buttonClass("primary")} disabled={saving}>
            <PlusIcon />
            {saving ? "Adding…" : "Add guest"}
          </button>
        </form>
      </div>
    </Sheet>
  );
}
