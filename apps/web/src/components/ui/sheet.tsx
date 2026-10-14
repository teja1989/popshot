"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { AnimatePresence, animate, motion, useMotionValue, useReducedMotion, useTransform } from "motion/react";
import { useEffect, useLayoutEffect, useRef, useState, type PointerEvent, type ReactNode } from "react";

import { closesOnRelease } from "@/lib/sheet-drag";

import { CloseIcon } from "./icons";

// A Radix dialog styled as a bottom sheet on phones and a centred card on wider screens.
// Radix handles focus trapping, Escape, returning focus and hiding the rest of the page
// from screen readers. On phones a bottom sheet can also be dragged down to close, by its
// grip or title row (never by its content, so scrolling inside it stays scrolling).

const DESKTOP =
  "sm:inset-x-auto sm:top-1/2 sm:bottom-auto sm:left-1/2 sm:h-auto sm:max-h-[92dvh] sm:w-full sm:max-w-md sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-[28px] sm:border sm:pb-6";

const PANEL = {
  bottom: `fixed inset-x-0 bottom-0 z-50 max-h-[92dvh] overflow-y-auto rounded-t-[28px] border border-line bg-surface px-5 pt-3 pb-8 text-ink shadow-fab sm:pt-5 ${DESKTOP}`,
  full: `fixed inset-0 z-50 h-dvh overflow-y-auto border-line bg-surface px-5 pt-5 pb-8 text-ink ${DESKTOP}`,
};

// Material 3 motion: arriving with a long, soft "emphasized decelerate" ease; leaving
// faster, accelerating away.
const EMPHASIZED = [0.05, 0.7, 0.1, 1] as const;
const ARRIVE = { duration: 0.4, ease: EMPHASIZED };
const SETTLE = { duration: 0.3, ease: EMPHASIZED };
const LEAVE = { duration: 0.22, ease: [0.3, 0, 0.8, 0.15] as const };
// Let go after holding still this long (ms) and it's not a flick.
const FLICK_PAUSE_MS = 100;

// Tailwind's sm breakpoint, where the sheet becomes a centred card.
const WIDE = "(min-width: 40rem)";

function useWide(): boolean {
  const [wide, setWide] = useState(() => window.matchMedia(WIDE).matches);
  useEffect(() => {
    const query = window.matchMedia(WIDE);
    const update = () => {
      setWide(query.matches);
    };
    query.addEventListener("change", update);
    return () => {
      query.removeEventListener("change", update);
    };
  }, []);
  return wide;
}

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
  // sheet would sit under the on-screen keyboard. These don't drag.
  fullOnPhone?: boolean;
  children: ReactNode;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      {trigger !== undefined && <Dialog.Trigger asChild>{trigger}</Dialog.Trigger>}
      <AnimatePresence>
        {open && (
          <Panel
            title={title}
            description={description}
            onOpenAutoFocus={onOpenAutoFocus}
            fullOnPhone={fullOnPhone}
            onClose={() => {
              onOpenChange(false);
            }}
          >
            {children}
          </Panel>
        )}
      </AnimatePresence>
    </Dialog.Root>
  );
}

