"""Digit games: 2D, 3D, Pick 3/4, 4D.

Digit games differ from ball draws in a way that matters for analysis:
positions are drawn *with* replacement, so under fairness every position
is independent and uniform on 0-9.  That makes them much easier to audit —
no hypergeometric corrections, no without-replacement covariance — and it
makes the house edge a pure function of the quoted payout.

**Myanmar 2D specifically.**  This game is not a ball draw at all.  The
winning number is derived from published Thai stock market figures.  The
description almost universally repeated — "the last two digits of the SET
closing index" — is **wrong**.  The actual rule, verified against twelve
independent historical records from two unrelated data sources, is:

    top digit    = hundredths digit of the SET index   (floor(S*100) mod 10)
    bottom digit = units digit of the integer part of
                   total trading value in millions of baht (floor(V) mod 10)
    2D           = top * 10 + bottom

Worked example, 21 November 2024, 12:01 slot: SET index 1443.7\\ **9**,
trading value 24,22\\ **1**.65 million baht, published result **91**.  The
folklore rule would have given 43.

Two consequences follow, and both are analytically important.

*The right null hypothesis is uniform.*  Benford's Law governs *leading*
digits and decays extremely fast across digit positions.  The digits used
here are the 5th and 6th significant figures of their respective
quantities, where Benford deviation is negligible.  So uniform on 00-99 is
correct, and :func:`digit_audit` tests exactly that.

*The exploitable weakness is not the market.*  The SET closes via a
random-timed auction between 16:35 and 16:40 precisely to frustrate
closing-price manipulation, and the index's hundredths digit is far too
sensitive to aim at.  The soft spot is that settlement depends on a
*private scraper's* timestamped capture rather than an audited exchange
publication.  Every documented lottery fraud in history — Hot Lotto, the
Triple Six Fix, Ronald Harris — was an attack on the operational chain,
never on the entropy source.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

from . import mathx as M
from .config import DigitGameConfig

__all__ = [
    "derive_myanmar_2d",
    "DigitDraw",
    "DigitHistory",
    "digit_audit",
    "DigitAuditReport",
    "position_uniformity",
    "joint_uniformity",
    "digit_independence",
    "serial_digit_test",
    "round_number_clustering",
    "house_edge_table",
    "digit_popularity",
    "kelly_for_digit_game",
]


# ---------------------------------------------------------------------------
# Myanmar 2D derivation
# ---------------------------------------------------------------------------


def derive_myanmar_2d(set_index: float, trading_value: float) -> int:
    """Compute the Myanmar 2D number from Thai SET figures.

    ``set_index`` is the SET index quoted to two decimals (e.g. ``1443.79``);
    ``trading_value`` is total turnover in millions of baht (e.g.
    ``24221.65``).  Returns the two-digit result as an integer 0-99.

    Note the deliberate design: both digits are the fastest-churning
    available in their series.  Using the *integer* part of the index
    instead would move only a few points a day and produce heavily
    autocorrelated results.
    """
    if set_index < 0 or trading_value < 0:
        raise ValueError("SET index and trading value must be non-negative")
    top = int(math.floor(set_index * 100 + 1e-9)) % 10
    bottom = int(math.floor(trading_value + 1e-9)) % 10
    return top * 10 + bottom


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DigitDraw:
    """One digit-game result, stored as a tuple of digits."""

    digits: tuple[int, ...]
    label: str = ""

    @property
    def value(self) -> int:
        """The result as an integer."""
        return int("".join(str(d) for d in self.digits))

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return "".join(str(d) for d in self.digits)


@dataclass
class DigitHistory:
    """A sequence of digit-game results."""

    config: DigitGameConfig
    draws: list[DigitDraw] = field(default_factory=list)
    source: str = "<memory>"

    def __len__(self) -> int:
        return len(self.draws)

    @classmethod
    def from_values(
        cls,
        config: DigitGameConfig,
        values: Iterable[int | str],
        source: str = "<memory>",
    ) -> "DigitHistory":
        """Build a history from integers or zero-padded strings."""
        width = config.digits
        draws: list[DigitDraw] = []
        for value in values:
            text = str(value).strip().zfill(width)
            if len(text) != width or not text.isdigit():
                raise ValueError(f"{value!r} is not a {width}-digit result")
            draws.append(DigitDraw(tuple(int(c) for c in text)))
        return cls(config=config, draws=draws, source=source)

    @classmethod
    def from_market_data(
        cls,
        config: DigitGameConfig,
        rows: Iterable[tuple[float, float]],
        source: str = "market feed",
    ) -> "DigitHistory":
        """Build a Myanmar 2D history from ``(set_index, trading_value)`` rows."""
        values = [derive_myanmar_2d(s, v) for s, v in rows]
        return cls.from_values(config, values, source=source)

    def position_counts(self, position: int) -> list[int]:
        """Counts of digits 0-9 at one position."""
        counts = [0] * 10
        for draw in self.draws:
            counts[draw.digits[position]] += 1
        return counts

    def value_counts(self) -> dict[int, int]:
        """Counts of every full outcome."""
        counts: dict[int, int] = {}
        for draw in self.draws:
            counts[draw.value] = counts.get(draw.value, 0) + 1
        return counts


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@dataclass
class DigitTestResult:
    """One digit-game test outcome."""

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
        return (self.qvalue if self.qvalue is not None else self.pvalue) < 0.05

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        mark = "FLAG" if self.significant else "ok"
        q = f" q={self.qvalue:.4f}" if self.qvalue is not None else ""
        return f"[{mark:4s}] {self.name:<38} stat={self.statistic:9.3f} p={self.pvalue:.4f}{q}"


def position_uniformity(history: DigitHistory, position: int) -> DigitTestResult:
    """Chi-square test that one digit position is uniform on 0-9."""
    counts = history.position_counts(position)
    n = sum(counts)
    if n < 50:
        return DigitTestResult(f"position {position} uniformity", 0.0, 1.0,
                               detail=f"only {n} draws - too few")
    expected = n / 10
    stat = sum((c - expected) ** 2 / expected for c in counts)
    p = M.chi2_sf(stat, 9)
    spread = f"counts {counts}"
    return DigitTestResult(
        f"position {position} uniformity", stat, p, 9, spread,
        "Uniform, as required." if p >= 0.05 else "This digit position is not uniform.",
    )


def joint_uniformity(history: DigitHistory) -> DigitTestResult:
    """Chi-square test that the full outcome is uniform over all possibilities.

    Lower power than the per-position tests when a single position is
    skewed, but the only test that catches structure in the *combination*
    that leaves each marginal looking fine.
    """
    counts = history.value_counts()
    outcomes = history.config.outcomes
    n = len(history.draws)
    expected = n / outcomes
    if expected < 5:
        return DigitTestResult(
            "joint outcome uniformity", 0.0, 1.0,
            detail=(f"expected only {expected:.2f} per outcome across {outcomes} outcomes; "
                    f"need ~{outcomes * 5:,} draws for this test to be valid"),
            interpretation="Not enough data - rely on the per-position tests instead.",
        )
    stat = sum((counts.get(v, 0) - expected) ** 2 / expected for v in range(outcomes))
    df = outcomes - 1
    p = M.chi2_sf(stat, df)
    return DigitTestResult(
        "joint outcome uniformity", stat, p, df,
        f"{n} draws over {outcomes} outcomes",
        "Outcomes look uniform." if p >= 0.05 else "Outcome distribution is not uniform.",
    )


def digit_independence(history: DigitHistory) -> DigitTestResult:
    """Chi-square test that the first two digit positions are independent.

    For Myanmar 2D this is a genuinely meaningful check, because the two
    digits come from *different* market aggregates (a price index and a
    turnover sum).  If they were coupled, the joint distribution would be
    predictable in a way the marginals would not reveal.
    """
    cfg = history.config
    if cfg.digits < 2:
        return DigitTestResult("digit independence", 0.0, 1.0,
                               detail="single-digit game - not applicable")
    n = len(history.draws)
    if n < 200:
        return DigitTestResult("digit independence", 0.0, 1.0,
                               detail=f"only {n} draws - too few")

    table = [[0] * 10 for _ in range(10)]
    for draw in history.draws:
        table[draw.digits[0]][draw.digits[1]] += 1
    rows = [sum(r) for r in table]
    cols = [sum(table[i][j] for i in range(10)) for j in range(10)]

    stat = 0.0
    cells = 0
    for i in range(10):
        for j in range(10):
            expected = rows[i] * cols[j] / n
            if expected > 0:
                stat += (table[i][j] - expected) ** 2 / expected
                cells += 1
    df = 81
    p = M.chi2_sf(stat, df)
    return DigitTestResult(
        "digit independence (top vs bottom)", stat, p, df,
        f"{n} draws, 10x10 contingency table",
        "The two digits are independent." if p >= 0.05
        else "The two digits are coupled - worth investigating.",
    )


def serial_digit_test(history: DigitHistory, lag: int = 1) -> DigitTestResult:
    """Does one draw's outcome predict the next?

    The direct test of whether "yesterday's number" carries information.
    For a market-derived game this is more meaningful than for a ball draw,
    because the underlying series *is* autocorrelated at the level of the
    index — the question is whether that survives down to the digit used.
    """
    n = len(history.draws)
    if n < 200 + lag:
        return DigitTestResult(f"serial dependence (lag {lag})", 0.0, 1.0,
                               detail=f"only {n} draws - too few")

    table = [[0] * 10 for _ in range(10)]
    for a, b in zip(history.draws, history.draws[lag:]):
        table[a.digits[0]][b.digits[0]] += 1
    total = sum(sum(r) for r in table)
    rows = [sum(r) for r in table]
    cols = [sum(table[i][j] for i in range(10)) for j in range(10)]

    stat = 0.0
    for i in range(10):
        for j in range(10):
            expected = rows[i] * cols[j] / total
            if expected > 0:
                stat += (table[i][j] - expected) ** 2 / expected
    p = M.chi2_sf(stat, 81)
    return DigitTestResult(
        f"serial dependence (lag {lag})", stat, p, 81,
        f"{total} consecutive pairs",
        "No serial dependence - past results carry no information."
        if p >= 0.05 else "Serial dependence detected.",
    )


def round_number_clustering(history: DigitHistory) -> DigitTestResult:
    """Test for over-representation of 0 and 5 — the price-clustering signature.

    Documented digit-preference research (Harris 1991; Ikenberry and Weston
    2008) shows traded prices cluster heavily on round increments, with the
    frequency ordering 0 > 5 > others.  If a market-derived digit game
    inherited that clustering, digits 0 and 5 would be over-represented and
    the game would be genuinely, exploitably biased.

    The theoretical expectation is that aggregation destroys the effect —
    an index is a weighted sum over hundreds of constituents divided by a
    non-round divisor, which equidistributes the low-order digits.  This
    test checks that expectation instead of assuming it.
    """
    n = len(history.draws)
    if n < 100:
        return DigitTestResult("round-number clustering (0 and 5)", 0.0, 1.0,
                               detail=f"only {n} draws - too few")

    total = 0
    round_hits = 0
    for draw in history.draws:
        for digit in draw.digits:
            total += 1
            if digit in (0, 5):
                round_hits += 1

    expected_p = 0.2
    p = M.binom_test(round_hits, total, expected_p)
    observed_p = round_hits / total
    lo, hi = M.wilson_interval(round_hits, total)
    return DigitTestResult(
        "round-number clustering (0 and 5)", observed_p, p, None,
        f"{round_hits}/{total} digits are 0 or 5 ({observed_p:.4f}, 95% CI "
        f"[{lo:.4f}, {hi:.4f}], expected 0.2000)",
        "No round-number clustering - aggregation washed it out, as theory predicts."
        if p >= 0.05 else
        "Round-number clustering detected - the price-clustering effect survived aggregation.",
    )


# ---------------------------------------------------------------------------
# Economics
# ---------------------------------------------------------------------------


def house_edge_table(configs: Sequence[DigitGameConfig]) -> str:
    """Compare the economics of several digit games.

    Multi-tier games are marked, because their headline payout covers only
    the top prize and scoring them from it alone is badly misleading.
    """
    lines = [f"  {'game':<30}{'outcomes':>10}{'payout':>10}{'fair':>10}{'RTP':>8}{'edge':>8}  note"]
    for cfg in sorted(configs, key=lambda c: c.house_edge):
        note = "top prize only; RTP is full structure" if cfg.is_multi_tier else ""
        lines.append(
            f"  {cfg.name:<30}{cfg.outcomes:>10,}{cfg.payout_straight:>10,.0f}"
            f"{cfg.fair_payout:>10,.0f}{cfg.expected_return:>8.1%}{cfg.house_edge:>8.1%}  {note}"
        )
    return "\n".join(lines)


def kelly_for_digit_game(config: DigitGameConfig) -> float:
    """Kelly stake for a digit game — always negative, i.e. do not bet.

    Included because it is the cleanest possible demonstration: with a
    payout below the fair multiple there is no stake size, bankroll, or
    progression system that produces a profit.  The number is the answer to
    every "what staking plan should I use?" question.
    """
    p = 1.0 / config.outcomes
    b = config.payout_straight - 1.0
    if b <= 0:
        return 0.0
    return (p * b - (1 - p)) / b


# ---------------------------------------------------------------------------
# Popularity (fixed-odds caveat)
# ---------------------------------------------------------------------------


def digit_popularity(value: int, digits: int = 2) -> tuple[float, list[str]]:
    """Rough popularity score for a digit combination, with reasons.

    Included for completeness and for one important negative result: in a
    **fixed-odds** digit game, popularity does not affect your payout at
    all.  An 80x payout is 80x whether one person or ten thousand backed
    the number.  The unpopular-numbers strategy that genuinely helps in a
    pari-mutuel jackpot game does *nothing* here.

    It matters only to the bookmaker, who manages exposure on heavily
    backed numbers, and occasionally to the punter when a bookmaker caps or
    refuses a popular number.
    """
    text = str(value).zfill(digits)
    reasons: list[str] = []
    score = 1.0

    if len(set(text)) == 1:
        score *= 2.4
        reasons.append("repdigit (11, 22, 33...) - heavily backed")
    if text == text[::-1] and len(set(text)) > 1:
        score *= 1.5
        reasons.append("palindrome")
    if all(c in "05" for c in text):
        score *= 1.6
        reasons.append("round number")
    if digits == 2:
        a, b = int(text[0]), int(text[1])
        if b == a + 1 or b == a - 1:
            score *= 1.3
            reasons.append("consecutive digits")
        if 1 <= value <= 31:
            score *= 1.4
            reasons.append("falls in the calendar-day range")
        if 7 in (a, b):
            score *= 1.2
            reasons.append("contains 7")
        if 4 in (a, b):
            score *= 0.85
            reasons.append("contains 4 (avoided in East Asian markets)")
        if 8 in (a, b):
            score *= 1.15
            reasons.append("contains 8 (favoured in East Asian markets)")

    if not reasons:
        reasons.append("no notable pattern")
    return score, reasons


# ---------------------------------------------------------------------------
# Full audit
# ---------------------------------------------------------------------------


@dataclass
class DigitAuditReport:
    """Results of auditing a digit-game history."""

    config: DigitGameConfig
    n_draws: int
    tests: list[DigitTestResult] = field(default_factory=list)

    @property
    def any_flag(self) -> bool:
        """Whether any test flagged after FDR correction."""
        return any(t.significant for t in self.tests)

    def to_text(self) -> str:
        """Formatted report."""
        cfg = self.config
        lines = ["=" * 78,
                 f"DIGIT GAME AUDIT  -  {cfg.name}",
                 f"{self.n_draws} draws | {cfg.describe()}",
                 f"source: {cfg.source}",
                 "=" * 78, ""]
        for test in self.tests:
            lines.append("  " + str(test))
            if test.detail:
                lines.append(f"         {test.detail}")
            if test.interpretation:
                lines.append(f"         -> {test.interpretation}")
        lines.append("")
        lines.append("ECONOMICS")
        lines.append(f"  fair payout        : {cfg.fair_payout:,.0f}x")
        lines.append(f"  actual payout      : {cfg.payout_straight:,.0f}x")
        lines.append(f"  return to player   : {cfg.expected_return:.2%}")
        lines.append(f"  house edge         : {cfg.house_edge:.2%}")
        lines.append(f"  Kelly stake        : {kelly_for_digit_game(cfg):.4f}  (negative = do not bet)")
        lines.append("")
        lines.append(f"  Every {cfg.stake:,.0f} staked returns {cfg.expected_return * cfg.stake:,.2f} "
                     f"on average - a loss of {cfg.house_edge * cfg.stake:,.2f} per bet.")
        lines.append("=" * 78)
        return "\n".join(lines)


def digit_audit(history: DigitHistory) -> DigitAuditReport:
    """Run the full digit-game battery, with FDR correction across it."""
    tests: list[DigitTestResult] = []
    for pos in range(history.config.digits):
        tests.append(position_uniformity(history, pos))
    tests.append(joint_uniformity(history))
    if history.config.digits >= 2:
        tests.append(digit_independence(history))
    tests.append(serial_digit_test(history, lag=1))
    tests.append(serial_digit_test(history, lag=2))
    tests.append(round_number_clustering(history))

    # Correct across the battery. Running seven tests on fair data produces a
    # p < 0.05 roughly a third of the time; without this, the audit would
    # "find" bias in most honest games.
    qvals = M.benjamini_hochberg([t.pvalue for t in tests])
    for test, q in zip(tests, qvals):
        test.qvalue = q

    return DigitAuditReport(config=history.config, n_draws=len(history.draws), tests=tests)
