"""Modelling which combinations *other players* choose.

This is the only part of the toolkit that can genuinely improve your
expected return, so it is worth being precise about why.

You cannot change your probability of winning a jackpot.  You *can* change
how many people you split it with.  Player number choice is wildly
non-uniform — birthdays crush the 1-31 range, sevens are over-picked,
people draw lines and patterns on the bet slip — so combinations differ
enormously in how many co-winners they attract.  Picking unpopular
combinations leaves your win probability untouched while raising the
*conditional* payout, which raises expected value.

Two honest caveats.

1. This effect only bites on shared, pari-mutuel prizes — jackpots above
   all.  Fixed-prize tiers pay the same no matter how many others win.
2. It is not enough to make a lottery profitable.  Ziemba and colleagues
   found unpopular-number strategies lift returns substantially but still
   leave most games negative-EV.  This narrows the loss; it does not
   reverse it.

The weights below are directional, drawn from the published
conscious-selection literature (Ziemba et al. on Canada 6/49, Simon and
Farrell et al. on the UK National Lottery, Henze and Riedwyl).  Exact
magnitudes vary by country and era, and no operator publishes the
per-combination sales data that would pin them down.  Treat the ranking
as reliable and the absolute numbers as approximate — and recalibrate
with :func:`calibrate_from_winner_counts` if you ever get real data.
"""

from __future__ import annotations

import dataclasses
import math
import random
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterable, Optional, Sequence

from .combinatorics import comb, random_combination
from .config import LotteryConfig

__all__ = [
    "PopularityWeights",
    "PopularityModel",
    "FeatureHit",
    "expected_cowinners",
    "share_factor",
]


# Normalisation constants are expensive to estimate and depend only on the
# game and the weight vector, so they are shared across model instances.
_BASELINE_CACHE: dict[tuple, float] = {}


@dataclass
class PopularityWeights:
    """Log-scale lift applied to a combination for each behavioural feature.

    A weight of ``0.40`` means "this feature multiplies a combination's
    selection odds by about ``e**0.40`` = 1.49".  Positive means players
    over-pick it, which is what you want to *avoid*.
    """

    # --- per-number effects (applied once per qualifying number) --------
    calendar_day: float = 0.32       # numbers 1-31 appear on birthdays
    month_number: float = 0.10       # 1-12 gets an extra bump
    lucky_seven: float = 0.55        # measured at ~1.9x uniform in Dutch selection data
    lucky_eight: float = 0.50        # ~1.8x uniform, close behind 7
    lucky_three: float = 0.10
    unlucky_thirteen: float = -0.10  # contested: avoided in the UK/US, POPULAR in France
    unlucky_four: float = -0.05      # avoided in East Asia
    round_number: float = -0.03      # multiples of 10 are mildly shunned
    # Numbers just above the calendar range attract players who are deliberately
    # avoiding dates. UK data shows 33 over-picked for exactly this reason, so
    # "just pick above 31" is already partly crowded.
    date_avoider_zone: float = 0.22  # applies to 32-36

    # --- bet-slip geometry ---------------------------------------------
    # Israeli data (805 million selections) shows pick rates declining
    # monotonically down the slip: 3.13%, 2.95%, 2.68%, 2.17% by row against a
    # 2.70% uniform rate - a 1.44x top-to-bottom ratio. This is one of the
    # largest and best-measured effects in the literature.
    slip_row_gradient: float = 0.36  # total log-lift spanned from top row to bottom
    slip_edge_aversion: float = -0.10  # leftmost column is persistently under-picked

    # --- whole-combination effects -------------------------------------
    all_calendar: float = 0.55       # every number <= 31: the classic birthday ticket
    # Proximity aversion: players AVOID adjacent numbers. A field experiment found
    # 70% preferred a random-looking ticket to a patterned one, and only 17% would
    # take a run of consecutives. Moderate runs are therefore UNDER-picked - the
    # opposite of the common assumption.
    consecutive_run: float = -0.30
    arithmetic_sequence: float = 0.55    # 5, 10, 15, 20... still over-picked
    same_slip_column: float = 0.85   # a vertical line down the bet slip
    slip_diagonal: float = 0.70      # a diagonal across the bet slip
    tight_cluster: float = -0.20     # clustering conflicts with proximity aversion
    all_same_decade: float = 0.30
    all_multiples_of_five: float = 0.60
    extreme_low_sum: float = 0.40    # small sums are over-picked with birthdays
    balanced_parity: float = 0.18    # a 3-odd/3-even "looking random" mix is favoured
    # Players generate evenly-spread combinations when trying to look random, and
    # a field experiment found the evenly-spread pattern was the ONLY distinctive
    # pattern players did not reject. This is the trap in "balanced" filters.
    even_spread: float = 0.30
    first_n_numbers: float = 1.80    # 1,2,3,4,5,6 - picked by thousands every draw
    # Recently drawn numbers are temporarily UNDER-bet: money on a number drops
    # sharply right after it appears and recovers only over months. This is a
    # genuine, time-limited, exploitable effect - and it points the opposite way
    # to "avoid numbers that just came up".
    recently_drawn: float = -0.28

    # --- structural ----------------------------------------------------
    # Share of tickets sold as machine-picked (uniform) rather than chosen.
    # Quick picks dilute every conscious-selection effect.
    quickpick_share: float = 0.70


