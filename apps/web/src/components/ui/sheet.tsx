"use client";

import * as Dialog from "@radix-ui/react-dialog";
import type { ReactNode } from "react";

import { CloseIcon } from "./icons";

// A Radix dialog styled as a bottom sheet on phones and a centred card on wider screens.
// Radix handles focus trapping, Escape, returning focus and hiding the rest of the page
// from screen readers.

const DESKTOP =
  "sm:inset-x-auto sm:top-1/2 sm:bottom-auto sm:left-1/2 sm:h-auto sm:max-h-[92dvh] sm:w-full sm:max-w-md sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-3xl sm:border sm:pb-6";

const PANEL = {
  bottom: `fixed inset-x-0 bottom-0 z-50 max-h-[92dvh] animate-sheet-up overflow-y-auto rounded-t-3xl border border-line bg-surface px-5 pt-5 pb-8 text-ink ${DESKTOP}`,
  full: `fixed inset-0 z-50 h-dvh animate-sheet-up overflow-y-auto border-line bg-surface px-5 pt-5 pb-8 text-ink ${DESKTOP}`,
};

export function Sheet({
  trigger,
  open,
  onOpenChange,
  title,
  description,
  onOpenAutoFocus,
  fullOnPhone = false,
  children,
}: {
  // The button that opens the sheet. Radix returns focus to it when the sheet closes.
  // Leave it out for a sheet the page opens itself (say, right after logging a game).
  trigger?: ReactNode;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  onOpenAutoFocus?: (event: Event) => void;
  // Fill the screen on phones, content from the top. For sheets with text fields: a bottom
  // sheet would sit under the on-screen keyboard.
  fullOnPhone?: boolean;
  children: ReactNode;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      {trigger !== undefined && <Dialog.Trigger asChild>{trigger}</Dialog.Trigger>}
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 animate-fade-in bg-ink/45" />
        <Dialog.Content
          onOpenAutoFocus={onOpenAutoFocus}
          className={fullOnPhone ? PANEL.full : PANEL.bottom}
        >
          <div className="flex items-start justify-between gap-4">
            <Dialog.Title className="text-[24px] leading-tight font-extrabold tracking-[-0.01em] [font-stretch:110%]">
              {title}
            </Dialog.Title>
            <Dialog.Close
              aria-label="Close"
              className="flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-full border border-line bg-bg text-ink"
            >
              <CloseIcon />
            </Dialog.Close>
          </div>
          <Dialog.Description className="mt-1 text-[15px] text-muted">{description}</Dialog.Description>
          <div className="mt-5">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
