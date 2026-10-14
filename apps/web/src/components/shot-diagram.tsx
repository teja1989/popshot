import {
  ACTOR_LABEL,
  actorAt,
  ballAtTime,
  COURT_LENGTH,
  COURT_WIDTH,
  FLIGHT_LABEL,
  isNear,
  KITCHEN,
  NET_Y,
  POST_OUTSIDE,
  type Scene,
} from "@/lib/shot-scene";

// Feet of space around the court, so players standing outside the lines still show.
const MARGIN = 4;
const VIEW = `${String(-MARGIN)} ${String(-MARGIN)} ${String(COURT_WIDTH + 2 * MARGIN)} ${String(COURT_LENGTH + 2 * MARGIN)}`;

// The near baseline at the bottom.
const sy = (y: number) => COURT_LENGTH - y;

/**
 * A shot seen from above: the court, every flight numbered in order, and the players and ball
 * at time t. Used where 3D isn't available or motion is reduced, and in the admin editor.
 */
export function ShotDiagram({ scene, t, className = "" }: { scene: Scene; t: number; className?: string }) {
  const ball = ballAtTime(scene, t);
  const shots = scene.flights.map((f) => FLIGHT_LABEL[f.kind]).join(", ");
  return (
    <svg
      viewBox={VIEW}
      className={className}
      role="img"
      aria-label={`Court from above. ${scene.flights.length === 0 ? "No shots yet." : `Shots in order: ${shots}.`}`}
    >
      <rect x={0} y={0} width={COURT_WIDTH} height={COURT_LENGTH} className="fill-surface" />
      <rect x={0} y={sy(NET_Y + KITCHEN)} width={COURT_WIDTH} height={KITCHEN * 2} className="fill-primary/10" />
      {scene.zones.map((z, i) => (
        <g key={`zone-${String(i)}`}>
          <rect x={z.x0} y={sy(z.y1)} width={z.x1 - z.x0} height={z.y1 - z.y0} className="fill-ball/30" />
          {z.label && (
            <text
              x={(z.x0 + z.x1) / 2}
              y={sy((z.y0 + z.y1) / 2)}
              textAnchor="middle"
              dominantBaseline="middle"
              className="fill-ink text-[1.2px] font-bold"
            >
              {z.label}
            </text>
          )}
        </g>
      ))}
      <g className="fill-none stroke-primary" strokeWidth={0.2}>
        <rect x={0} y={0} width={COURT_WIDTH} height={COURT_LENGTH} />
        <path d={`M0 ${String(sy(NET_Y - KITCHEN))}H${String(COURT_WIDTH)}`} />
        <path d={`M0 ${String(sy(NET_Y + KITCHEN))}H${String(COURT_WIDTH)}`} />
        <path d={`M${String(COURT_WIDTH / 2)} 0V${String(sy(NET_Y + KITCHEN))}`} />
        <path d={`M${String(COURT_WIDTH / 2)} ${String(sy(NET_Y - KITCHEN))}V${String(COURT_LENGTH)}`} />
      </g>
      <path
        d={`M${String(-POST_OUTSIDE)} ${String(sy(NET_Y))}H${String(COURT_WIDTH + POST_OUTSIDE)}`}
        className="stroke-ink"
        strokeWidth={0.35}
      />
      {scene.flights.map((f, i) => {
        const current = ball?.flight === i;
        const midX = (f.start.x + f.end.x) / 2;
        const midY = sy((f.start.y + f.end.y) / 2);
        return (
          <g key={`flight-${String(i)}`} className={current ? "opacity-100" : "opacity-60"}>
            <path
              d={`M${String(f.start.x)} ${String(sy(f.start.y))}L${String(f.end.x)} ${String(sy(f.end.y))}`}
              className="fill-none stroke-ink"
              strokeWidth={current ? 0.25 : 0.15}
              strokeDasharray="0.6 0.4"
            />
            {f.end.z === 0 && (
              <path
                d={`M${String(f.end.x - 0.5)} ${String(sy(f.end.y) - 0.5)}l1 1m0 -1l-1 1`}
                className="stroke-ink"
                strokeWidth={0.2}
              />
            )}
            <circle
              cx={midX}
              cy={midY}
              r={0.9}
              className={current ? "fill-ink" : "fill-chip stroke-line"}
              strokeWidth={0.1}
            />
            <text
              x={midX}
              y={midY}
              textAnchor="middle"
              dominantBaseline="central"
              className={`text-[1.1px] font-bold ${current ? "fill-bg" : "fill-ink"}`}
            >
              {i + 1}
            </text>
          </g>
        );
      })}
      {scene.actors.map((actor) => {
        const pose = actorAt(actor, t);
        const near = isNear(actor.id);
        return (
          <g key={actor.id}>
            <circle cx={pose.x} cy={sy(pose.y)} r={0.9} className={near ? "fill-primary" : "fill-muted"} />
            <text
              x={pose.x}
              y={sy(pose.y) + (near ? 2.2 : -1.6)}
              textAnchor="middle"
              className="fill-ink text-[1.2px] font-bold"
            >
              {ACTOR_LABEL[actor.id]}
            </text>
          </g>
        );
      })}
      {ball && (
        <circle
          cx={ball.at.x}
          cy={sy(ball.at.y)}
          // Higher looks bigger from above.
          r={0.4 + Math.min(ball.at.z, 15) * 0.05}
          className="fill-ball stroke-ink"
          strokeWidth={0.08}
        />
      )}
    </svg>
  );
}
