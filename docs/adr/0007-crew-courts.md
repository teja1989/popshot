# 0007: One list of crew courts, with a default

- Status: accepted
- Date: 2026-10-15

## Context

A crew described where it plays in three unconnected ways: up to three home courts typed as
text (migration 0022), one court on the map found with Google Places (0035), and a typed venue
on every meetup. Planned features need "where this crew plays" in more places: open crews list
a crew by its court, and meetups and events should offer the crew's usual courts instead of
retyping them.

## Decision

1. **Crew courts** (`crew_courts`, migration 0036): up to 5 per crew, managed by its lead and
   co-leads, read by its active members only.
2. **A court is typed or from Google.** Typed courts need nothing else. A Google court keeps
   only Google's place ID, through `places` (coordinates for at most 30 days, refreshed by the
   job); its name is always the crew's own, because Google's name can't be kept. Picking a
   Google court needs the `courts.places` switch and counts against the Google limits.
3. **Exactly one default** whenever a crew has courts: the first court added, until a lead
   picks another; removing it passes it to the next court. The database holds this.
4. **Everything that needs a place picks from the list**, default first, and can still be
   typed as a one-off: meetups (`play_nights.court_id`) and events now; the open-crews listing
   uses the default, which must be a Google court.
5. **A meetup keeps its venue text.** The court link is a convenience (a Maps link, a quicker
   pick); renaming or removing a court never rewrites past meetups.

## Consequences

- One place to change how courts work, and one picker on the web.
- The old shape is migrated in (the court on the map becomes the default) and kept readable
  through the old fields until the web moves to the new routes; a later migration drops the
  old columns.
- Limits stay small and fixed (5 courts, the existing Google caps), so Google costs can't grow
  with the number of courts.
