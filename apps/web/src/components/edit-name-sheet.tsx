"use client";

import { useRef, useState, type SubmitEvent } from "react";

import { apiPatch, ApiError } from "@/lib/api-client";
import { NAME_MAX } from "@/lib/games";

import { useAuth, useSignedIn, type Me } from "./auth";
import { buttonClass } from "./ui/button";
import { Sheet } from "./ui/sheet";

/** Change the name your crew sees. It stays when you sign in again. */
export function EditNameSheet() {
  const { me, user } = useSignedIn();
  const { updateMe } = useAuth();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(me?.display_name ?? "");
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    event.stopPropagation();
    if (!name.trim()) {
      setProblem("Your name can't be empty.");
      inputRef.current?.focus();
      return;
    }
    setSaving(true);
    setProblem(null);
    try {
      updateMe(await apiPatch<Me>(user, "/v1/me", { display_name: name }));
      setOpen(false);
    } catch (error) {
      setProblem(
        error instanceof ApiError && error.status === 422
          ? "That name won't work. Use letters, numbers, spaces and punctuation."
          : "We couldn't save your name just now. Try again in a moment.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Sheet
      trigger={
        <button type="button" className={buttonClass("quiet", "min-h-11 px-4 text-body")}>
          Edit name
        </button>
      }
      open={open}
      onOpenChange={(next) => {
        if (next) {
          setName(me?.display_name ?? "");
          setProblem(null);
        }
        setOpen(next);
      }}
      title="Your name"
      description="This is what your crew sees on games and the Crew tab, in every group you're in."
      onOpenAutoFocus={(event) => {
        event.preventDefault();
        inputRef.current?.select();
      }}
    >
      <form className="flex flex-col gap-4" onSubmit={(event) => void submit(event)} noValidate>
        <label className="flex flex-col gap-2">
          <span className="text-body font-bold">Name</span>
          <input
            ref={inputRef}
            value={name}
            onChange={(event) => {
              setName(event.target.value);
            }}
            maxLength={NAME_MAX}
            autoComplete="nickname"
            aria-invalid={problem ? true : undefined}
            className="min-h-12 rounded-xl border border-line bg-bg px-4 text-field text-ink"
          />
        </label>
        <p role="alert" className="text-body text-warn empty:hidden">
          {problem}
        </p>
        <button type="submit" className={buttonClass("primary", "h-14 w-full")} disabled={saving}>
          {saving ? "Saving…" : "Save name"}
        </button>
      </form>
    </Sheet>
  );
}
