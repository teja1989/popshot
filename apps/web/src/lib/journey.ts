// Your journey: the shapes from the API (routes/journey.py), the words the Journey tab uses,
// and the day's tip. Every word here is checked by journey.test.ts: encouraging, never
// shaming, no rankings, no he or she.

export const FEATURE = "you.journey";

export const STORY_LIMITS = { origin: 800, strengths: 500, gaps: 500, goal: 300 } as const;
export const MAX_TAGS = 4;
export const NOTE_MAX = 200;

export interface Story {
  id: string;
  created_at: string;
  origin: string;
  strengths: string;
  gaps: string;
  goal: string;
  tag_strengths: string[];
  tag_gaps: string[];
  tags_source: "player" | "rules" | "ai";
}

export interface JourneySettings {
  ai_consent: boolean;
  onboarding: "new" | "skipped" | "done";
}

export interface LearningNote {
  id: string;
  noted_on: string;
  body: string;
  skill: string | null;
  created_at: string;
}

export interface Journey {
  story: Story | null;
  history: Story[];
  settings: JourneySettings;
  notes: LearningNote[];
  learning_days: number;
}

export interface StoryDraft {
  origin: string;
  strengths: string;
  gaps: string;
  goal: string;
  tag_strengths: string[];
  tag_gaps: string[];
}

// The four questions, in order.
export const QUESTIONS: readonly { key: keyof typeof STORY_LIMITS; label: string; hint: string }[] = [
  {
    key: "origin",
    label: "How did you get into pickleball?",
    hint: "When you started, who got you playing, what keeps you coming back.",
  },
  {
    key: "strengths",
    label: "What are you good at?",
    hint: "The shots and moments where you feel at home.",
  },
  {
    key: "gaps",
    label: "What would you like to get better at?",
    hint: "The shot that sometimes lets you down, or the part of the game you want to grow.",
  },
  {
    key: "goal",
    label: "A goal for the next month",
    hint: "Something small and yours. Like winning more dink rallies.",
  },
];

export const COPY = {
  title: "Your journey",
  motto: "Every day on court is a lesson. Nobody has it all figured out; everybody's learning.",
  learningDays: (days: number) => (days === 1 ? "1 learning day" : `${String(days)} learning days`),
  learningDaysHint: "A day you reflected on a game, noted something you learned or worked on your story.",
  todayHeading: "Today's one thing",
  noteHeading: "What did you learn today?",
  notePlaceholder: "Soft hands on the reset. Watched the ball onto the paddle.",
  storyHeading: "Your story",
  storyEmpty: "Tell us where your game is today. It shapes your tips now and your check-ins later.",
  storyStart: "Tell your story",
  storyEdit: "Update your story",
  storySheetDescription: "In your own words. Only you can see it, and every version is kept so you can look back.",
  readAs: "Skills you named",
  checkinsHeading: "Check-ins",
  checkinsSoon:
    "Every two weeks, a look at how your game is growing. Your first one arrives two weeks after you start.",
  earlier: (n: number) => (n === 1 ? "1 earlier version" : `${String(n)} earlier versions`),
  promptTitle: "What's your pickleball story?",
  promptBody: "A few lines about your game: how you started, what you love, what you're working on. Only you see it.",
  promptStart: "Tell your story",
  promptLater: "Not now",
  off: "Your journey isn't switched on for you yet. It's coming soon.",
} as const;

export interface Tip {
  // A skill from the focus list, or null for a tip for everyone.
  skill: string | null;
  text: string;
}

