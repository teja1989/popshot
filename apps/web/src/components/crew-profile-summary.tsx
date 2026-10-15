import { usualLine, type CrewProfile } from "@/lib/crew-profile";
import { mapsUrl } from "@/lib/places";

/** The crew's court on the map, for members, when the courts.places switch is on. */
export interface MapCourt {
  name: string;
  googleId: string | null | undefined;
}

/** A crew's about, usual times and (for members) home courts. Nothing when none is set. */
export function CrewProfileSummary({
  profile,
  onHero = false,
  court = null,
}: {
  profile: Partial<CrewProfile>;
  onHero?: boolean;
  court?: MapCourt | null;
}) {
  const usual = usualLine({ usual_days: profile.usual_days ?? [], usual_times: profile.usual_times ?? [] });
  const courts = profile.home_courts ?? [];
  if (!profile.about && !usual && courts.length === 0 && !court) {
    return null;
  }
  const muted = onHero ? "text-on-hero-muted" : "text-muted";
  const link = court ? mapsUrl(court.googleId, court.name) : null;
  return (
    <div className="flex flex-col gap-1">
      {profile.about && <p className="text-lead leading-snug break-words">{profile.about}</p>}
      {usual && <p className={`text-body font-bold ${muted}`}>{usual}</p>}
      {court && (
        <p className={`text-body ${muted} break-words`}>
          Home court: <span className="font-bold">{court.name}</span>
          {link && (
            <>
              {" · "}
              <a href={link} target="_blank" rel="noopener noreferrer" className="font-bold text-primary">
                Open in Maps ↗
              </a>
            </>
          )}
        </p>
      )}
      {courts.length > 0 && <p className={`text-body ${muted}`}>Plays at {courts.join(", ")}</p>}
    </div>
  );
}
