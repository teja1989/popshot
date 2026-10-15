// Every ID in a signed-in address is a UUID (a crew, game, meetup, event, recap, check-in or
// person). The proxy turns an address with anything else in those places into a real 404
// before the page renders: once a page has started streaming (it shows a loading outline
// straight away) it can no longer change the status. Each page still checks its own IDs.

const ID = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";

// Each route with IDs in it, where any segment may be an ID ("*") or must be one ("id").
const ROUTES: readonly (readonly string[])[] = [
  ["groups", "id"],
  ["groups", "id", "*"],
  ["groups", "id", "events", "new"],
  ["groups", "id", "events", "id"],
  ["groups", "id", "nights", "id"],
  ["groups", "id", "recaps", "id"],
  ["groups", "id", "matches", "id", "edit"],
  ["you", "journey", "checkins", "id"],
  ["admin", "crews", "id"],
  ["admin", "people", "id"],
];

const ID_PATTERN = new RegExp(`^${ID}$`);

function fits(route: readonly string[], segments: readonly string[], strict: boolean): boolean {
  return (
    route.length === segments.length &&
    route.every((part, i) => {
      const segment = segments[i] ?? "";
      if (part === "id") {
        return strict ? ID_PATTERN.test(segment) : true;
      }
      return part === "*" || part === segment;
    })
  );
}

/**
 * True when the path has the shape of a route with IDs but an ID in it isn't one, such as
 * /groups/not-a-real-id. Paths of any other shape are left to the router.
 */
export function hasMalformedId(pathname: string): boolean {
  const segments = pathname.split("/").filter((s) => s !== "");
  const shaped = ROUTES.filter((route) => fits(route, segments, false));
  return shaped.length > 0 && !shaped.some((route) => fits(route, segments, true));
}