// Two for each skill on the focus list, and some for everyone. Short, kind and practical.
export const TIPS: readonly Tip[] = [
  {
    skill: "serve_consistency",
    text: "Pick one serve and own it: same toss, same spot, every time. Deep and in beats fast and out.",
  },
  { skill: "serve_consistency", text: "Aim for the middle third of the box. A little margin is a lot of confidence." },
  { skill: "return_of_serve", text: "Return deep and a little high. It buys you the time to get to the kitchen." },
  {
    skill: "return_of_serve",
    text: "Start a step back from the baseline for returns. Moving forward into the ball is easier than backing up.",
  },
  {
    skill: "getting_to_kitchen",
    text: "After your return, walk in, and split-step as they hit. Arriving balanced matters more than arriving fast.",
  },
  {
    skill: "getting_to_kitchen",
    text: "If you can't reach the line yet, stop and split-step anyway. Then keep moving in on the next ball.",
  },
  {
    skill: "third_shot_drop",
    text: "Lift the drop from low to high with a firm wrist. Let the arc do the work, not the swing.",
  },
  {
    skill: "third_shot_drop",
    text: "Aim the drop at the backhand of the player who's further back. A good drop only needs to be unattackable.",
  },
  { skill: "third_shot_drive", text: "Drive when the ball sits up. Keep it low over the net and follow it in." },
  {
    skill: "third_shot_drive",
    text: "Pair the drive with a drop. Hitting one then the other keeps the other side guessing.",
  },
  { skill: "dinking_patience", text: "Count your dinks today. Ten in a row, cross-court, then see what opens up." },
  { skill: "dinking_patience", text: "Dink to space, not to the player. Make them move, then wait for the high one." },
  {
    skill: "kitchen_positioning",
    text: "Toes near the line, paddle up in front. Move with your partner like you're joined by a rope.",
  },
  {
    skill: "kitchen_positioning",
    text: "Shade toward the middle when the ball's cross-court. Most points end down the middle.",
  },
  {
    skill: "speedups_counters",
    text: "Speed up only from a ball above the net, aimed at the shoulder on the paddle side.",
  },
  {
    skill: "speedups_counters",
    text: "To counter, keep your paddle up and the swing short. Block it back rather than swinging big.",
  },
  { skill: "hand_battles", text: "Short backswing, firm wrist, paddle in front. Fast hands come from a small motion." },
  {
    skill: "hand_battles",
    text: "Reset your paddle to the middle after every volley. It's where the next ball is coming.",
  },
  {
    skill: "transition_resets",
    text: "In the middle of the court, aim to land the ball in the kitchen. Soft beats fancy there.",
  },
  {
    skill: "transition_resets",
    text: "Stop and split-step before each ball in the transition zone, then take one more step in.",
  },
  {
    skill: "reset_under_pressure",
    text: "Under pressure, open the paddle face and absorb. A soft reset turns their attack into a dink rally.",
  },
  { skill: "reset_under_pressure", text: "Breathe out as you reset. A loose grip gives a softer ball." },
  {
    skill: "put_aways",
    text: "Put it away at the feet or through the middle. Down is good; angled and down is better.",
  },
  { skill: "put_aways", text: "Wait for the ball that's clearly high. Patience makes the put-away easy." },
  {
    skill: "lobs_overheads",
    text: "Lob over the backhand shoulder, and only when they're leaning in. Surprise is the whole shot.",
  },
  {
    skill: "lobs_overheads",
    text: "On an overhead, turn sideways and point at the ball with your free hand. Then hit through it.",
  },
  { skill: "poaching", text: "Tell your partner before you poach, then commit fully. A half poach helps nobody." },
  { skill: "poaching", text: "Poach a ball that floats to the middle. Then cover the space your partner leaves open." },
  {
    skill: "backhand",
    text: "Lead with the elbow on backhand dinks and keep the paddle face steady. Calm and compact.",
  },
  {
    skill: "backhand",
    text: "Try ten minutes of backhand-only dinks with a friend. Repetition builds trust in the shot.",
  },
  {
    skill: "spin_variety",
    text: "Add a little topspin to dinks by brushing up the back of the ball. It dips at their feet.",
  },
  { skill: "spin_variety", text: "Mix one slice into each rally. A change of pace is a quiet way to win a point." },
  { skill: "footwork", text: "Split-step every time the other side hits. Light feet, then move to the ball." },
  { skill: "footwork", text: "Take small steps to set up before you hit. Most mis-hits start in the feet." },
  {
    skill: "court_coverage",
    text: "Move as a pair: you both slide toward the ball, together. The gap that's left is the safe one.",
  },
  { skill: "court_coverage", text: "Call 'mine' or 'yours' early. Clear calls cover more court than fast legs." },
  {
    skill: "fitness_stamina",
    text: "Warm up for five minutes before you play: easy dinks, then volleys, then a few serves.",
  },
  {
    skill: "fitness_stamina",
    text: "Sip water between games, not just at the end. Your legs will thank you in game three.",
  },
  {
    skill: "partner_communication",
    text: "Say one kind thing to your partner after a lost point. It resets you both.",
  },
  {
    skill: "partner_communication",
    text: "Agree before the game who takes the middle. One decision saves a dozen collisions.",
  },
  {
    skill: "shot_selection",
    text: "When in doubt, dink. Attack only the ball you'd happily hit ten times out of ten.",
  },
  {
    skill: "shot_selection",
    text: "Ask yourself after each point: was there a safer shot that still kept the pressure on?",
  },
  {
    skill: "staying_calm",
    text: "After an error, take one slow breath and look at your strings. Then play the next point fresh.",
  },
  { skill: "staying_calm", text: "Pick a word for resetting, like 'next'. Saying it helps you let a point go." },
  { skill: null, text: "Notice one thing that went well today. Growth is easier to see when you look for it." },
  { skill: null, text: "Play one game today just for the long rallies. Keeping the ball in play teaches a lot." },
  { skill: null, text: "Watch the ball onto your paddle. The quietest habit makes the cleanest shots." },
  { skill: null, text: "Ask someone you enjoy playing with what they work on. Everyone has something." },
  { skill: null, text: "Ready position between shots: paddle up, knees soft, weight forward." },
  { skill: null, text: "Celebrate a good rally, whoever wins it. It's what keeps the game fun." },
];