function Panel({
  title,
  description,
  onOpenAutoFocus,
  fullOnPhone,
  onClose,
  children,
}: {
  title: string;
  description: string;
  onOpenAutoFocus?: (event: Event) => void;
  fullOnPhone: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  const wide = useWide();
  const reduced = useReducedMotion() ?? false;
  const draggable = !fullOnPhone && !wide;
  // A bottom sheet on a phone slides up from the bottom edge and back down when it closes;
  // the others (full-screen sheets, the centred card) fade with a small lift.
  const slides = !fullOnPhone && !wide && !reduced;
  const panel = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState(0);
  // How far down the panel is: it rises into place when it opens, and follows the pointer
  // while dragged.
  const y = useMotionValue(reduced ? 0 : 16);
  const shown = useMotionValue(0);
  // The backdrop fades in as the sheet opens, and out again as it's dragged down.
  const backdrop = useTransform(() => shown.get() * (1 - Math.min(Math.max(y.get(), 0), 320) / 320));
  const drag = useRef<{ pointer: number; startY: number; lastY: number; lastTime: number; speed: number } | null>(null);

  // Start from just below the screen's edge, before the first paint, then rise.
  useLayoutEffect(() => {
    const full = panel.current?.offsetHeight ?? 0;
    setHeight(full);
    if (slides) {
      y.set(full);
    }
    const fade = animate(shown, 1, { duration: reduced ? 0.15 : 0.3, ease: "easeOut" });
    const rise = animate(y, 0, reduced ? { duration: 0 } : ARRIVE);
    return () => {
      fade.stop();
      rise.stop();
    };
  }, [shown, y, reduced, slides]);

  // Dragging, by the grip or the title row (never the content, so scrolling it stays
  // scrolling). Plain pointer events: the panel follows the pointer down only, and on
  // release closes or springs back.
  function down(event: PointerEvent<HTMLDivElement>) {
    if (!draggable || event.button !== 0 || (event.target as Element).closest("button")) {
      return;
    }
    event.currentTarget.setPointerCapture(event.pointerId);
    y.stop();
    drag.current = {
      pointer: event.pointerId,
      startY: event.clientY - y.get(),
      lastY: event.clientY,
      lastTime: event.timeStamp,
      speed: 0,
    };
  }

  function move(event: PointerEvent<HTMLDivElement>) {
    const now = drag.current;
    if (now?.pointer !== event.pointerId) {
      return;
    }
    y.set(Math.max(0, event.clientY - now.startY));
    const elapsed = event.timeStamp - now.lastTime;
    if (elapsed > 0) {
      now.speed = ((event.clientY - now.lastY) / elapsed) * 1000;
    }
    now.lastY = event.clientY;
    now.lastTime = event.timeStamp;
  }

  function up(event: PointerEvent<HTMLDivElement>) {
    const now = drag.current;
    if (now?.pointer !== event.pointerId) {
      return;
    }
    drag.current = null;
    // A pause before letting go is not a flick.
    const speed = event.timeStamp - now.lastTime > FLICK_PAUSE_MS ? 0 : now.speed;
    if (event.type === "pointerup" && closesOnRelease(y.get(), speed)) {
      onClose();
    } else {
      void animate(y, 0, reduced ? { duration: 0 } : SETTLE);
    }
  }

  const dragHandlers = draggable
    ? { onPointerDown: down, onPointerMove: move, onPointerUp: up, onPointerCancel: up }
    : {};

  return (
    // forceMount: Motion, not Radix, decides when they leave, so they can animate out.
    <Dialog.Portal forceMount>
      <motion.div exit={{ opacity: 0 }} transition={LEAVE}>
        <Dialog.Overlay asChild forceMount>
          <motion.div className="fixed inset-0 z-40 bg-ink/45" style={{ opacity: backdrop }} />
        </Dialog.Overlay>
      </motion.div>
      <Dialog.Content asChild forceMount onOpenAutoFocus={onOpenAutoFocus}>
        <motion.div
          ref={panel}
          className={fullOnPhone ? PANEL.full : PANEL.bottom}
          style={{ y }}
          initial={{ opacity: slides ? 1 : 0 }}
          animate={{ opacity: 1 }}
          exit={slides ? { y: height || 600 } : { opacity: 0, y: reduced ? 0 : 16 }}
          transition={slides ? LEAVE : { duration: reduced ? 0.15 : 0.2 }}
        >
          {draggable && (
            // The grip: a visual handle for dragging. Keyboard and screen reader users close
            // with the Close button or Escape, so it isn't a control of its own.
            <div
              aria-hidden="true"
              data-sheet-grip=""
              {...dragHandlers}
              className="-mx-5 flex h-6 cursor-grab touch-none items-center justify-center active:cursor-grabbing"
            >
              <span className="h-1 w-9 rounded-full bg-muted/50" />
            </div>
          )}
          <div {...dragHandlers} className={`flex items-start justify-between gap-4 ${draggable ? "touch-none" : ""}`}>
            <Dialog.Title className="text-title leading-tight font-extrabold tracking-[-0.01em] font-display">
              {title}
            </Dialog.Title>
            <Dialog.Close
              aria-label="Close"
              className="flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-full bg-surface-high text-ink"
            >
              <CloseIcon />
            </Dialog.Close>
          </div>
          <Dialog.Description className="mt-1 text-body text-muted">{description}</Dialog.Description>
          <div className="mt-5">{children}</div>
        </motion.div>
      </Dialog.Content>
    </Dialog.Portal>
  );
}
