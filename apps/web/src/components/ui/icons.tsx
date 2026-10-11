// Small stroke icons. Decorative: they always sit next to text that says the same thing.

const stroke = {
  fill: "none",
  stroke: "currentColor",
  strokeLinecap: "round",
  strokeLinejoin: "round",
} as const;

export function ArrowIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <path d="M4 9h10M10 5l4 4-4 4" strokeWidth="2" {...stroke} />
    </svg>
  );
}

export function BackIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <path d="M11 4L6 9l5 5" strokeWidth="2" {...stroke} />
    </svg>
  );
}

export function PlusIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <path d="M9 3.5v11M3.5 9h11" strokeWidth="2.4" {...stroke} />
    </svg>
  );
}

export function ChevronIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M6 4l4 4-4 4" strokeWidth="2" {...stroke} />
    </svg>
  );
}

export function CloseIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <path d="M4.5 4.5l9 9M13.5 4.5l-9 9" strokeWidth="2" {...stroke} />
    </svg>
  );
}

export function LockIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
      <rect x="2.5" y="6" width="9" height="6.5" rx="1.5" strokeWidth="1.5" {...stroke} />
      <path d="M4.5 6V4.5a2.5 2.5 0 0 1 5 0V6" strokeWidth="1.5" {...stroke} />
    </svg>
  );
}
