// Private focus areas and post-game reflections. Shapes match the API's routes/focus.py;
// the option list itself comes from GET /v1/focus-options.

export const MAX_STRENGTHS = 4;
export const MAX_IMPROVE = 3;
export const MAX_PER_REFLECTION = 3;
// A game you played shows "How did it go?" for this long.
export const REFLECT_PROMPT_DAYS = 7;

export interface FocusOption {
  id: string;
  label: string;
  area: string;
}

export interface Suggestion {
  option_id: string;
  kind: "strength" | "improve";
  count: number;
  out_of: number;
}

export interface Focus {
  strengths: string[];
  improve: string[];
  suggestions: Suggestion[];
}

export interface Reflection {
  went_well: string[];
  to_improve: string[];
}

/** Options in list order, grouped by area. */
export function byArea(options: readonly FocusOption[]): { area: string; options: FocusOption[] }[] {
  const groups: { area: string; options: FocusOption[] }[] = [];
  for (const option of options) {
    const last = groups.at(-1);
    if (last?.area === option.area) {
      last.options.push(option);
    } else {
      groups.push({ area: option.area, options: [option] });
    }
  }
  return groups;
}

export function labelFor(options: readonly FocusOption[], id: string): string {
  return options.find((o) => o.id === id)?.label ?? id;
}

/** "You picked Third-shot drops as going well in 6 of your last 10 games." */
export function describeSuggestion(suggestion: Suggestion, label: string): string {
  const how = suggestion.kind === "strength" ? "as going well" : "as something to improve";
  const games = suggestion.out_of === 1 ? "game" : "games";
  return `You picked ${label} ${how} in ${String(suggestion.count)} of your last ${String(suggestion.out_of)} ${games}.`;
}

/**
 * The profile lists after accepting a suggestion: the option joins its list and leaves the
 * other one. Null when that list is already full.
 */
export function promote(focus: Pick<Focus, "strengths" | "improve">, suggestion: Suggestion): Pick<Focus, "strengths" | "improve"> | null {
  const id = suggestion.option_id;
  if (suggestion.kind === "strength") {
    if (focus.strengths.length >= MAX_STRENGTHS) {
      return null;
    }
    return { strengths: [...focus.strengths, id], improve: focus.improve.filter((x) => x !== id) };
  }
  if (focus.improve.length >= MAX_IMPROVE) {
    return null;
  }
  return { strengths: focus.strengths.filter((x) => x !== id), improve: [...focus.improve, id] };
}

/** Whether a game you played still shows the "How did it go?" prompt. */
export function wantsReflection(
  match: { i_played: boolean; my_reflection: Reflection | null; played_at: string },
  now: Date = new Date(),
): boolean {
  const age = now.getTime() - new Date(match.played_at).getTime();
  return match.i_played && match.my_reflection === null && age < REFLECT_PROMPT_DAYS * 86_400_000;
}

/** Toggle `id` in `selected`, keeping at most `max`. Returns the same array when full. */
export function toggle(selected: readonly string[], id: string, max: number): string[] {
  if (selected.includes(id)) {
    return selected.filter((x) => x !== id);
  }
  return selected.length >= max ? [...selected] : [...selected, id];
}