@dataclass
class FeatureHit:
    """One feature that fired on a combination, with its contribution."""

    name: str
    weight: float
    detail: str = ""


class PopularityModel:
    """Estimates how heavily other players favour a given combination.

    The model is log-linear: each behavioural feature contributes an
    additive term to a log-weight, and the exponentiated weight is
    normalised against a uniform-random baseline so that
    :meth:`multiplier` returns "how many times more often than chance do
    players pick this combination".
    """

    def __init__(
        self,
        config: LotteryConfig,
        weights: Optional[PopularityWeights] = None,
        *,
        calibration_samples: int = 8000,
        seed: int = 20240601,
        recent_numbers: Optional[Iterable[int]] = None,
    ) -> None:
        self.config = config
        self.weights = weights or PopularityWeights()
        self._calibration_samples = calibration_samples
        self._seed = seed
        self._baseline: Optional[float] = None
        # Numbers drawn in the last few draws, which players temporarily shun.
        self.recent_numbers: set[int] = set(recent_numbers or ())

    @classmethod
    def with_recent_draws(
        cls,
        config: LotteryConfig,
        history,  # DrawHistory, imported lazily to avoid a cycle
        lookback: int = 3,
        weights: Optional[PopularityWeights] = None,
    ) -> "PopularityModel":
        """Build a model that knows which numbers came up recently.

        Players cut their stake on a number sharply right after it is
        drawn, recovering only over months.  That makes recently drawn
        numbers *temporarily under-bet* — one of the few genuinely
        actionable findings in this literature, and the opposite of the
        usual "avoid numbers that just came up" folk advice.
        """
        recent: set[int] = set()
        for draw in list(history)[-lookback:]:
            recent.update(draw.main)
        return cls(config, weights, recent_numbers=recent)

    # -- feature extraction ---------------------------------------------

    def features(self, combination: Sequence[int]) -> list[FeatureHit]:
        """Every behavioural feature that fires on this combination."""
        w = self.weights
        cfg = self.config
        values = sorted(combination)
        k = len(values)
        hits: list[FeatureHit] = []

        # Per-number effects.
        calendar = sum(1 for v in values if v <= 31)
        if calendar:
            hits.append(FeatureHit("calendar-day numbers", w.calendar_day * calendar,
                                   f"{calendar} number(s) <= 31"))
        months = sum(1 for v in values if v <= 12)
        if months:
            hits.append(FeatureHit("month-range numbers", w.month_number * months,
                                   f"{months} number(s) <= 12"))
        if 7 in values:
            hits.append(FeatureHit("contains 7", w.lucky_seven,
                                   "the most over-picked number worldwide, ~1.9x uniform"))
        if 8 in values:
            hits.append(FeatureHit("contains 8", w.lucky_eight, "~1.8x uniform"))
        if 3 in values:
            hits.append(FeatureHit("contains 3", w.lucky_three, ""))
        if 13 in values:
            hits.append(FeatureHit("contains 13", w.unlucky_thirteen,
                                   "avoided in the UK/US but POPULAR in France - culture-specific"))
        if 4 in values:
            hits.append(FeatureHit("contains 4", w.unlucky_four, ""))
        rounds = sum(1 for v in values if v % 10 == 0)
        if rounds:
            hits.append(FeatureHit("multiples of 10", w.round_number * rounds, ""))

        avoider = sum(1 for v in values if 32 <= v <= 36)
        if avoider:
            hits.append(FeatureHit("date-avoider zone (32-36)", w.date_avoider_zone * avoider,
                                   "already crowded by players deliberately picking above 31"))

        # Bet-slip row position: pick rates decline monotonically down the slip.
        cols_for_rows = cfg.slip_columns
        if cols_for_rows > 1:
            n_rows = max(1, (cfg.main_pool + cols_for_rows - 1) // cols_for_rows)
            if n_rows > 1:
                row_lift = 0.0
                for v in values:
                    row = (v - 1) // cols_for_rows
                    # +half the gradient at the top row, -half at the bottom.
                    row_lift += w.slip_row_gradient * (0.5 - row / (n_rows - 1))
                hits.append(FeatureHit("bet-slip row position", row_lift,
                                       "upper rows are scanned first and over-picked"))
            edge = sum(1 for v in values if (v - 1) % cols_for_rows == 0)
            if edge:
                hits.append(FeatureHit("left-edge positions", w.slip_edge_aversion * edge,
                                       "edge positions are persistently avoided"))

        # Whole-combination effects.
        if calendar == k:
            hits.append(FeatureHit("all numbers <= 31", w.all_calendar,
                                   "the classic all-birthdays ticket"))

        run = _longest_run(values)
        if run >= 2:
            hits.append(FeatureHit("consecutive run", w.consecutive_run * (run - 1),
                                   f"run of {run} - proximity aversion makes these UNDER-picked"))

        # Evenly-spread combinations are what people produce when trying to look
        # random, and they are over-picked as a result.
        if k >= 3:
            gaps = [b - a for a, b in zip(values, values[1:])]
            mean_gap = sum(gaps) / len(gaps)
            if mean_gap > 0:
                dispersion = max(gaps) - min(gaps)
                if dispersion <= max(2, cfg.main_pool // 20):
                    hits.append(FeatureHit("evenly spread", w.even_spread,
                                           "looks random to humans, so it is over-picked"))

        if k >= 3 and _is_arithmetic(values):
            step = values[1] - values[0]
            hits.append(FeatureHit("arithmetic sequence", w.arithmetic_sequence,
                                   f"constant step of {step}"))

        cols = cfg.slip_columns
        if cols > 1:
            if len({(v - 1) % cols for v in values}) == 1:
                hits.append(FeatureHit("single bet-slip column", w.same_slip_column,
                                       f"all numbers in column {(values[0] - 1) % cols + 1}"))
            if _is_slip_diagonal(values, cols):
                hits.append(FeatureHit("bet-slip diagonal", w.slip_diagonal, ""))

        spread = values[-1] - values[0]
        if spread <= max(6, cfg.main_pool // 6):
            hits.append(FeatureHit("tight cluster", w.tight_cluster, f"spread of only {spread}"))

        if len({(v - 1) // 10 for v in values}) == 1:
            hits.append(FeatureHit("all in one decade", w.all_same_decade, ""))

        if all(v % 5 == 0 for v in values):
            hits.append(FeatureHit("all multiples of 5", w.all_multiples_of_five, ""))

        total = sum(values)
        mean_total = k * (cfg.main_pool + 1) / 2
        if total < mean_total * 0.70:
            hits.append(FeatureHit("unusually low sum", w.extreme_low_sum,
                                   f"sum {total} vs typical {mean_total:.0f}"))

        odd = sum(1 for v in values if v % 2)
        if k >= 4 and abs(odd - k / 2) <= 0.5:
            hits.append(FeatureHit("balanced odd/even", w.balanced_parity,
                                   f"{odd} odd / {k - odd} even"))

        if values == list(range(1, k + 1)):
            hits.append(FeatureHit("1,2,3,...,k", w.first_n_numbers,
                                   "famously picked by thousands of players every draw"))

        if self.recent_numbers:
            recent = sum(1 for v in values if v in self.recent_numbers)
            if recent:
                hits.append(FeatureHit("recently drawn numbers", w.recently_drawn * recent,
                                       f"{recent} number(s) drawn recently - temporarily under-bet"))

        return hits

    def log_weight(self, combination: Sequence[int]) -> float:
        """Total log-weight for a combination."""
        return sum(h.weight for h in self.features(combination))

    # -- normalisation ---------------------------------------------------

    def _cache_key(self) -> tuple:
        """Identity of the (game, weights, recency) combination for caching."""
        cfg = self.config
        return (
            cfg.name, cfg.main_pool, cfg.main_pick, cfg.slip_columns,
            dataclasses.astuple(self.weights),
            tuple(sorted(self.recent_numbers)),
            self._calibration_samples, self._seed,
        )

    def _baseline_weight(self) -> float:
        """Mean exponentiated weight over uniformly random combinations.

        Estimated by Monte Carlo, then cached both on the instance and in a
        module-level table.  The module-level cache matters: callers that
        construct a fresh model per draw (a backtest loop, for instance)
        would otherwise repeat tens of thousands of samples every time,
        which made the unpopular-picking strategy several thousand times
        slower than every other strategy.
        """
        if self._baseline is not None:
            return self._baseline

        key = self._cache_key()
        cached = _BASELINE_CACHE.get(key)
        if cached is not None:
            self._baseline = cached
            return cached

        rng = random.Random(self._seed)
        cfg = self.config
        total = 0.0
        for _ in range(self._calibration_samples):
            combo = random_combination(cfg.main_pool, cfg.main_pick, rng)
            total += math.exp(self.log_weight(combo))
        baseline = total / self._calibration_samples
        self._baseline = baseline
        _BASELINE_CACHE[key] = baseline
        return baseline

    def multiplier(self, combination: Sequence[int]) -> float:
        """How many times more often than chance players pick this combination.

        ``1.0`` means average.  ``3.0`` means roughly three times as many
        players hold this combination as would if everyone picked at
        random — so a jackpot would be split about three times as many
        ways.
        """
        return math.exp(self.log_weight(combination)) / self._baseline_weight()

    def effective_multiplier(self, combination: Sequence[int]) -> float:
        """Popularity multiplier after accounting for quick-pick dilution.

        Machine-picked tickets are uniform, so they wash out conscious
        selection.  With 70% quick picks, a combination that conscious
        players favour 3x is only about 1.6x over-represented in the real
        ticket pool.  This is the number that actually drives your payout,
        and it is why the honest version of this strategy promises less
        than the lottery-systems industry claims.
        """
        f = self.weights.quickpick_share
        return f + (1.0 - f) * self.multiplier(combination)

    def explain(self, combination: Sequence[int]) -> str:
        """Human-readable breakdown of why a combination scores as it does."""
        hits = sorted(self.features(combination), key=lambda h: -abs(h.weight))
        lines = [f"Combination {tuple(sorted(combination))}"]
        lines.append(f"  raw popularity multiplier      : {self.multiplier(combination):.3f}x")
        lines.append(f"  after quick-pick dilution      : {self.effective_multiplier(combination):.3f}x")
        if not hits:
            lines.append("  no behavioural features fired - this looks like an unremarkable pick")
            return "\n".join(lines)
        lines.append("  contributing features:")
        for hit in hits:
            arrow = "+" if hit.weight >= 0 else "-"
            detail = f"  ({hit.detail})" if hit.detail else ""
            lines.append(f"    {arrow} {hit.name:<28} {hit.weight:+.3f}{detail}")
        return "\n".join(lines)

    # -- calibration ------------------------------------------------------

    def calibrate_from_winner_counts(
        self,
        observations: Iterable[tuple[Sequence[int], int, int]],
        *,
        learning_rate: float = 0.05,
        iterations: int = 200,
    ) -> dict[str, float]:
        """Fit the quick-pick share to observed jackpot-winner counts.

        ``observations`` yields ``(winning_combination, n_jackpot_winners,
        tickets_sold)``.  Winner counts are the only public signal of pick
        popularity — operators publish them, and a draw whose combination
        the model calls popular should show more co-winners.

        Fits only ``quickpick_share`` by gradient descent on Poisson
        log-likelihood, because that single parameter carries most of the
        practical effect and the data are far too sparse to identify the
        full weight vector.
        """
        records = [
            (self.multiplier(combo), winners, sold)
            for combo, winners, sold in observations
        ]
        if not records:
            raise ValueError("no observations supplied")

        space = comb(self.config.main_pool, self.config.main_pick)
        f = self.weights.quickpick_share

        for _ in range(iterations):
            gradient = 0.0
            for mult, winners, sold in records:
                base = sold / space
                lam = base * (f + (1 - f) * mult)
                if lam <= 0:
                    continue
                d_lam = base * (1 - mult)
                gradient += (winners / lam - 1.0) * d_lam
            f += learning_rate * gradient / len(records)
            f = min(0.99, max(0.0, f))

        self.weights.quickpick_share = f
        return {"quickpick_share": f, "observations": float(len(records))}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _longest_run(values: Sequence[int]) -> int:
    """Length of the longest run of consecutive integers."""
    best = current = 1
    for a, b in zip(values, values[1:]):
        current = current + 1 if b == a + 1 else 1
        best = max(best, current)
    return best


def _is_arithmetic(values: Sequence[int]) -> bool:
    """Whether the values form an arithmetic progression with step > 1."""
    if len(values) < 3:
        return False
    step = values[1] - values[0]
    if step <= 1:
        return False
    return all(b - a == step for a, b in zip(values, values[1:]))


def _is_slip_diagonal(values: Sequence[int], columns: int) -> bool:
    """Whether the numbers trace a diagonal on a ``columns``-wide bet slip."""
    if len(values) < 3:
        return False
    rows = [(v - 1) // columns for v in values]
    cols = [(v - 1) % columns for v in values]
    if len(set(rows)) != len(rows):
        return False
    row_step = rows[1] - rows[0]
    col_step = cols[1] - cols[0]
    if abs(col_step) != 1 or row_step == 0:
        return False
    return all(
        r - pr == row_step and c - pc == col_step
        for pr, r, pc, c in zip(rows, rows[1:], cols, cols[1:])
    )


# ---------------------------------------------------------------------------
# Sharing mathematics
# ---------------------------------------------------------------------------


def expected_cowinners(
    tickets_sold: int,
    jackpot_probability: float,
    popularity_multiplier: float = 1.0,
) -> float:
    """Expected number of *other* tickets holding the winning combination.

    The standard model: the count of other jackpot-winning tickets is
    Poisson with mean ``tickets_sold * p * multiplier``.
    """
    return max(0.0, tickets_sold * jackpot_probability * popularity_multiplier)


def share_factor(expected_others: float) -> float:
    """Expected fraction of the jackpot you keep, given you have won.

    If the number of *other* winners is Poisson with mean ``lam``, your
    share is ``1 / (1 + others)`` and the expectation has the closed form
    ``(1 - e**-lam) / lam``.

    This is the term that quietly destroys most "the jackpot is huge, it
    must be worth playing" arguments: a jackpot big enough to draw a crowd
    is a jackpot you will probably be splitting.
    """
    if expected_others <= 0:
        return 1.0
    if expected_others < 1e-9:
        return 1.0 - expected_others / 2
    return (1.0 - math.exp(-expected_others)) / expected_others
