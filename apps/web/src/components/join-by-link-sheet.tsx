"use client";

import { useRouter } from "next/navigation";
import { useRef, useState, type ReactNode, type SubmitEvent } from "react";

import { INVITE_PATH, tokenFromPasted } from "@/lib/invites";

import { buttonClass } from "./ui/button";
import { Sheet } from "./ui/sheet";

/**
 * Paste the invite link a lead sent you (or just its code) and go to the join screen. Only
 * the code is taken from what you paste; the pasted address itself is never opened.
 */
export function JoinByLinkSheet({ trigger }: { trigger: ReactNode }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    event.stopPropagation();
    const token = tokenFromPasted(value);
    if (!token) {
      setProblem("That doesn't look like a Popshot invite link. Paste the whole link your lead sent.");
      inputRef.current?.focus();
      return;
    }
    setOpen(false);
    setValue("");
    router.push(`${INVITE_PATH}#${token}`);
  }

  return (
    <Sheet
      fullOnPhone
      trigger={trigger}
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setValue("");
          setProblem(null);
        }
        setOpen(next);
      }}
      title="Join with an invite link"
      description="Paste the link a group's lead or co-lead sent you."
      onOpenAutoFocus={(event) => {
        event.preventDefault();
        inputRef.current?.focus();
      }}
    >
      <form className="flex flex-col gap-3" onSubmit={submit} noValidate>
        <label className="flex flex-col gap-2">
          <span className="text-body font-bold">Invite link</span>
          <input
            ref={inputRef}
            value={value}
            onChange={(event) => {
              setValue(event.target.value);
              setProblem(null);
            }}
            inputMode="url"
            autoComplete="off"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            enterKeyHint="go"
            placeholder="https://…/join#…"
            aria-invalid={problem ? true : undefined}
            className="min-h-12 rounded-xl border border-line bg-bg px-4 text-field text-ink placeholder:text-muted"
          />
        </label>
        <p role="alert" className="text-body text-warn empty:hidden">
          {problem}
        </p>
        <button type="submit" className={buttonClass("primary", "h-14")}>
          Open invite
        </button>
        <p className="text-small text-muted">
          You&apos;ll see the group&apos;s name before you ask to join, and its lead approves you.
        </p>
      </form>
    </Sheet>
  );
}
