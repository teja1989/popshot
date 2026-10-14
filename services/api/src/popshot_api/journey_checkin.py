"""Journey check-ins: the facts of two weeks, the chapter you're in, and Popshot's own words.

The facts come from your games, reflections, learning notes and story in the check-in's
period, read as you (row-level security applies). Popshot's own words (`lines_for`) always
work; the AI (journey_ai.py) may write them instead, from the same facts, when you've said
yes to that. Every check-in leads with something that went well, then one thing to try next:
never a list of faults, never a comparison with anyone else.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from popshot_api.focus import FOCUS_OPTIONS, OFFERED_IDS
from popshot_api.recap_lines import first_name

EVERY = timedelta(days=14)
SHOWN = 3
NOTES_GIVEN = 10

Chapter = Literal["feet", "rallies", "kitchen", "plan", "sharpening"]
CHAPTERS: tuple[Chapter, ...] = ("feet", "rallies", "kitchen", "plan", "sharpening")
CHAPTER_LABEL: dict[Chapter, str] = {
    "feet": "Finding your feet",
    "rallies": "Building rallies",
    "kitchen": "Owning the kitchen",
    "plan": "Playing with a plan",
    "sharpening": "Sharpening for competition",
}
# (games played, games reflected on) to reach each chapter after the first.
CHAPTER_NEEDS: tuple[tuple[int, int], ...] = ((10, 0), (30, 5), (60, 15), (100, 30))
# The chapter your level starts you in, at least.
LEVEL_FLOOR = {"beginner": 0, "intermediate": 1, "advanced": 2, "expert": 2}

_LABELS = {o.id: o.label for o in FOCUS_OPTIONS}


def chapter_for(games: int, reflected: int, level: str | None, previous: Chapter | None) -> Chapter:
    """The chapter for this many games and reflections, never below your level's start or
    the chapter you'd already reached: chapters only move forward."""
    reached = sum(1 for g, r in CHAPTER_NEEDS if games >= g and reflected >= r)
    floor = LEVEL_FLOOR.get(level or "", 0)
    before = CHAPTERS.index(previous) if previous else 0
    return CHAPTERS[max(reached, floor, before)]


@dataclass(frozen=True, slots=True)
class Words:
    headline: str
    lines: tuple[str, ...]
    try_next: str


def _skill_counts(rows: list[Any], column: str) -> Counter[str]:
    return Counter(i for row in rows for i in getattr(row, column) if i in OFFERED_IDS)


def _trend(now: Counter[str], before: Counter[str]) -> list[dict[str, Any]]:
    return [
        {"skill": _LABELS[skill], "id": skill, "times": n, "before": before.get(skill, 0)}
        for skill, n in sorted(now.items(), key=lambda kv: (-kv[1], kv[0]))[:SHOWN]
    ]


