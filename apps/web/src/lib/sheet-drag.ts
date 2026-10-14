// When a bottom sheet dragged down by its grip should close (components/ui/sheet.tsx).

// Let go past this far down (px), or flick down faster than this (px/s), and it closes.
export const CLOSE_DISTANCE = 120;
export const CLOSE_SPEED = 500;

/** Whether a drag that ended like this should close the sheet. */
export function closesOnRelease(offsetY: number, velocityY: number): boolean {
  return offsetY > CLOSE_DISTANCE || velocityY > CLOSE_SPEED;
}
