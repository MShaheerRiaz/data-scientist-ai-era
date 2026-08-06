"""Statistical audit of a draw history.

This module answers one question: **is there any detectable structure in
this lottery's past results?**  It is the honest core of the toolkit.

Two things are worth understanding before reading the output.

First, a battery of tests on random data produces small p-values by
chance.  Run 49 per-ball tests at alpha = 0.05 and you should *expect*
about 2.5 "significant" balls in a perfectly fair game.  Every multi-test
routine here therefore reports Benjamini-Hochberg adjusted q-values, and
:func:`audit` corrects across the battery as a whole.

Second, and more important: even a genuinely biased machine is nearly
undetectable at realistic sample sizes.  :func:`power_analysis` quantifies
this, and it is the single most useful function in the module — it tells
you what size of bias your data could even *see*.  For a 6/49 game with
3,000 draws of history, the answer is roughly a 20% deviation.  Real
physical ball bias is an order of magnitude smaller than that.  So a clean
audit does not prove fairness; it proves the bias is smaller than your
data can resolve, which is a much weaker statement, and is not something
you can bet on.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Optional, Sequence

from . import mathx as M
from .combinatorics import comb, sum_distribution
from .config import BonusMode, LotteryConfig
from .data import DrawHistory

__all__ = [
    "TestResult",
    "BallStat",
    "FairnessReport",
    "ball_frequency_test",
    "per_ball_tests",
    "gap_test",
    "repeat_test",
    "serial_persistence_test",
    "pair_cooccurrence_test",
    "sum_distribution_test",
    "parity_test",
    "runs_test",
    "duplicate_combination_test",
    "power_analysis",
    "audit",
]

ALPHA = 0.05


@dataclass
class TestResult:
    """Outcome of a single statistical test."""

    name: str
    statistic: float
    pvalue: float
    df: Optional[int] = None
    detail: str = ""
    interpretation: str = ""
    qvalue: Optional[float] = None

    @property
    def significant(self) -> bool:
        """Whether the FDR-adjusted p-value clears the 0.05 threshold."""
        return (self.qvalue if self.qvalue is not None else self.pvalue) < ALPHA

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        mark = "FLAG" if self.significant else "ok"
        q = f" q={self.qvalue:.4f}" if self.qvalue is not None else ""
        return f"[{mark:4s}] {self.name:<34} stat={self.statistic:10.3f} p={self.pvalue:.4f}{q}"


@dataclass
class BallStat:
    """Per-ball summary used by the frequency audit."""

    ball: int
    count: int
    expected: float
    pvalue: float
    qvalue: float
    ci_low: float
    ci_high: float
    posterior_mean: float
    shrunk_lift: float

    @property
    def lift(self) -> float:
        """Raw observed frequency relative to expectation (1.0 = exactly par)."""
        return self.count / self.expected if self.expected else float("nan")


# ---------------------------------------------------------------------------
# Individual tests
# ---------------------------------------------------------------------------


def ball_frequency_test(history: DrawHistory) -> TestResult:
    """Chi-square goodness-of-fit on how often each ball has appeared.

    The headline fairness test, and the one every "hot numbers" website
    implicitly relies on without ever running it.

    There is a correction here that naive implementations miss.  Because a
    draw takes ``k`` balls *without replacement*, the per-ball indicators
    within a draw are negatively correlated, with covariance
    ``-p(1-p)/(pool-1)``.  Working through the algebra, the raw Pearson
    statistic is distributed as ``[(pool-k)/(pool-1)] * chi2(pool-1)``
    rather than plain ``chi2(pool-1)``.  Comparing the unscaled statistic
    against ``chi2(pool-1)`` makes the test badly conservative — for a 6/49
    game it fires at roughly 1% instead of 5%, so it misses real bias.
    Multiplying by ``(pool-1)/(pool-k)`` restores calibration.
    """
    cfg = history.config
    counts = history.main_counts()[1:]
    n_draws = history.n_draws
    pool, pick = cfg.main_pool, cfg.main_pick
    expected = n_draws * pick / pool

    if n_draws == 0 or expected <= 0:
        return TestResult("ball frequency (chi-square)", 0.0, 1.0, pool - 1,
                          detail="no draws supplied")

    raw = sum((c - expected) ** 2 / expected for c in counts)
    stat = raw * (pool - 1) / (pool - pick)
    df = pool - 1
    p = M.chi2_sf(stat, df)

    hottest = max(range(pool), key=lambda i: counts[i]) + 1
    coldest = min(range(pool), key=lambda i: counts[i]) + 1
    detail = (
        f"{n_draws} draws, expected {expected:.1f} appearances per ball; "
        f"hottest {hottest} ({counts[hottest - 1]}), coldest {coldest} ({counts[coldest - 1]})"
    )
    interp = (
        "Ball frequencies are consistent with a fair draw."
        if p >= ALPHA else
        "Ball frequencies deviate more than chance comfortably explains - worth a closer look."
    )
    return TestResult("ball frequency (chi-square)", stat, p, df, detail, interp)


def per_ball_tests(history: DrawHistory, prior_strength: float = 0.0) -> list[BallStat]:
    """Test each ball individually, with FDR control and Bayesian shrinkage.

    The ``shrunk_lift`` column is the one to read.  Raw "hot ball" lifts are
    mostly noise; shrinking them toward 1.0 under a Dirichlet prior shows
    how little signal survives once you account for how much of the spread
    is expected anyway.  ``prior_strength`` of 0 selects a sensible default
    (one pseudo-draw's worth of evidence per ball).
    """
    cfg = history.config
    counts = history.main_counts()
    n_draws = history.n_draws
    pool, pick = cfg.main_pool, cfg.main_pick
    p0 = pick / pool
    expected = n_draws * p0

    raw_p = [M.binom_test(counts[b], n_draws, p0) if n_draws else 1.0
             for b in range(1, pool + 1)]
    qvals = M.benjamini_hochberg(raw_p)

    # Dirichlet-multinomial posterior. alpha0 spread evenly over the pool.
    alpha0 = prior_strength if prior_strength > 0 else float(pool)
    prior_each = alpha0 / pool
    total_appearances = n_draws * pick

    stats: list[BallStat] = []
    for b in range(1, pool + 1):
        count = counts[b]
        post_mean = (count + prior_each) / (total_appearances + alpha0) if total_appearances else 1 / pool
        lo, hi = M.wilson_interval(count, n_draws, 0.95) if n_draws else (0.0, 1.0)
        stats.append(BallStat(
            ball=b,
            count=count,
            expected=expected,
            pvalue=raw_p[b - 1],
            qvalue=qvals[b - 1],
            ci_low=lo * pool / pick if pick else 0.0,
            ci_high=hi * pool / pick if pick else 0.0,
            posterior_mean=post_mean,
            shrunk_lift=post_mean * pool,
        ))
    return stats


def gap_test(history: DrawHistory, max_gap_bins: int = 12) -> TestResult:
    """Are the waiting times between a ball's appearances geometric?

    A machine that favours a ball produces short gaps; one that somehow
    "remembers" produces clustered gaps.  Under fairness the gap between
    consecutive appearances of any given ball is geometric with
    ``p = pick / pool``, regardless of which ball it is, so all balls' gaps
    can be pooled into one well-powered test.
    """
    cfg = history.config
    pool, pick = cfg.main_pool, cfg.main_pick
    p = pick / pool

    last_seen: dict[int, int] = {}
    gaps: list[int] = []
    for t, draw in enumerate(history.draws):
        for value in draw.main:
            if value in last_seen:
                gaps.append(t - last_seen[value])
            last_seen[value] = t

    if len(gaps) < 50:
        return TestResult("gap distribution (chi-square)", 0.0, 1.0,
                          detail=f"only {len(gaps)} gaps observed - too few to test")

    bins = max_gap_bins
    observed = [0] * bins
    for g in gaps:
        observed[min(g, bins) - 1] += 1

    n = len(gaps)
    expected = []
    for i in range(bins - 1):
        expected.append(n * p * (1 - p) ** i)
    expected.append(n * (1 - p) ** (bins - 1))  # tail bin absorbs the rest

    # Merge any bin with a tiny expectation into its neighbour to keep the
    # chi-square approximation honest.
    merged_o: list[float] = []
    merged_e: list[float] = []
    acc_o = acc_e = 0.0
    for o, e in zip(observed, expected):
        acc_o += o
        acc_e += e
        if acc_e >= 5.0:
            merged_o.append(acc_o)
            merged_e.append(acc_e)
            acc_o = acc_e = 0.0
    if acc_e > 0:
        if merged_e:
            merged_o[-1] += acc_o
            merged_e[-1] += acc_e
        else:
            merged_o.append(acc_o)
            merged_e.append(acc_e)

    stat = sum((o - e) ** 2 / e for o, e in zip(merged_o, merged_e) if e > 0)
    df = max(1, len(merged_e) - 1)
    pv = M.chi2_sf(stat, df)
    return TestResult(
        "gap distribution (chi-square)", stat, pv, df,
        detail=f"{n} gaps pooled across {pool} balls, {len(merged_e)} bins after merging",
        interpretation=("Waiting times look geometric, as a memoryless draw requires."
                        if pv >= ALPHA else
                        "Waiting times depart from the memoryless pattern."),
    )


def repeat_test(history: DrawHistory) -> TestResult:
    """How many numbers carry over from one draw to the next?

    Under fairness the overlap between consecutive draws is hypergeometric.
    This is a direct, interpretable probe of draw-to-draw dependence — the
    thing you would need to exist for "last week's numbers" to matter.
    """
    cfg = history.config
    pool, pick = cfg.main_pool, cfg.main_pick
    draws = history.draws
    if len(draws) < 30:
        return TestResult("consecutive-draw overlap", 0.0, 1.0,
                          detail=f"only {len(draws)} draws - too few to test")

    observed = [0] * (pick + 1)
    for a, b in zip(draws, draws[1:]):
        observed[len(set(a.main) & set(b.main))] += 1

    trials = len(draws) - 1
    expected = [
        trials * comb(pick, j) * comb(pool - pick, pick - j) / comb(pool, pick)
        for j in range(pick + 1)
    ]

    merged_o: list[float] = []
    merged_e: list[float] = []
    acc_o = acc_e = 0.0
    for o, e in zip(observed, expected):
        acc_o += o
        acc_e += e
        if acc_e >= 5.0:
            merged_o.append(acc_o)
            merged_e.append(acc_e)
            acc_o = acc_e = 0.0
    if acc_e > 0 and merged_e:
        merged_o[-1] += acc_o
        merged_e[-1] += acc_e

    if len(merged_e) < 2:
        return TestResult("consecutive-draw overlap", 0.0, 1.0,
                          detail="not enough distinct overlap categories to test")

    stat = sum((o - e) ** 2 / e for o, e in zip(merged_o, merged_e) if e > 0)
    df = len(merged_e) - 1
    pv = M.chi2_sf(stat, df)
    mean_overlap = sum(j * observed[j] for j in range(pick + 1)) / trials
    theory_overlap = pick * pick / pool
    return TestResult(
        "consecutive-draw overlap", stat, pv, df,
        detail=f"mean carry-over {mean_overlap:.3f} vs theoretical {theory_overlap:.3f}",
        interpretation=("Consecutive draws are independent, as expected."
                        if pv >= ALPHA else
                        "Consecutive draws show more structure than independence predicts."),
    )


def serial_persistence_test(history: DrawHistory) -> TestResult:
    """Does a ball appearing this draw make it likelier to appear next draw?

    Pools a 2x2 contingency table over every ball and every consecutive
    pair of draws.  If "hot" balls were real in any usable sense, this test
    would fire.
    """
    cfg = history.config
    pool = cfg.main_pool
    draws = history.draws
    if len(draws) < 30:
        return TestResult("serial persistence (2x2)", 0.0, 1.0,
                          detail=f"only {len(draws)} draws - too few to test")

    a = b = c = d = 0
    for prev, nxt in zip(draws, draws[1:]):
        in_prev = set(prev.main)
        in_next = set(nxt.main)
        for ball in range(1, pool + 1):
            p_in, n_in = ball in in_prev, ball in in_next
            if p_in and n_in:
                a += 1
            elif p_in and not n_in:
                b += 1
            elif not p_in and n_in:
                c += 1
            else:
                d += 1

    n = a + b + c + d
    row1, row2 = a + b, c + d
    col1, col2 = a + c, b + d
    if min(row1, row2, col1, col2) == 0:
        return TestResult("serial persistence (2x2)", 0.0, 1.0, detail="degenerate table")

    # Chi-square with Yates continuity correction.
    stat = n * max(0.0, abs(a * d - b * c) - n / 2.0) ** 2 / (row1 * row2 * col1 * col2)
    pv = M.chi2_sf(stat, 1)
    p_repeat = a / row1
    p_base = col1 / n
    return TestResult(
        "serial persistence (2x2)", stat, pv, 1,
        detail=(f"P(appears | appeared last draw) = {p_repeat:.4f} vs "
                f"base rate {p_base:.4f}"),
        interpretation=("No carry-over effect: a ball's history does not predict its next draw."
                        if pv >= ALPHA else
                        "A carry-over effect is present."),
    )


def pair_cooccurrence_test(
    history: DrawHistory,
    reps: int = 2000,
    seed: int = 12345,
) -> TestResult:
    """Do particular *pairs* of balls turn up together too often?

    The pair counts are not independent, so the usual chi-square reference
    distribution does not apply.  The null is therefore built by Monte
    Carlo: simulate fair histories of the same size and see how extreme the
    real statistic looks against them.
    """
    cfg = history.config
    pool, pick = cfg.main_pool, cfg.main_pick
    draws = history.draws
    if len(draws) < 100:
        return TestResult("pair co-occurrence (Monte Carlo)", 0.0, 1.0,
                          detail=f"only {len(draws)} draws - too few to test")

    n_draws = len(draws)
    expected = n_draws * comb(pool - 2, pick - 2) / comb(pool, pick)

    def statistic(sequences: Sequence[Sequence[int]]) -> float:
        counts: dict[tuple[int, int], int] = {}
        for combo in sequences:
            values = sorted(combo)
            for i in range(len(values)):
                for j in range(i + 1, len(values)):
                    key = (values[i], values[j])
                    counts[key] = counts.get(key, 0) + 1
        total_pairs = comb(pool, 2)
        seen = sum((c - expected) ** 2 for c in counts.values())
        missing = (total_pairs - len(counts)) * expected ** 2
        return (seen + missing) / expected

    observed_stat = statistic([d.main for d in draws])

    rng = random.Random(seed)
    pool_values = list(range(1, pool + 1))
    null = []
    for _ in range(reps):
        sim = [rng.sample(pool_values, pick) for _ in range(n_draws)]
        null.append(statistic(sim))

    at_least = sum(1 for v in null if v >= observed_stat)
    pv = (at_least + 1) / (reps + 1)
    null_mean = M.mean(null)
    return TestResult(
        "pair co-occurrence (Monte Carlo)", observed_stat, pv,
        detail=(f"statistic {observed_stat:.1f} vs null mean {null_mean:.1f} "
                f"over {reps} simulated histories"),
        interpretation=("Pair frequencies look like chance."
                        if pv >= ALPHA else
                        "Some pairs co-occur more than chance explains."),
    )


def sum_distribution_test(history: DrawHistory, target_bins: int = 20) -> TestResult:
    """Chi-square test of draw sums against their exact distribution.

    Sensitive to bias that favours a whole region of the pool (low numbers,
    say) even when no individual ball stands out.

    A Kolmogorov-Smirnov test is the tempting choice here and it is the
    wrong one: draw sums are heavily tied (2,000 draws of a 6/49 game land
    on ~175 distinct sums), and KS assumes a continuous distribution.
    Scoring every tied observation against the inclusive CDF inflates the
    statistic by each atom's mass, which drove the false-positive rate to
    21% in calibration.  Binning against exact probabilities and using a
    chi-square instead is correctly calibrated, because each draw
    contributes one independent multinomial observation.
    """
    cfg = history.config
    pool, pick = cfg.main_pool, cfg.main_pick
    draws = history.draws
    if len(draws) < 30:
        return TestResult("draw-sum distribution (chi-square)", 0.0, 1.0,
                          detail=f"only {len(draws)} draws - too few to test")

    dist = sum_distribution(pool, pick)
    grand = comb(pool, pick)
    ordered = sorted(dist)
    n = len(draws)

    # Build contiguous bins whose expected counts are all at least 5.
    floor_count = max(5.0, n / (target_bins * 2))
    edges: list[int] = []
    probs: list[float] = []
    acc_p = 0.0
    for s in ordered:
        acc_p += dist[s] / grand
        if acc_p * n >= floor_count:
            edges.append(s)
            probs.append(acc_p)
            acc_p = 0.0
    if acc_p > 0:
        if edges:
            edges[-1] = ordered[-1]
            probs[-1] += acc_p
        else:
            edges.append(ordered[-1])
            probs.append(acc_p)

    if len(probs) < 3:
        return TestResult("draw-sum distribution (chi-square)", 0.0, 1.0,
                          detail="too few usable bins")

    observed = [0] * len(edges)
    for draw in draws:
        total = draw.total
        for i, upper in enumerate(edges):
            if total <= upper:
                observed[i] += 1
                break
        else:
            observed[-1] += 1

    expected = [n * p for p in probs]
    stat = sum((o - e) ** 2 / e for o, e in zip(observed, expected) if e > 0)
    df = len(expected) - 1
    pv = M.chi2_sf(stat, df)

    observed_mean = M.mean([float(d.total) for d in draws])
    theory_mean = pick * (pool + 1) / 2
    return TestResult(
        "draw-sum distribution (chi-square)", stat, pv, df,
        detail=(f"mean sum {observed_mean:.1f} vs theoretical {theory_mean:.1f}, "
                f"{len(expected)} bins"),
        interpretation=("Draw sums follow the exact theoretical distribution."
                        if pv >= ALPHA else
                        "Draw sums deviate from theory - suggests a regional bias in the pool."),
    )


def parity_test(history: DrawHistory) -> TestResult:
    """Odd/even split of each draw against its exact distribution."""
    cfg = history.config
    pool, pick = cfg.main_pool, cfg.main_pick
    draws = history.draws
    if len(draws) < 30:
        return TestResult("odd/even split (chi-square)", 0.0, 1.0,
                          detail=f"only {len(draws)} draws - too few to test")

    n_odd = (pool + 1) // 2
    n_even = pool - n_odd
    total = comb(pool, pick)
    expected_p = [comb(n_odd, j) * comb(n_even, pick - j) / total for j in range(pick + 1)]

    observed = [0] * (pick + 1)
    for draw in draws:
        observed[draw.odd_count] += 1
    expected = [len(draws) * p for p in expected_p]

    merged_o: list[float] = []
    merged_e: list[float] = []
    acc_o = acc_e = 0.0
    for o, e in zip(observed, expected):
        acc_o += o
        acc_e += e
        if acc_e >= 5.0:
            merged_o.append(acc_o)
            merged_e.append(acc_e)
            acc_o = acc_e = 0.0
    if acc_e > 0 and merged_e:
        merged_o[-1] += acc_o
        merged_e[-1] += acc_e

    if len(merged_e) < 2:
        return TestResult("odd/even split (chi-square)", 0.0, 1.0, detail="too few categories")

    stat = sum((o - e) ** 2 / e for o, e in zip(merged_o, merged_e) if e > 0)
    df = len(merged_e) - 1
    pv = M.chi2_sf(stat, df)
    return TestResult(
        "odd/even split (chi-square)", stat, pv, df,
        detail=f"{len(draws)} draws across {len(merged_e)} parity categories",
        interpretation=("Odd/even balance is as expected."
                        if pv >= ALPHA else "Odd/even balance is off."),
    )


def runs_test(history: DrawHistory) -> TestResult:
    """Wald-Wolfowitz runs test on whether each draw's sum is above the median.

    Detects drift or cycling over time — for instance a machine whose
    behaviour changes after a ball-set swap.
    """
    draws = history.draws
    if len(draws) < 40:
        return TestResult("runs test (sum vs median)", 0.0, 1.0,
                          detail=f"only {len(draws)} draws - too few to test")

    sums = [d.total for d in draws]
    ordered = sorted(sums)
    mid = len(ordered) // 2
    median = ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2

    signs = [s > median for s in sums if s != median]
    n1 = sum(1 for s in signs if s)
    n2 = len(signs) - n1
    if n1 < 2 or n2 < 2:
        return TestResult("runs test (sum vs median)", 0.0, 1.0, detail="degenerate split")

    runs = 1 + sum(1 for a, b in zip(signs, signs[1:]) if a != b)
    n = n1 + n2
    mu = 2 * n1 * n2 / n + 1
    var = (2 * n1 * n2 * (2 * n1 * n2 - n)) / (n * n * (n - 1))
    if var <= 0:
        return TestResult("runs test (sum vs median)", 0.0, 1.0, detail="zero variance")

    z = (runs - mu) / math.sqrt(var)
    pv = 2 * M.norm_sf(abs(z))
    return TestResult(
        "runs test (sum vs median)", z, pv,
        detail=f"{runs} runs observed, {mu:.1f} expected",
        interpretation=("No drift or cycling over time."
                        if pv >= ALPHA else
                        "Results are not stationary over time - check for a machine or ball-set change."),
    )


def duplicate_combination_test(history: DrawHistory) -> TestResult:
    """Are there more repeated combinations than the birthday problem predicts?

    Repeats feel astonishing and are usually nothing: with D draws there
    are D(D-1)/2 chances to collide, so occasional repeats are expected.
    """
    cfg = history.config
    draws = history.draws
    space = comb(cfg.main_pool, cfg.main_pick)
    n = len(draws)
    if n < 2:
        return TestResult("duplicate combinations (Poisson)", 0.0, 1.0, detail="too few draws")

    observed = len(history.duplicates())
    lam = n * (n - 1) / 2 / space
    # One-sided: are there MORE duplicates than expected?
    pv = M.poisson_sf(observed - 1, lam) if observed > 0 else 1.0
    return TestResult(
        "duplicate combinations (Poisson)", float(observed), pv,
        detail=f"{observed} repeats observed, {lam:.4f} expected across {n} draws",
        interpretation=("Repeat count is unremarkable."
                        if pv >= ALPHA else
                        "More repeated combinations than chance predicts."),
    )


# ---------------------------------------------------------------------------
# Power
# ---------------------------------------------------------------------------


def power_analysis(
    config: LotteryConfig,
    n_draws: int,
    *,
    power: float = 0.80,
    alpha: float = 0.05,
    bonferroni: bool = True,
    lifts: Sequence[float] = (1.05, 1.10, 1.20, 1.50, 2.00),
) -> dict[str, object]:
    """What size of bias could this much history actually detect?

    The most important calculation in the module, and the one that
    dissolves most "I found a pattern" claims.  Returns the draws required
    to detect each relative bias, and the smallest bias detectable with the
    history you have.

    Uses the standard two-proportion sample-size formula, Bonferroni-adjusted
    for testing every ball in the pool.
    """
    pool, pick = config.main_pool, config.main_pick
    p0 = pick / pool
    effective_alpha = alpha / pool if bonferroni else alpha
    z_alpha = M.norm_ppf(1 - effective_alpha / 2)
    z_beta = M.norm_ppf(power)

    def draws_needed(lift: float) -> float:
        p1 = min(0.999999, p0 * lift)
        delta = abs(p1 - p0)
        if delta <= 0:
            return math.inf
        numerator = (z_alpha * math.sqrt(p0 * (1 - p0)) + z_beta * math.sqrt(p1 * (1 - p1))) ** 2
        return numerator / (delta ** 2)

    requirements = {lift: draws_needed(lift) for lift in lifts}

    # Invert: smallest detectable lift given n_draws.
    detectable = math.inf
    if n_draws > 0:
        lo, hi = 1.0 + 1e-9, 10.0
        for _ in range(200):
            mid = (lo + hi) / 2
            if draws_needed(mid) > n_draws:
                lo = mid
            else:
                hi = mid
        detectable = hi

    return {
        "n_draws": n_draws,
        "p_null": p0,
        "alpha": alpha,
        "effective_alpha": effective_alpha,
        "power": power,
        "draws_required": requirements,
        "min_detectable_lift": detectable,
        "note": (
            f"With {n_draws} draws you can only detect a ball running "
            f"{(detectable - 1) * 100:.1f}% hot or better. Documented physical ball "
            f"bias is far smaller than this, so a clean audit at this sample size is "
            f"weak evidence of fairness - and no basis for picking numbers."
        ) if math.isfinite(detectable) else "Insufficient data for a power calculation.",
    }


# ---------------------------------------------------------------------------
# The full battery
# ---------------------------------------------------------------------------


@dataclass
class FairnessReport:
    """Everything the audit found."""

    config: LotteryConfig
    n_draws: int
    tests: list[TestResult] = field(default_factory=list)
    ball_stats: list[BallStat] = field(default_factory=list)
    power: dict[str, object] = field(default_factory=dict)
    flagged_balls: list[BallStat] = field(default_factory=list)

    @property
    def any_flag(self) -> bool:
        """Whether any battery-level test survived FDR correction."""
        return any(t.significant for t in self.tests)

    def verdict(self) -> str:
        """A plain-language bottom line."""
        if not self.any_flag and not self.flagged_balls:
            return (
                "No detectable departure from fairness. Note this is a statement about "
                "the limits of the data, not proof of randomness - see the power analysis."
            )
        parts = []
        if self.flagged_balls:
            names = ", ".join(str(b.ball) for b in self.flagged_balls[:8])
            parts.append(f"{len(self.flagged_balls)} ball(s) flagged after FDR correction: {names}")
        flagged_tests = [t.name for t in self.tests if t.significant]
        if flagged_tests:
            parts.append("battery tests flagged: " + ", ".join(flagged_tests))
        return ("Possible structure detected. " + "; ".join(parts) +
                ". Confirm on held-out draws before believing it - and see the power analysis "
                "for whether an effect this size is even plausible.")

    def to_text(self, top_balls: int = 10) -> str:
        """Full report as formatted text."""
        lines: list[str] = []
        lines.append("=" * 78)
        lines.append(f"FAIRNESS AUDIT  -  {self.config.name}")
        lines.append(f"{self.n_draws} draws | {self.config.describe()}")
        lines.append("=" * 78)
        lines.append("")
        lines.append("BATTERY")
        for test in self.tests:
            lines.append("  " + str(test))
            if test.detail:
                lines.append(f"         {test.detail}")
            if test.interpretation:
                lines.append(f"         -> {test.interpretation}")
        lines.append("")

        lines.append(f"PER-BALL EXTREMES (top {top_balls} by |lift - 1|)")
        lines.append(f"  {'ball':>5}{'count':>8}{'expect':>9}{'lift':>8}"
                     f"{'shrunk':>9}{'p':>9}{'q':>9}")
        ranked = sorted(self.ball_stats, key=lambda s: -abs(s.lift - 1.0))[:top_balls]
        for s in ranked:
            lines.append(f"  {s.ball:>5}{s.count:>8}{s.expected:>9.1f}{s.lift:>8.3f}"
                         f"{s.shrunk_lift:>9.3f}{s.pvalue:>9.4f}{s.qvalue:>9.4f}")
        lines.append("")
        lines.append("  'lift' is raw observed/expected. 'shrunk' applies a Dirichlet prior -")
        lines.append("  note how much closer to 1.000 it sits. That gap is the noise you would")
        lines.append("  otherwise mistake for a hot number.")
        lines.append("")

        if self.power:
            lines.append("POWER ANALYSIS")
            lines.append(f"  Smallest detectable bias with {self.power['n_draws']} draws: "
                         f"{(float(self.power['min_detectable_lift']) - 1) * 100:.1f}% lift")
            lines.append("  Draws required to detect a given bias at 80% power:")
            for lift, needed in sorted(self.power["draws_required"].items()):  # type: ignore[union-attr]
                years = needed / 104.0  # two draws a week
                lines.append(f"    {(lift - 1) * 100:>5.0f}% hot ball -> {needed:>12,.0f} draws "
                             f"({years:,.0f} years at 2 draws/week)")
            lines.append("")

        lines.append("VERDICT")
        for chunk in _wrap(self.verdict(), 74):
            lines.append("  " + chunk)
        lines.append("=" * 78)
        return "\n".join(lines)


def _wrap(text: str, width: int) -> list[str]:
    """Minimal word wrapper so reports read well in a terminal."""
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    length = 0
    for word in words:
        if length + len(word) + (1 if current else 0) > width and current:
            lines.append(" ".join(current))
            current, length = [word], len(word)
        else:
            current.append(word)
            length += len(word) + (1 if len(current) > 1 else 0)
    if current:
        lines.append(" ".join(current))
    return lines


def audit(
    history: DrawHistory,
    *,
    pair_reps: int = 500,
    include_pair_test: bool = True,
) -> FairnessReport:
    """Run the whole battery and correct for multiple testing across it."""
    tests: list[TestResult] = [
        ball_frequency_test(history),
        gap_test(history),
        repeat_test(history),
        serial_persistence_test(history),
        sum_distribution_test(history),
        parity_test(history),
        runs_test(history),
        duplicate_combination_test(history),
    ]
    if include_pair_test:
        tests.append(pair_cooccurrence_test(history, reps=pair_reps))

    # FDR across the battery, so a single lucky test does not read as a finding.
    qvals = M.benjamini_hochberg([t.pvalue for t in tests])
    for test, q in zip(tests, qvals):
        test.qvalue = q
        # Each test writes its interpretation from its own raw p-value, before it
        # knows how many siblings it has. Reconcile the wording with the
        # corrected verdict, otherwise a test can read "[ok]" while its prose
        # announces a finding - which is precisely the multiple-testing error
        # the correction exists to prevent.
        if test.pvalue < ALPHA <= q:
            test.interpretation = (
                f"Raw p = {test.pvalue:.4f} looks notable, but across {len(tests)} tests "
                f"this is expected by chance (FDR-adjusted q = {q:.4f}). Not a finding."
            )

    ball_stats = per_ball_tests(history)
    flagged = [s for s in ball_stats if s.qvalue < ALPHA]

    return FairnessReport(
        config=history.config,
        n_draws=history.n_draws,
        tests=tests,
        ball_stats=ball_stats,
        power=power_analysis(history.config, history.n_draws),
        flagged_balls=flagged,
    )
