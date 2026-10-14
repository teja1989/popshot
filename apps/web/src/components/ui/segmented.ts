// One option in a segmented control: a visually hidden radio inside a <label>. Wrap the
// options in `segmentTrack`. Classes only, like button.ts.

export const segmentTrack = "grid gap-1 rounded-full bg-surface-high p-1";

export const segmentOption =
  "flex min-h-11 cursor-pointer items-center justify-center rounded-full px-3 text-body font-bold text-muted " +
  "has-[:checked]:bg-secondary-container has-[:checked]:text-on-secondary-container " +
  // The chosen option gets a check, as in Material 3. Its alt text is empty: the radio
  // already says it's selected.
  "has-[:checked]:before:mr-1.5 has-[:checked]:before:content-['✓'_/_''] " +
  "has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-primary";
