import { Fragment } from "react";

import { courtMapsUrl, inOrder, type Court } from "@/lib/courts";
import { usualLine, type CrewProfile } from "@/lib/crew-profile";

/** A crew's about, usual times and (for members) its saved courts, default first. Nothing when
 *  none is set. Invite previews have no courts. */
export function CrewProfileSummary({
  profile,
  onHero = false,
  courts = [],
}: {
  profile: Partial<CrewProfile>;
  onHero?: boolean;
  courts?: readonly Court[];
}) {
  const usual = usualLine({ usual_days: profile.usual_days ?? [], usual_times: profile.usual_times ?? [] });
  if (!profile.about && !usual && courts.length === 0) {
    return null;
  }
  const muted = onHero ? "text-on-hero-muted" : "text-muted";
  return (
    <div className="flex flex-col gap-1">
      {profile.about && <p className="text-lead leading-snug break-words">{profile.about}</p>}
      {usual && <p className={`text-body font-bold ${muted}`}>{usual}</p>}
      {courts.length > 0 && (
        <p className={`text-body ${muted} break-words`}>
          Plays at{" "}
          {inOrder(courts).map((court, index) => {
            const link = courtMapsUrl(court);
            return (
              <Fragment key={court.id}>
                {index > 0 && ", "}
                <span className="font-bold">{court.label}</span>
                {link && (
                  <>
                    {" "}
                    <a
                      href={link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-bold text-primary"
                      aria-label={`Open ${court.label} in Maps`}
                    >
                      (Maps ↗)
                    </a>
                  </>
                )}
              </Fragment>
            );
          })}
        </p>
      )}
    </div>
  );
}
