import { usualLine, type CrewProfile } from "@/lib/crew-profile";

/** A crew's about, usual times and (for members) home courts. Nothing when none is set. */
export function CrewProfileSummary({ profile, onHero = false }: { profile: Partial<CrewProfile>; onHero?: boolean }) {
  const usual = usualLine({ usual_days: profile.usual_days ?? [], usual_times: profile.usual_times ?? [] });
  const courts = profile.home_courts ?? [];
  if (!profile.about && !usual && courts.length === 0) {
    return null;
  }
  const muted = onHero ? "text-on-hero-muted" : "text-muted";
  return (
    <div className="flex flex-col gap-1">
      {profile.about && <p className="text-[16px] leading-snug break-words">{profile.about}</p>}
      {usual && <p className={`text-[15px] font-bold ${muted}`}>{usual}</p>}
      {courts.length > 0 && <p className={`text-[15px] ${muted}`}>Plays at {courts.join(", ")}</p>}
    </div>
  );
}