def build_facts(
    session: Session, me: UUID, start: datetime, end: datetime, previous: Chapter | None
) -> dict[str, Any]:
    """Everything a check-in may say, for [start, end), as plain data."""
    params = {"me": me, "start": start, "end": end, "before": start - (end - start)}
    name = session.execute(
        text("SELECT display_name, self_level FROM users WHERE id = :me"), params
    ).one()
    games = session.execute(
        text(
            """
            SELECT m.id, m.played_at, g.name AS crew, mine.team,
                   (SELECT count(*) FILTER (
                        WHERE (mine.team = 'A') = (mg.team_a_score > mg.team_b_score))
                    FROM match_games mg WHERE mg.match_id = m.id) AS games_won,
                   (SELECT count(*) FROM match_games mg WHERE mg.match_id = m.id) AS games_in,
                   (SELECT bool_or(abs(mg.team_a_score - mg.team_b_score) <= 2)
                    FROM match_games mg WHERE mg.match_id = m.id) AS close,
                   (SELECT array_agg(p.display_name ORDER BY p.display_name)
                    FROM match_players mp JOIN players p ON p.id = mp.player_id
                    WHERE mp.match_id = m.id AND mp.team = mine.team
                      AND p.id <> mine.player_id) AS partners
            FROM players me_p
            JOIN match_players mine ON mine.player_id = me_p.id
            JOIN matches m ON m.id = mine.match_id
            JOIN groups g ON g.id = m.group_id
            WHERE me_p.user_id = :me AND m.played_at >= :start AND m.played_at < :end
            ORDER BY m.played_at
            """
        ),
        params,
    ).all()
    previous_games = session.execute(
        text(
            """
            SELECT count(*) FROM players p JOIN match_players mp ON mp.player_id = p.id
            JOIN matches m ON m.id = mp.match_id
            WHERE p.user_id = :me AND m.played_at >= :before AND m.played_at < :start
            """
        ),
        params,
    ).scalar_one()
    totals = session.execute(
        text(
            """
            SELECT (SELECT count(*) FROM players p JOIN match_players mp ON mp.player_id = p.id
                    JOIN matches m ON m.id = mp.match_id
                    WHERE p.user_id = :me AND m.played_at < :end) AS games,
                   (SELECT count(*) FROM match_reflections r
                    WHERE r.user_id = :me AND r.created_at < :end
                      AND cardinality(r.went_well) + cardinality(r.to_improve) > 0) AS reflected
            """
        ),
        params,
    ).one()
    reflections = session.execute(
        text(
            "SELECT went_well, to_improve, created_at FROM match_reflections "
            "WHERE user_id = :me AND created_at >= :before AND created_at < :end "
            "AND cardinality(went_well) + cardinality(to_improve) > 0"
        ),
        params,
    ).all()
    now_rows = [r for r in reflections if r.created_at >= start]
    before_rows = [r for r in reflections if r.created_at < start]
    notes = (
        session.execute(
            text(
                "SELECT body FROM journey_notes WHERE user_id = :me "
                "AND created_at >= :start AND created_at < :end ORDER BY created_at DESC LIMIT :n"
            ),
            {**params, "n": NOTES_GIVEN},
        )
        .scalars()
        .all()
    )
    story = session.execute(
        text(
            "SELECT goal, gaps, tag_gaps FROM journey_entries WHERE user_id = :me "
            "AND created_at < :end ORDER BY created_at DESC LIMIT 1"
        ),
        params,
    ).one_or_none()
    focus = session.execute(
        text("SELECT improve FROM user_focus WHERE user_id = :me"), params
    ).scalar_one_or_none()

    partners: Counter[str] = Counter(first_name(p) for g in games for p in (g.partners or []))
    working_on = [s for s in (story.tag_gaps if story else []) or (focus or []) if s in OFFERED_IDS]
    chapter = chapter_for(totals.games, totals.reflected, name.self_level, previous)
    return {
        "first_name": first_name(name.display_name),
        "days": (end - start).days,
        "games": len(games),
        "wins": sum(1 for g in games if g.games_in and g.games_won * 2 > g.games_in),
        "close_games": sum(1 for g in games if g.close),
        "days_played": len({g.played_at.date() for g in games}),
        "crews": sorted({g.crew for g in games}),
        "partners": [
            {"name": p, "games": n}
            for p, n in sorted(partners.items(), key=lambda kv: (-kv[1], kv[0]))[:SHOWN]
        ],
        "previous_games": previous_games,
        "reflected_games": len(now_rows),
        "went_well": _trend(
            _skill_counts(now_rows, "went_well"), _skill_counts(before_rows, "went_well")
        ),
        "to_improve": _trend(
            _skill_counts(now_rows, "to_improve"), _skill_counts(before_rows, "to_improve")
        ),
        "working_on": [_LABELS[s] for s in working_on[:SHOWN]],
        "working_on_ids": working_on[:SHOWN],
        "chapter": CHAPTER_LABEL[chapter],
        "chapter_id": chapter,
        "new_chapter": previous is not None and chapter != previous,
        "games_ever": totals.games,
        "notes": list(notes),
        "goal": story.goal if story and story.goal else None,
        "in_your_words": story.gaps if story and story.gaps else None,
    }


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def lines_for(facts: dict[str, Any]) -> Words:
    """Popshot's own words: a win first, then what the period showed, then one thing to try."""
    games, wins, days = facts["games"], facts["wins"], facts["days_played"]
    if facts["new_chapter"]:
        headline = f"A new chapter: {facts['chapter']}"
    elif games:
        headline = f"{_plural(games, 'game')} in two weeks of pickleball"
    else:
        headline = "Two weeks of learning"
    lines: list[str] = []
    if games:
        played = f"You played {_plural(games, 'game')} on {_plural(days, 'day')}"
        played = f"{played} and won {wins}" if wins else played
        close = facts["close_games"]
        lines.append(f"{played}, {close} of them close." if close else f"{played}.")
    if facts["partners"]:
        top = facts["partners"][0]
        lines.append(f"You teamed up most with {top['name']} ({_plural(top['games'], 'game')}).")
    if facts["went_well"]:
        best = facts["went_well"][0]
        lines.append(f"{best['skill']} went well in {_plural(best['times'], 'game')}.")
    if facts["to_improve"]:
        work = facts["to_improve"][0]
        if 0 < work["times"] < work["before"]:
            lines.append(
                f"You marked {work['skill']} to work on less often: "
                f"{work['times']}, down from {work['before']}."
            )
        else:
            lines.append(f"You're working on {work['skill']}.")
    if facts["notes"]:
        lines.append(f"You wrote {_plural(len(facts['notes']), 'learning note')}.")
    if facts["goal"]:
        lines.append(f"Your goal: {facts['goal']}")
    focus = (facts["to_improve"][0]["skill"] if facts["to_improve"] else None) or (
        facts["working_on"][0] if facts["working_on"] else None
    )
    try_next = (
        f"Next: pick one moment in each game to practise {focus.lower()}."
        if focus
        else "Next: notice one thing that goes well in each game."
    )
    return Words(
        headline=headline[:120], lines=tuple(line[:200] for line in lines[:6]), try_next=try_next
    )


def pick_skills(facts: dict[str, Any]) -> list[str]:
    """The skills library picks are for: what you marked to work on, then what you named."""
    wanted = [t["id"] for t in facts["to_improve"]] + list(facts["working_on_ids"])
    return list(dict.fromkeys(wanted))[:SHOWN]
