"""Exact combinatorics for draw games.

Every probability in this module is computed exactly with integer
arithmetic wherever possible.  Nothing here is estimated by simulation,
because for these structures it does not need to be.
"""

from __future__ import annotations

import math
import random
from functools import lru_cache
from typing import Iterable, Iterator, Sequence

from .config import BonusMode, LotteryConfig, PrizeTier

__all__ = [
    "comb",
    "total_combinations",
    "tier_probability",
    "match_probability",
    "all_tier_probabilities",
    "jackpot_probability",
    "any_prize_probability",
    "match_count",
    "classify_ticket",
    "unrank_combination",
    "rank_combination",
    "random_combination",
    "iter_combinations",
    "sum_distribution",
    "sum_percentile",
    "odds_string",
]

comb = math.comb


# ---------------------------------------------------------------------------
# Sizes and tier probabilities
# ---------------------------------------------------------------------------


def total_combinations(config: LotteryConfig) -> int:
    """Number of distinct tickets in the game.

    For Powerball this is ``C(69,5) * 26 = 292,201,338``.
    """
    total = comb(config.main_pool, config.main_pick)
    if config.bonus_mode is BonusMode.SEPARATE_POOL:
        total *= comb(config.bonus_pool, config.bonus_pick)
    return total


def _main_match_probability(config: LotteryConfig, main_match: int) -> float:
    """P(a ticket matches exactly ``main_match`` of the main numbers).

    Hypergeometric: choose which of the player's numbers hit and which of
    the undrawn balls fill the rest of the ticket.
    """
    n, k = config.main_pool, config.main_pick
    if not 0 <= main_match <= k:
        return 0.0
    ways = comb(k, main_match) * comb(n - k, k - main_match)
    return ways / comb(n, k)


def tier_probability(config: LotteryConfig, main_match: int, bonus_match: int = 0) -> float:
    """P(a ticket matches exactly ``main_match`` main and ``bonus_match`` bonus).

    Handles all three bonus modes.  The ``FROM_REMAINING`` case is the
    subtle one: the bonus ball is drawn from the balls the main draw left
    behind, so whether the player hits it is *conditional* on how many main
    numbers they missed.
    """
    base = _main_match_probability(config, main_match)
    if base == 0.0:
        return 0.0

    if config.bonus_mode is BonusMode.NONE:
        return base if bonus_match == 0 else 0.0

    if config.bonus_mode is BonusMode.SEPARATE_POOL:
        m, b = config.bonus_pool, config.bonus_pick
        if not 0 <= bonus_match <= b:
            return 0.0
        bonus_p = comb(b, bonus_match) * comb(m - b, b - bonus_match) / comb(m, b)
        return base * bonus_p

    # FROM_REMAINING: one bonus ball drawn uniformly from the n - k undrawn balls.
    n, k = config.main_pool, config.main_pick
    misses = k - main_match          # player numbers sitting in the undrawn pile
    p_hit_bonus = misses / (n - k)
    if bonus_match == 1:
        return base * p_hit_bonus
    if bonus_match == 0:
        return base * (1.0 - p_hit_bonus)
    return 0.0


def _max_bonus_match(config: LotteryConfig) -> int:
    """Largest number of bonus balls a ticket could match."""
    if config.bonus_mode is BonusMode.SEPARATE_POOL:
        return config.bonus_pick
    if config.bonus_mode is BonusMode.FROM_REMAINING:
        return 1
    return 0


def match_probability(config: LotteryConfig, tier: PrizeTier) -> float:
    """P(a ticket lands on ``tier``).

    Tiers flagged ``bonus_any`` sum over every possible bonus outcome,
    because the prize pays on main matches alone.
    """
    if tier.bonus_any:
        return sum(
            tier_probability(config, tier.main_match, b)
            for b in range(_max_bonus_match(config) + 1)
        )
    return tier_probability(config, tier.main_match, tier.bonus_match)


def all_tier_probabilities(config: LotteryConfig) -> list[tuple[PrizeTier, float]]:
    """Every prize tier paired with its exact probability, best tier first."""
    return [(tier, match_probability(config, tier)) for tier in config.tiers]


def jackpot_probability(config: LotteryConfig) -> float:
    """P(a single ticket wins the top prize)."""
    tier = config.jackpot_tier
    if tier is not None:
        return match_probability(config, tier)
    return 1.0 / total_combinations(config)


def any_prize_probability(config: LotteryConfig) -> float:
    """P(a single ticket wins *something*.

    Tiers are mutually exclusive by construction (each fixes an exact main
    and bonus match count), so these probabilities simply add.
    """
    return sum(p for _, p in all_tier_probabilities(config))


