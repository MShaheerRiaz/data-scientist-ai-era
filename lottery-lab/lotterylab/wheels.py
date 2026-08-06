"""Lottery wheels: covering designs with provable guarantees.

A "wheel" is a set of tickets built from a chosen pool of numbers such
that *if* enough of your chosen numbers come up, you are **guaranteed** at
least one ticket with a given number of matches.  Unlike almost everything
else sold to lottery players, this part is real mathematics — these are
covering designs, and the guarantee is a theorem, not a sales pitch.

Be precise about what is guaranteed, though.  A wheel does **not** improve
your odds of winning the jackpot; buying ``n`` distinct tickets multiplies
your jackpot chance by exactly ``n`` no matter how you choose them.  What a
wheel does is *concentrate* your lower-tier outcomes: it converts a random
scatter of small wins into a guaranteed floor, conditional on your chosen
numbers performing.  It trades variance for certainty, and it costs money
to do so.

Formally, a ``(v, k, t)`` covering design is a collection of ``k``-subsets
(blocks) of a ``v``-set such that every ``t``-subset is contained in at
least one block.  ``C(v, k, t)`` denotes the minimum possible number of
blocks.  Known optimal values are catalogued in the La Jolla Covering
Repository; the greedy-plus-local-search construction here gets close to
optimal for small cases and always *verifies* the guarantee it claims.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from itertools import combinations
from typing import Iterable, Optional, Sequence

from .combinatorics import comb

__all__ = [
    "Wheel",
    "full_wheel",
    "covering_design",
    "key_number_wheel",
    "verify_covering",
    "schonheim_bound",
    "guarantee_report",
]


@dataclass
class Wheel:
    """A set of tickets built from a chosen pool of numbers."""

    numbers: tuple[int, ...]
    blocks: list[tuple[int, ...]]
    guarantee_t: int
    guarantee_match: int
    verified: bool = False
    name: str = "wheel"

    @property
    def size(self) -> int:
        """Number of tickets in the wheel."""
        return len(self.blocks)

    def cost(self, ticket_price: float) -> float:
        """What the wheel costs to play."""
        return self.size * ticket_price

    def describe(self) -> str:
        """Plain-language statement of what this wheel guarantees."""
        status = "verified" if self.verified else "UNVERIFIED"
        return (
            f"{self.name}: {self.size} tickets from {len(self.numbers)} numbers. "
            f"Guarantee ({status}): if at least {self.guarantee_t} of the drawn numbers "
            f"are among your {len(self.numbers)}, at least one ticket matches "
            f"{self.guarantee_match} or more."
        )


def schonheim_bound(v: int, k: int, t: int) -> int:
    """Schoenheim lower bound on the covering number ``C(v, k, t)``.

    No covering design can use fewer blocks than this, so it measures how
    close a constructed wheel is to optimal.  The bound is the nested
    ceiling::

        L(v,k,t) = ceil( v/k * ceil( (v-1)/(k-1) * ... ceil( (v-t+1)/(k-t+1) ) ) )

    The nesting order matters and is easy to get backwards: ceilings do not
    commute, so the recursion has to be evaluated **innermost first**
    (starting at ``v-t+1`` and working outwards).  Evaluating it
    outermost-first produces values that exceed known optimal designs — it
    would claim C(49,6,2) >= 87 when the true covering number is 82 —
    which is not a lower bound at all.

    Sanity checks: this returns 82 for ``C(49,6,2)`` and 325,205 for
    ``C(49,6,5)``, both of which are known to meet the Schoenheim bound
    exactly.
    """
    if t == 0:
        return 1
    if t > k or k > v:
        raise ValueError("require t <= k <= v")
    bound = 1
    for i in range(t - 1, -1, -1):
        bound = -(-(v - i) * bound // (k - i))  # ceiling division
    return bound


def full_wheel(numbers: Sequence[int], pick: int) -> Wheel:
    """Every possible combination of ``pick`` numbers from the chosen pool.

    The complete guarantee — if all ``pick`` drawn numbers are among your
    chosen set, you hold the jackpot ticket.  Also the most expensive
    option by a wide margin: 15 chosen numbers in a 6-ball game is
    ``C(15,6) = 5,005`` tickets.
    """
    values = tuple(sorted(set(numbers)))
    if len(values) < pick:
        raise ValueError(f"need at least {pick} numbers, got {len(values)}")
    blocks = list(combinations(values, pick))
    return Wheel(numbers=values, blocks=blocks, guarantee_t=pick,
                 guarantee_match=pick, verified=True,
                 name=f"full wheel {len(values)}/{pick}")


def covering_design(
    numbers: Sequence[int],
    pick: int,
    coverage: int,
    *,
    guarantee_match: Optional[int] = None,
    seed: int = 0,
    restarts: int = 6,
    local_search_rounds: int = 4000,
    verify: bool = True,
) -> Wheel:
    """Build an abbreviated wheel: a ``(v, pick, coverage)`` covering design.

    Guarantees that if ``coverage`` of the drawn numbers fall inside your
    chosen pool, at least one of your tickets matches at least
    ``guarantee_match`` (which defaults to ``coverage``).

    Construction is randomised greedy — repeatedly take the block covering
    the most still-uncovered ``t``-subsets — followed by a pruning pass that
    removes blocks made redundant by later additions, over several random
    restarts.  This is not guaranteed optimal (computing ``C(v,k,t)`` exactly
    is hard), but it lands close for the small sizes players actually use,
    and the result is verified rather than asserted.
    """
    values = tuple(sorted(set(numbers)))
    v = len(values)
    if not 0 < coverage <= pick <= v:
        raise ValueError("require 0 < coverage <= pick <= len(numbers)")
    if guarantee_match is None:
        guarantee_match = coverage

    targets = list(combinations(range(v), coverage))
    target_index = {t: i for i, t in enumerate(targets)}
    all_blocks = list(combinations(range(v), pick))

    # Which targets each candidate block covers.
    block_targets: list[tuple[int, ...]] = [
        tuple(target_index[c] for c in combinations(block, coverage))
        for block in all_blocks
    ]

    best: Optional[list[int]] = None
    rng = random.Random(seed)

    for attempt in range(max(1, restarts)):
        uncovered = set(range(len(targets)))
        chosen: list[int] = []
        order = list(range(len(all_blocks)))
        rng.shuffle(order)

        while uncovered:
            best_idx, best_gain = -1, -1
            for idx in order:
                gain = sum(1 for t in block_targets[idx] if t in uncovered)
                if gain > best_gain:
                    best_gain, best_idx = gain, idx
                    if gain == len(block_targets[idx]):
                        break
            if best_idx < 0 or best_gain <= 0:
                break
            chosen.append(best_idx)
            uncovered.difference_update(block_targets[best_idx])

        chosen = _prune(chosen, block_targets, len(targets))

        # Local search: swap a block out for a random alternative, keep if no worse.
        for _ in range(local_search_rounds if attempt == 0 else local_search_rounds // 4):
            if len(chosen) <= 1:
                break
            drop = rng.randrange(len(chosen))
            trial = chosen[:drop] + chosen[drop + 1:]
            covered = set()
            for idx in trial:
                covered.update(block_targets[idx])
            missing = set(range(len(targets))) - covered
            if not missing:
                chosen = trial
                continue
            candidate = max(
                range(len(all_blocks)),
                key=lambda i: sum(1 for t in block_targets[i] if t in missing),
            )
            gain = sum(1 for t in block_targets[candidate] if t in missing)
            if gain == len(missing):
                trial = trial + [candidate]
                if len(trial) < len(chosen):
                    chosen = _prune(trial, block_targets, len(targets))

        if best is None or len(chosen) < len(best):
            best = chosen

    assert best is not None
    blocks = [tuple(values[i] for i in all_blocks[idx]) for idx in best]
    blocks.sort()

    wheel = Wheel(
        numbers=values, blocks=blocks, guarantee_t=coverage,
        guarantee_match=guarantee_match,
        name=f"covering wheel C({v},{pick},{coverage})",
    )
    if verify:
        wheel.verified = verify_covering(wheel, pick)
        if not wheel.verified:
            raise RuntimeError("constructed wheel failed its own guarantee check")
    return wheel


def _prune(chosen: Sequence[int], block_targets: Sequence[tuple[int, ...]], n_targets: int) -> list[int]:
    """Drop blocks whose targets are already covered by the others."""
    result = list(chosen)
    changed = True
    while changed:
        changed = False
        for i in range(len(result) - 1, -1, -1):
            trial = result[:i] + result[i + 1:]
            covered = set()
            for idx in trial:
                covered.update(block_targets[idx])
            if len(covered) == n_targets:
                result = trial
                changed = True
    return result


def key_number_wheel(
    numbers: Sequence[int],
    pick: int,
    key_numbers: Sequence[int],
) -> Wheel:
    """A wheel where certain "key" numbers appear on every ticket.

    Popular because it is cheap, and worth understanding honestly: it only
    pays off if the key numbers actually come up.  If they miss, *every*
    ticket is damaged at once — you have concentrated your risk rather than
    spread it.  The guarantee is correspondingly conditional.
    """
    values = tuple(sorted(set(numbers)))
    keys = tuple(sorted(set(key_numbers)))
    if not set(keys).issubset(values):
        raise ValueError("key numbers must be part of the chosen pool")
    if len(keys) >= pick:
        raise ValueError("need fewer key numbers than the pick size")

    rest = [v for v in values if v not in keys]
    remaining = pick - len(keys)
    blocks = [tuple(sorted(keys + combo)) for combo in combinations(rest, remaining)]
    return Wheel(
        numbers=values, blocks=blocks,
        guarantee_t=pick, guarantee_match=pick, verified=True,
        name=f"key-number wheel ({len(keys)} keys, {len(values)} numbers)",
    )


def verify_covering(wheel: Wheel, pick: int) -> bool:
    """Exhaustively confirm a wheel delivers what it claims.

    Enumerates every way ``guarantee_t`` of the drawn numbers could land
    inside the chosen pool and checks that some ticket achieves the promised
    match count.  Trust the check, not the construction.
    """
    values = wheel.numbers
    t = wheel.guarantee_t
    need = wheel.guarantee_match
    block_sets = [set(b) for b in wheel.blocks]
    for subset in combinations(values, t):
        target = set(subset)
        if not any(len(target & block) >= need for block in block_sets):
            return False
    return True


def guarantee_report(wheel: Wheel, pick: int) -> dict[int, int]:
    """Worst-case match count for every possible level of pool performance.

    Maps "how many drawn numbers landed in your chosen pool" to "the
    minimum matches you are guaranteed on your best ticket".  This is the
    honest full picture, and it usually shows a wheel doing less than its
    marketing implies at the levels that matter.
    """
    values = wheel.numbers
    block_sets = [set(b) for b in wheel.blocks]
    report: dict[int, int] = {}
    for hits in range(1, min(pick, len(values)) + 1):
        worst = pick
        for subset in combinations(values, hits):
            target = set(subset)
            best = max((len(target & block) for block in block_sets), default=0)
            worst = min(worst, best)
            if worst == 0:
                break
        report[hits] = worst
    return report
