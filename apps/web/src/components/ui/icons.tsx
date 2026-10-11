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

export function StopwatchIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
      <circle cx="11" cy="12.5" r="7" strokeWidth="1.8" {...stroke} />
      <path d="M11 12.5V9M9 2.5h4M16.5 6l1.2-1.2" strokeWidth="1.8" {...stroke} />
    </svg>
  );
}

export function HandshakeIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
      <circle cx="11" cy="11" r="8" strokeWidth="1.8" {...stroke} />
      <path d="M7.5 11.2l2.4 2.4 4.6-4.8" strokeWidth="1.8" {...stroke} />
    </svg>
  );
}

export function PrivateIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
      <rect x="4.5" y="9.5" width="13" height="9" rx="2" strokeWidth="1.8" {...stroke} />
      <path d="M7.5 9.5V7a3.5 3.5 0 0 1 7 0v2.5" strokeWidth="1.8" {...stroke} />
    </svg>
  );
}

export function PauseIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
      <path d="M4.5 3v8M9.5 3v8" strokeWidth="2" {...stroke} />
    </svg>
  );
}

export function PlayIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
      <path d="M4.5 3l6 4-6 4z" strokeWidth="1.6" {...stroke} />
    </svg>
  );
}
