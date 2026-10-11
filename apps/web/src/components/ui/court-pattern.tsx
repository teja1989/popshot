// Faint court lines filling a court-blue block. Decorative; sits behind the content.

export function CourtPattern({ className = "" }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      preserveAspectRatio="xMidYMid slice"
      viewBox="0 0 1200 600"
      className={`pointer-events-none absolute inset-0 -z-10 h-full w-full stroke-hero-line ${className}`}
    >
      <rect x="120" y="70" width="960" height="460" rx="10" fill="none" strokeWidth="3" />
      <path
        d="M600 70v460M440 70v460M760 70v460M120 300h320M760 300h320"
        fill="none"
        strokeWidth="3"
      />
      <path d="M600 70v460" fill="none" strokeWidth="7" />
    </svg>
  );
}
