"""The focus options players pick for Strengths, Areas to improve and post-game reflections.

IDs are permanent: stored data refers to them. To rename an option, change its label. To
retire one, set retired=True: it stays valid in saved data but isn't offered any more.
Add new options anywhere; the order here is the order on screen.
"""

from dataclasses import dataclass

MAX_STRENGTHS = 4
MAX_IMPROVE = 3
MAX_PER_REFLECTION = 3
# Suggest promoting an option picked in at least SUGGEST_MIN of your last SUGGEST_WINDOW
# reflections that weren't skipped.
SUGGEST_WINDOW = 10
SUGGEST_MIN = 5


@dataclass(frozen=True, slots=True)
class FocusOption:
    id: str
    label: str
    area: str
    retired: bool = False


FOCUS_OPTIONS: tuple[FocusOption, ...] = (
    FocusOption("serve_consistency", "Serve consistency", "Serve & return"),
    FocusOption("return_of_serve", "Return of serve", "Serve & return"),
    FocusOption("getting_to_kitchen", "Getting to the kitchen after the return", "Serve & return"),
    FocusOption("third_shot_drop", "Third-shot drops", "Third shot"),
    FocusOption("third_shot_drive", "Third-shot drives", "Third shot"),
    FocusOption("dinking_patience", "Dinking patience", "Kitchen"),
    FocusOption("kitchen_positioning", "Kitchen positioning", "Kitchen"),
    FocusOption("speedups_counters", "Speed-ups and counters", "Kitchen"),
    FocusOption("transition_resets", "Transition zone resets", "Transition"),
    FocusOption("reset_under_pressure", "Reset ability under pressure", "Transition"),
    FocusOption("put_aways", "Aggressive put-aways", "Finishing"),
    FocusOption("lobs_overheads", "Lobs and overheads", "Finishing"),
    FocusOption("footwork", "Footwork", "Movement"),
    FocusOption("court_coverage", "Court coverage", "Movement"),
    FocusOption("partner_communication", "Communication with partner", "Mental & team"),
    FocusOption("shot_selection", "Shot selection and patience", "Mental & team"),
)

KNOWN_IDS = frozenset(o.id for o in FOCUS_OPTIONS)
OFFERED_IDS = frozenset(o.id for o in FOCUS_OPTIONS if not o.retired)
