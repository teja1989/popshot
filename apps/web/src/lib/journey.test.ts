import { describe, expect, it } from "vitest";

import { BANNED } from "./copy-rules";
import {
  COPY,
  emptyDraft,
  hasWords,
  localDate,
  QUESTIONS,
  periodLabel,
  shouldAskForStory,
  shouldAskPersonal,
  TIPS,
  tipFor,
  workingOn,
  type Journey,
  type Story,
} from "./journey";

// The focus list (services/api/src/popshot_api/focus.py), which tips are keyed on.
const SKILLS = [
  "serve_consistency",
  "return_of_serve",
  "getting_to_kitchen",
  "third_shot_drop",
  "third_shot_drive",
  "dinking_patience",
  "kitchen_positioning",
  "speedups_counters",
  "hand_battles",
  "transition_resets",
  "reset_under_pressure",
  "put_aways",
  "lobs_overheads",
  "poaching",
  "backhand",
  "spin_variety",
  "footwork",
  "court_coverage",
  "fitness_stamina",
  "partner_communication",
  "shot_selection",
  "staying_calm",
];

function allCopy(): string[] {
  const words: string[] = [];
  for (const value of Object.values(COPY)) {
    words.push(typeof value === "function" ? `${value(1)} ${value(7)}` : value);
  }
  for (const question of QUESTIONS) {
    words.push(question.label, question.hint);
  }
  for (const tip of TIPS) {
    words.push(tip.text);
  }
  return words;
}

const story = (gaps: string[]): Story => ({
  id: "s1",
  created_at: "2026-10-14T10:00:00Z",
  origin: "A friend brought me.",
  strengths: "",
  gaps: "",
  goal: "",
  tag_strengths: [],
  tag_gaps: gaps,
  tags_source: "player",
});

describe("journey words", () => {
  it.each(allCopy())("are kind: %s", (text) => {
    expect(text).not.toMatch(BANNED);
  });

  it("catches what it should", () => {
    for (const text of ["You failed", "Nobody's perfect", "she plays", "your weak backhand", "ranked third"]) {
      expect(text).toMatch(BANNED);
    }
    for (const text of ["the shoulder", "the ball", "help others", "behold"]) {
      expect(text).not.toMatch(BANNED);
    }
  });

  it("has a couple of tips for every skill, and only for known skills", () => {
    for (const skill of SKILLS) {
      expect(TIPS.filter((tip) => tip.skill === skill).length, skill).toBeGreaterThanOrEqual(2);
    }
    for (const tip of TIPS) {
      if (tip.skill !== null) {
        expect(SKILLS).toContain(tip.skill);
      }
      expect(tip.text.length).toBeLessThanOrEqual(140);
    }
    expect(TIPS.filter((tip) => tip.skill === null).length).toBeGreaterThanOrEqual(5);
  });
});

describe("the day's tip", () => {
  const monday = new Date(2026, 9, 12, 8, 0);
  const mondayNight = new Date(2026, 9, 12, 23, 30);
  const tuesday = new Date(2026, 9, 13, 8, 0);

  it("is about a skill you're working on, the same all day, and moves on the next day", () => {
    const tip = tipFor(["backhand"], monday);
    expect(tip.skill).toBe("backhand");
    expect(tipFor(["backhand"], mondayNight)).toEqual(tip);
    expect(tipFor(["backhand"], tuesday).text).not.toBe(tip.text);
    expect(tipFor(["backhand"], tuesday).skill).toBe("backhand");
  });

  it("is for everyone when you've named no skills, or none it knows", () => {
    expect(tipFor([], monday).skill).toBeNull();
    expect(tipFor(["juggling"], monday).skill).toBeNull();
  });

  it("comes from your story, else from your focus list", () => {
    expect(workingOn(story(["footwork"]), ["backhand"])).toEqual(["footwork"]);
    expect(workingOn(story([]), ["backhand"])).toEqual(["backhand"]);
    expect(workingOn(null, [])).toEqual([]);
  });
});

describe("the story", () => {
  const journey = (over: Partial<Journey>): Journey => ({
    story: null,
    history: [],
    settings: { ai_consent: false, onboarding: "new" },
    notes: [],
    learning_days: 0,
    ...over,
  });

  it("is asked for only until you write it or say not now", () => {
    expect(shouldAskForStory(null)).toBe(false);
    expect(shouldAskForStory(journey({}))).toBe(true);
    expect(shouldAskForStory(journey({ settings: { ai_consent: false, onboarding: "skipped" } }))).toBe(false);
    expect(shouldAskForStory(journey({ story: story([]) }))).toBe(false);
  });

  it("starts a draft from the current version, and needs some words", () => {
    const draft = emptyDraft(story(["footwork"]));
    expect(draft.origin).toBe("A friend brought me.");
    expect(draft.tag_gaps).toEqual(["footwork"]);
    expect(hasWords(draft)).toBe(true);
    expect(hasWords({ ...emptyDraft(null), goal: "   " })).toBe(false);
  });

  it("dates a note by your own calendar", () => {
    expect(localDate(new Date(2026, 0, 5, 23, 59))).toBe("2026-01-05");
  });

  it("asks about personal check-ins only with the switch on, no yes yet, and no 'not now' here", () => {
    expect(shouldAskPersonal(true, false, false)).toBe(true);
    expect(shouldAskPersonal(false, false, false)).toBe(false);
    expect(shouldAskPersonal(true, true, false)).toBe(false);
    expect(shouldAskPersonal(true, false, true)).toBe(false);
  });

  it("names Google Gemini in the note, and never says AI", () => {
    expect(COPY.personalNote).toContain("Google Gemini");
    for (const text of allCopy()) {
      expect(text).not.toMatch(/\bAI\b/);
    }
  });

  it("shows the two weeks a check-in covers", () => {
    const label = periodLabel("2026-10-01T09:00:00Z", "2026-10-15T09:00:00Z");
    expect(label).toContain("–");
    expect(label).toMatch(/1/);
    expect(label).toMatch(/15/);
  });
});
