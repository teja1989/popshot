"use client";

import { useRef, useState, type SubmitEvent } from "react";

import { apiPost, ApiError } from "@/lib/api-client";
import { NAME_MAX, type Player } from "@/lib/games";

import { useSignedIn } from "./auth";
import { Avatar } from "./ui/avatar";
import { buttonClass } from "./ui/button";
import { BackIcon, PlusIcon } from "./ui/icons";
import { Sheet } from "./ui/sheet";

/**
 * One player slot in a team: shows who's picked, and opens a sheet to pick someone or add a
 * guest. On phones the sheet fills the screen and nothing grabs focus on open, so the
 * keyboard only appears when you tap a text field, and adding a guest is its own short step
 * with the field at the top, clear of the keyboard.
 */
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
  const [step, setStep] = useState<"pick" | "guest">("pick");
  const [filter, setFilter] = useState("");
  const [guestName, setGuestName] = useState("");
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const guestRef = useRef<HTMLInputElement>(null);

  const query = filter.trim().toLowerCase();
  const shown = players.filter((p) => p.display_name.toLowerCase().includes(query));

  function reset() {
    setStep("pick");
    setFilter("");
    setGuestName("");
    setProblem(null);
  }

  function choose(playerId: string | null) {
    onPick(playerId);
    setOpen(false);
    reset();
  }

  function startGuest(prefill: string) {
    setGuestName(prefill);
    setProblem(null);
    setStep("guest");
    // After React shows the field. Focusing here opens the keyboard, which is the point.
    requestAnimationFrame(() => guestRef.current?.focus());
  }

  async function addGuest(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    // The sheet renders in a portal, but React still bubbles events through the component
    // tree: without this, submitting here would also submit the log-a-game form around it.
    event.stopPropagation();
    if (!guestName.trim()) {
      setProblem("Type the guest's name.");
      guestRef.current?.focus();
      return;
    }
    setSaving(true);
    setProblem(null);
    try {
      const guest = await apiPost<Player>(user, `/v1/groups/${groupId}/players`, { display_name: guestName });
      onGuestAdded(guest);
      choose(guest.id);
    } catch (error) {
      setProblem(
        error instanceof ApiError && error.status === 422
          ? "That name won't work. Use letters, numbers, spaces and punctuation."
          : error instanceof ApiError && error.detail
            ? error.detail
            : "We couldn't add the guest just now. Try again in a moment.",
      );
      guestRef.current?.focus();
    } finally {
      setSaving(false);
    }
  }

  return (
    <Sheet
      fullOnPhone
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
          reset();
        }
        setOpen(next);
      }}
      title={step === "guest" ? "Add a guest" : "Pick a player"}
      description={step === "guest" ? "Someone who isn't on Popshot. Their games count like anyone else's." : label}
      onOpenAutoFocus={(event) => {
        // Don't focus a text field on open: on a phone that pops the keyboard over the list.
        event.preventDefault();
      }}
    >
      {step === "guest" ? (
        <form className="flex flex-col gap-3" onSubmit={(event) => void addGuest(event)} noValidate>
          <label className="flex flex-col gap-2">
            <span className="text-[15px] font-bold">Guest&apos;s name</span>
            <input
              ref={guestRef}
              value={guestName}
              onChange={(event) => {
                setGuestName(event.target.value);
              }}
              maxLength={NAME_MAX}
              autoComplete="off"
              autoCapitalize="words"
              enterKeyHint="done"
              placeholder="Their name"
              aria-invalid={problem ? true : undefined}
              className="min-h-12 rounded-xl border border-line bg-bg px-4 text-[17px] text-ink placeholder:text-muted"
            />
          </label>
          <p role="alert" className="text-[15px] text-warn empty:hidden">
            {problem}
          </p>
          <button type="submit" className={buttonClass("primary", "h-14")} disabled={saving}>
            <PlusIcon />
            {saving ? "Adding…" : "Add guest"}
          </button>
          <button
            type="button"
            className="flex min-h-11 cursor-pointer items-center gap-1.5 self-start font-bold text-primary"
            onClick={() => {
              setStep("pick");
              setProblem(null);
            }}
          >
            <BackIcon />
            Back to players
          </button>
        </form>
      ) : (
        <div className="flex flex-col gap-3">
          <button
            type="button"
            className={buttonClass("quiet", "h-12 justify-start")}
            onClick={() => {
              startGuest(filter.trim());
            }}
          >
            <PlusIcon />
            Add a guest
          </button>
          <input
            value={filter}
            onChange={(event) => {
              setFilter(event.target.value);
            }}
            type="search"
            aria-label="Find a player"
            placeholder="Find a player"
            autoComplete="off"
            enterKeyHint="search"
            className="min-h-12 rounded-xl border border-line bg-bg px-4 text-[17px] text-ink placeholder:text-muted"
          />
          <ul className="flex flex-col rounded-2xl border border-line" aria-label="Players">
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
            {shown.length === 0 && (
              <li className="flex flex-col items-start gap-2 p-4">
                <span className="text-muted">Nobody called &ldquo;{filter.trim()}&rdquo; yet.</span>
                <button
                  type="button"
                  className="min-h-11 cursor-pointer font-bold text-primary"
                  onClick={() => {
                    startGuest(filter.trim());
                  }}
                >
                  Add &ldquo;{filter.trim()}&rdquo; as a guest
                </button>
              </li>
            )}
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
        </div>
      )}
    </Sheet>
  );
}