// For everyone, if somehow nothing else fits.
const GENERAL: Tip = {
  skill: null,
  text: "Watch the ball onto your paddle. The quietest habit makes the cleanest shots.",
};

function dayNumber(date: Date): number {
  return Math.floor(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / 86_400_000);
}

/**
 * The day's tip: for a skill you want to get better at when you've named some, otherwise one
 * for everyone. The same all day, and it moves on each day.
 */
export function tipFor(skills: readonly string[], date: Date): Tip {
  const yours = TIPS.filter((tip) => tip.skill !== null && skills.includes(tip.skill));
  const pool = yours.length > 0 ? yours : TIPS.filter((tip) => tip.skill === null);
  const day = dayNumber(date);
  // The general tips are never empty, so there's always one to give.
  return pool[((day % pool.length) + pool.length) % pool.length] ?? GENERAL;
}

/** The skills a tip should help with: what your story says, else your focus list. */
export function workingOn(story: Story | null, improve: readonly string[]): string[] {
  return story && story.tag_gaps.length > 0 ? [...story.tag_gaps] : [...improve];
}

/** Your local date as YYYY-MM-DD, for a note you write today. */
export function localDate(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${String(date.getFullYear())}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** Whether to ask for your story: switched on, no story yet, and you haven't said "not now". */
export function shouldAskForStory(journey: Journey | null): boolean {
  return journey !== null && journey.story === null && journey.settings.onboarding === "new";
}

export function emptyDraft(story: Story | null): StoryDraft {
  return {
    origin: story?.origin ?? "",
    strengths: story?.strengths ?? "",
    gaps: story?.gaps ?? "",
    goal: story?.goal ?? "",
    tag_strengths: story ? [...story.tag_strengths] : [],
    tag_gaps: story ? [...story.tag_gaps] : [],
  };
}

export function hasWords(draft: StoryDraft): boolean {
  return [draft.origin, draft.strengths, draft.gaps, draft.goal].some((text) => text.trim() !== "");
}
