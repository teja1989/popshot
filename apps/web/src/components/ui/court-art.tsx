// A pickleball court drawn line by line, then the ball drops in. Decorative only.

const lines = [
  // Starts and ends mid-edge, so the seam of the draw-on animation falls on a straight line.
  { d: "M167 6H324a4 4 0 0 1 4 4V190a4 4 0 0 1-4 4H10a4 4 0 0 1-4-4V10a4 4 0 0 1 4-4H167", w: 3, tone: "stroke-primary", delay: "" },
  { d: "M167 6v188", w: 4, tone: "stroke-ink", delay: "[animation-delay:150ms]" },
  { d: "M113 6v188", w: 2, tone: "stroke-primary", delay: "[animation-delay:250ms]" },
  { d: "M221 6v188", w: 2, tone: "stroke-primary", delay: "[animation-delay:250ms]" },
  { d: "M6 100h107", w: 2, tone: "stroke-primary", delay: "[animation-delay:350ms]" },
  { d: "M221 100h107", w: 2, tone: "stroke-primary", delay: "[animation-delay:350ms]" },
];

export function CourtArt({
  className = "",
  rally = false,
}: {
  className?: string;
  // Rally the ball over the net a few times instead of just dropping it in.
  rally?: boolean;
}) {
  return (
    <svg className={className} viewBox="0 0 334 200" aria-hidden="true">
      {lines.map((line) => (
        <path
          key={line.d}
          d={line.d}
          pathLength={1}
          fill="none"
          strokeWidth={line.w}
          className={`court-line animate-court-draw ${line.tone} ${line.delay}`}
        />
      ))}
      {rally ? (
        <g className="animate-rally-x">
          <ellipse
            cx="70"
            cy="128"
            rx="11"
            ry="4"
            className="animate-rally-shadow fill-ink/20 [transform-box:fill-box] [transform-origin:center]"
          />
          <g className="animate-rally-y">
            <circle cx="70" cy="112" r="11" className="fill-ball" />
          </g>
        </g>
      ) : (
        <circle
          cx="262"
          cy="58"
          r="11"
          className="animate-court-ball fill-ball [transform-box:fill-box]"
        />
      )}
    </svg>
  );
}
