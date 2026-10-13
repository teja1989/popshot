// One option in a segmented control: a visually hidden radio inside a <label>. Wrap the
// options in `segmentTrack`. Classes only, like button.ts.

export const segmentTrack = "grid gap-1 rounded-xl bg-chip p-1";

export const segmentOption =
  "flex min-h-11 cursor-pointer items-center justify-center rounded-[10px] px-3 text-body font-bold text-muted " +
  "has-[:checked]:bg-surface has-[:checked]:text-ink has-[:checked]:shadow-sm " +
  "has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-primary";