# ---------------------------------------------------------------------------
# Evaluating a ticket against a draw
# ---------------------------------------------------------------------------


def match_count(
    ticket: Sequence[int],
    drawn: Sequence[int],
) -> int:
    """How many of ``ticket``'s numbers appear in ``drawn``."""
    return len(set(ticket) & set(drawn))


def classify_ticket(
    config: LotteryConfig,
    ticket: Sequence[int],
    drawn_main: Sequence[int],
    drawn_bonus: Sequence[int] = (),
    ticket_bonus: Sequence[int] = (),
) -> tuple[PrizeTier | None, int, int]:
    """Work out which tier a ticket lands in.

    Returns ``(tier_or_None, main_matches, bonus_matches)``.  ``None`` means
    the ticket won nothing.
    """
    mains = match_count(ticket, drawn_main)

    if config.bonus_mode is BonusMode.SEPARATE_POOL:
        bonuses = match_count(ticket_bonus, drawn_bonus)
    elif config.bonus_mode is BonusMode.FROM_REMAINING:
        # The bonus is matched by any *unused* number on the player's ticket.
        bonuses = len((set(ticket) - set(drawn_main)) & set(drawn_bonus))
    else:
        bonuses = 0

    # Tiers are ordered best-first, so the first match is the highest prize.
    for tier in config.tiers:
        if tier.main_match != mains:
            continue
        if tier.bonus_any or tier.bonus_match == bonuses:
            return tier, mains, bonuses
    return None, mains, bonuses


# ---------------------------------------------------------------------------
# Addressing the combination space
# ---------------------------------------------------------------------------


def unrank_combination(index: int, n: int, k: int) -> tuple[int, ...]:
    """The ``index``-th k-subset of ``{1..n}`` in lexicographic order.

    Lets you address any ticket in a 292-million-combination space in
    microseconds without enumerating anything, which is what makes
    whole-space sampling and syndicate coverage analysis tractable.
    """
    total = comb(n, k)
    if not 0 <= index < total:
        raise IndexError(f"index {index} out of range for C({n},{k}) = {total}")
    out: list[int] = []
    x = 1
    remaining = k
    while remaining > 0:
        count = comb(n - x, remaining - 1)
        if index < count:
            out.append(x)
            remaining -= 1
        else:
            index -= count
        x += 1
    return tuple(out)


def rank_combination(combination: Sequence[int], n: int) -> int:
    """Inverse of :func:`unrank_combination`."""
    values = sorted(combination)
    k = len(values)
    index = 0
    x = 1
    for position, value in enumerate(values):
        if not 1 <= value <= n:
            raise ValueError(f"value {value} outside 1..{n}")
        while x < value:
            index += comb(n - x, k - position - 1)
            x += 1
        x = value + 1
    return index


def random_combination(n: int, k: int, rng: random.Random | None = None) -> tuple[int, ...]:
    """A uniformly random k-subset of ``{1..n}``, sorted."""
    rng = rng or random
    return tuple(sorted(rng.sample(range(1, n + 1), k)))


def iter_combinations(n: int, k: int) -> Iterator[tuple[int, ...]]:
    """Lazily enumerate every k-subset of ``{1..n}`` in lexicographic order."""
    from itertools import combinations

    return combinations(range(1, n + 1), k)


# ---------------------------------------------------------------------------
# Sum distribution
# ---------------------------------------------------------------------------


@lru_cache(maxsize=64)
def sum_distribution(n: int, k: int) -> dict[int, int]:
    """Exact count of k-subsets of ``{1..n}`` by their sum.

    Computed by dynamic programming, not simulation.  This underpins the
    "is my ticket's sum unusual?" check and the sum-based fairness test.
    """
    # dp[j] maps sum -> number of j-subsets achieving it.
    dp: list[dict[int, int]] = [dict() for _ in range(k + 1)]
    dp[0][0] = 1
    for value in range(1, n + 1):
        for j in range(min(k, value), 0, -1):
            source = dp[j - 1]
            if not source:
                continue
            target = dp[j]
            for s, count in source.items():
                target[s + value] = target.get(s + value, 0) + count
    return dict(dp[k])


def sum_percentile(n: int, k: int, total: int) -> float:
    """Fraction of k-subsets of ``{1..n}`` whose sum is <= ``total``."""
    dist = sum_distribution(n, k)
    grand = comb(n, k)
    below = sum(count for s, count in dist.items() if s <= total)
    return below / grand


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------


def odds_string(probability: float) -> str:
    """Render a probability as ``1 in N``, the way lotteries quote it."""
    if probability <= 0.0:
        return "never"
    if probability >= 1.0:
        return "certain"
    return f"1 in {1.0 / probability:,.0f}"
