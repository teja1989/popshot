// The Popshot mark: a court seen from above, with the ball in play.

export function BrandMark({
  className = "",
  onHero = false,
}: {
  className?: string;
  onHero?: boolean;
}) {
  const line = onHero ? "stroke-on-hero" : "stroke-primary";
  return (
    <svg className={className} width="30" height="30" viewBox="0 0 30 30" aria-hidden="true">
      <rect x="1.5" y="1.5" width="27" height="27" rx="6" fill="none" className={line} strokeWidth="2.5" />
      <line x1="15" y1="1.5" x2="15" y2="28.5" className={line} strokeWidth="2.5" />
      <circle cx="21.5" cy="9" r="4" className="fill-ball" />
    </svg>
  );
}

export function Brand({ onHero = false }: { onHero?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <BrandMark onHero={onHero} />
      <span
        className={`text-title font-extrabold tracking-[-0.01em] font-display ${onHero ? "text-on-hero" : ""}`}
      >
        Popshot
      </span>
    </div>
  );
}
