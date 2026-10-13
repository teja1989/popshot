import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  crewSteps,
  peopleSteps,
  percent,
  SOURCE_LABEL,
  spreadPerActive,
  STAGE_LABEL,
  waitText,
  type Loops,
} from "./admin-funnel";
import { SOURCES } from "./funnel";

describe("the funnel page", () => {
  it("measures weeks 2 and 4 only against crews old enough", () => {
    const steps = crewSteps({
      created: 10,
      second_member: 7,
      first_game: 6,
      activated: 3,
      week_2_eligible: 4,
      played_week_2: 2,
      week_4_eligible: 0,
      played_week_4: 0,
      median_hours_to_first_game: 30,
    });
    expect(steps.map((s) => [s.count, s.of])).toEqual([
      [10, 10],
      [7, 10],
      [6, 10],
      [3, 10],
      [2, 4],
      [0, 0],
    ]);
    expect(peopleSteps({ signed_up: 5, in_crew: 4, played: 2, week_2_eligible: 3, back_week_2: 1 }).at(-1)).toEqual({
      label: "Back in week 2",
      count: 1,
      of: 3,
      note: "of 3 old enough",
    });
  });

  it("draws bars that never overflow or divide by zero", () => {
    expect(percent(3, 4)).toBe(75);
    expect(percent(0, 0)).toBe(0);
    expect(percent(5, 4)).toBe(100);
  });

  it("says how long a first game took, roughly", () => {
    expect(waitText(null)).toBe("no first games yet");
    expect(waitText(0.4)).toBe("under an hour");
    expect(waitText(1)).toBe("about 1 hour");
    expect(waitText(30)).toBe("about 30 hours");
    expect(waitText(80)).toBe("about 3 days");
  });

  it("counts new players per active player from shares, invites and codes", () => {
    const loops: Loops = {
      recaps_shared: 4,
      share_views: 40,
      try_taps: 9,
      recap_signups: 2,
      invite_links: 3,
      link_joins: 5,
      direct_invites: 2,
      direct_accepted: 1,
      invite_signups: 3,
      code_signups: 1,
      active_users: 20,
    };
    expect(spreadPerActive(loops)).toBe("0.30");
    expect(spreadPerActive({ ...loops, active_users: 0 })).toBe("–");
  });

  it("has a label for every source and stage", () => {
    for (const source of SOURCES) {
      expect(SOURCE_LABEL[source]).toBeTruthy();
    }
    // routes/admin_funnel.py's Stage: a stage added there needs a label here.
    const api = readFileSync(
      fileURLToPath(new URL("../../../../services/api/src/popshot_api/routes/admin_funnel.py", import.meta.url)),
      "utf8",
    );
    const stages = [...(/Stage = Literal\[([^\]]*)\]/.exec(api)?.[1] ?? "").matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);
    expect(stages.length).toBeGreaterThan(0);
    expect(new Set(stages)).toEqual(new Set(Object.keys(STAGE_LABEL)));
  });
});
