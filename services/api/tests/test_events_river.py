"""Ride the River (events.river): winners up, losers down, partners split."""

import random
from collections.abc import Mapping, Sequence
from uuid import UUID, uuid4

import pytest

from popshot_api.events import Court, Round, games_played
from popshot_api.events.river import Winner, next_round


def people(n: int) -> list[UUID]:
    return [uuid4() for _ in range(n)]


def results(r: Round, rng: random.Random) -> dict[int, Winner]:
    return {k: rng.choice(("A", "B")) for k in range(len(r.courts))}


def ride(
    players: Sequence[UUID], courts: int, rounds: int, seed: int = 3
) -> list[tuple[Round, dict[int, Winner]]]:
    rng = random.Random(seed)  # noqa: S311 - made-up results for a test
    played: list[tuple[Round, dict[int, Winner]]] = []
    for _ in range(rounds):
        history = [r for r, _ in played]
        winners: Mapping[int, Winner] = played[-1][1] if played else {}
        r = next_round(players, courts, history, winners=winners, start=players, seed=seed)
        played.append((r, results(r, rng)))
    return played


def teams(court: Court) -> set[frozenset[UUID]]:
    return {frozenset(court.team_a), frozenset(court.team_b)}


def test_the_first_round_follows_the_starting_order() -> None:
    p = people(8)
    r = next_round(p, 2, [], winners={}, start=p, seed=1)
    # Dealt top court down; on each court 1st and 4th play 2nd and 3rd.
    assert r.courts == (Court((p[0], p[3]), (p[1], p[2])), Court((p[4], p[7]), (p[5], p[6])))
    assert r.sitting_out == ()


def test_winners_go_up_losers_go_down_and_partners_split() -> None:
    p = people(12)
    first = next_round(p, 3, [], winners={}, start=p, seed=1)
    top, middle, bottom = first.courts
    second = next_round(p, 3, [first], winners={0: "A", 1: "B", 2: "A"}, start=p, seed=1)
    new_top, new_middle, new_bottom = second.courts
    # Top court: its own winners stay, the middle court's winners come up.
    assert set(new_top.players) == {*top.team_a, *middle.team_b}
    # Middle: the top court's losers come down, the bottom court's winners come up.
    assert set(new_middle.players) == {*top.team_b, *bottom.team_a}
    # Bottom: the middle court's losers come down, and its own losers stay.
    assert set(new_bottom.players) == {*middle.team_a, *bottom.team_b}
    # Nobody keeps their partner.
    before = set().union(*(teams(c) for c in first.courts))
    after = set().union(*(teams(c) for c in second.courts))
    assert not before & after


def test_one_court_keeps_everyone_and_splits_partners() -> None:
    p = people(4)
    first = next_round(p, 1, [], winners={}, start=p, seed=1)
    second = next_round(p, 1, [first], winners={0: "B"}, start=p, seed=1)
    assert set(second.courts[0].players) == set(p)
    assert not teams(first.courts[0]) & teams(second.courts[0])


def test_a_skipped_court_stays_put() -> None:
    p = people(8)
    first = next_round(p, 2, [], winners={}, start=p, seed=1)
    # Court 2 had no result, so nobody comes up from it: court 1 keeps its four, court 2 its.
    second = next_round(p, 2, [first], winners={0: "A"}, start=p, seed=1)
    assert set(second.courts[0].players) == set(first.courts[0].players)
    assert set(second.courts[1].players) == set(first.courts[1].players)
    assert not teams(first.courts[0]) & teams(second.courts[0])
    assert not teams(first.courts[1]) & teams(second.courts[1])
    # A skipped middle court blocks moves through it: every court keeps its four, and
    # everyone still gets a new partner.
    q = people(12)
    one = next_round(q, 3, [], winners={}, start=q, seed=1)
    two = next_round(q, 3, [one], winners={0: "A", 2: "A"}, start=q, seed=1)
    for before, after in zip(one.courts, two.courts, strict=True):
        assert set(after.players) == set(before.players)
        assert not teams(before) & teams(after)


@pytest.mark.parametrize("n", range(4, 25))
@pytest.mark.parametrize("courts", [1, 2, 3, 6])
def test_every_round_is_fair(n: int, courts: int) -> None:
    p = people(n)
    played = ride(p, courts, 12)
    rounds = [r for r, _ in played]
    for i, r in enumerate(rounds):
        assert sorted([*r.playing, *r.sitting_out], key=str) == sorted(p, key=str)
        assert len(r.courts) == min(courts, n // 4)
        if i > 0:
            prev = set(rounds[i - 1].sitting_out)
            if n - len(prev) >= len(r.sitting_out):
                assert not prev & set(r.sitting_out), (n, courts, i)
        played_so_far = games_played(rounds[: i + 1])
        counts = [played_so_far[x] for x in p]
        assert max(counts) - min(counts) <= 1, (n, courts, i)


def test_people_come_and_go() -> None:
    p = people(9)
    played = ride(p, 2, 3)
    history = [r for r, _ in played]
    late, leaver = uuid4(), p[0]
    now = [x for x in p if x != leaver] + [late]
    r = next_round(now, 2, history, winners=played[-1][1], start=p, seed=3)
    assert sorted([*r.playing, *r.sitting_out], key=str) == sorted(now, key=str)
    # Someone new gets a game rather than waiting.
    assert late in r.playing
    # Down to 7: one court, three wait.
    fewer = now[:7]
    r2 = next_round(fewer, 2, [*history, r], winners={0: "A", 1: "B"}, start=p, seed=3)
    assert (len(r2.courts), len(r2.sitting_out)) == (1, 3)


def test_the_same_seed_gives_the_same_rounds() -> None:
    p = people(10)
    assert ride(p, 2, 5, seed=9) == ride(p, 2, 5, seed=9)
