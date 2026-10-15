import { describe, expect, it } from "vitest";

import { hasMalformedId } from "./app-paths";

const A = "0b6f2a4e-1c3d-4e5f-8a9b-0c1d2e3f4a5b";
const B = "9e8d7c6b-5a49-4382-9172-6b5a49382716";

describe("addresses with IDs", () => {
  it.each([
    `/groups/${A}`,
    `/groups/${A}/log`,
    `/groups/${A}/settings`,
    `/groups/${A}/members`,
    `/groups/${A}/events/new`,
    `/groups/${A}/events/${B}`,
    `/groups/${A}/nights/${B}`,
    `/groups/${A}/recaps/${B}`,
    `/groups/${A}/matches/${B}/edit`,
    `/you/journey/checkins/${A}`,
    `/admin/crews/${A}`,
    `/admin/people/${A}/`,
  ])("are fine when every ID is one: %s", (path) => {
    expect(hasMalformedId(path)).toBe(false);
  });

  it.each([
    "/groups/not-a-real-id",
    "/groups/not-a-real-id/log",
    `/groups/${A.toUpperCase()}`,
    `/groups/${A}/events/old`,
    `/groups/${A}/nights/42`,
    `/groups/${A}/recaps/latest`,
    `/groups/${A}/matches/x/edit`,
    `/groups/x/matches/${B}/edit`,
    "/you/journey/checkins/abc",
    "/admin/crews/1",
    `/admin/people/${A}x`,
  ])("are a 404 when an ID isn't one: %s", (path) => {
    expect(hasMalformedId(path)).toBe(true);
  });

  it.each([
    "/",
    "/play",
    "/crew",
    "/you",
    "/you/journey",
    "/more",
    "/admin",
    "/admin/funnel",
    "/join",
    "/r/abc",
    "/groups",
  ])("leave every other address to the router: %s", (path) => {
    expect(hasMalformedId(path)).toBe(false);
  });
});
