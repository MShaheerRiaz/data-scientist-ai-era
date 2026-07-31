"""The mathematics that actually determines whether a trading account survives.

Trading maths is not the algebra and calculus of a syllabus. Almost none of it
is differentiation. What decides outcomes is a small set of results from
probability and the theory of repeated betting:

    expectancy        is the edge positive at all?
    Kelly criterion   given an edge, how much may be risked per bet?
    risk of ruin      what is the probability of going broke before the edge pays?
    leverage maths    how far can price move before the position is closed for you?

The last two are the ones that end accounts, and they are the ones most often
skipped — because they answer "how much" and "how long can I survive", not the
much more interesting-sounding "what will price do next".

Everything here is deterministic, testable and independent of the model. It is
the arithmetic underneath the strategy, not another opinion about direction.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


# --- edge -----------------------------------------------------------------


def expectancy_r(win_rate: float, reward_risk: float) -> float:
    """Expected profit per trade, measured in R (multiples of the risked amount).

    R is the only sane unit for comparing trades of different sizes: a trade
    risking 50 and making 100 is +2R, exactly like one risking 500 to make
    1000.

        E[R] = p * b - (1 - p) * 1

    Positive expectancy is necessary but nowhere near sufficient — a positive
    edge bet too large still goes to zero (see risk_of_ruin).
    """
    if not 0.0 <= win_rate <= 1.0:
        raise ValueError("win_rate must be between 0 and 1")
    if reward_risk <= 0:
        raise ValueError("reward_risk must be positive")
    return win_rate * reward_risk - (1.0 - win_rate)


def breakeven_win_rate(reward_risk: float) -> float:
    """Win rate at which expectancy is exactly zero, for a given reward:risk.

    The single most clarifying number in trading. At 2:1 you need only 33.3%
    of trades to work. At 0.5:1 you need 66.7%. This is why "win rate" quoted
    without reward:risk is meaningless, and why a strategy winning 80% of the
    time can still lose money.
    """
    if reward_risk <= 0:
        raise ValueError("reward_risk must be positive")
    return 1.0 / (1.0 + reward_risk)


# --- how much to risk -----------------------------------------------------


def kelly_fraction(win_rate: float, reward_risk: float) -> float:
    """Kelly-optimal fraction of capital to risk per trade.

        f* = (p * b - q) / b

    Kelly maximises the long-run growth *rate* of capital. It is the
    mathematically correct answer to "how much", and it is almost always too
    large to actually use — see kelly_fraction_fractional.

    Returns 0.0 when the edge is negative: the correct size for a losing
    strategy is nothing.
    """
    edge = expectancy_r(win_rate, reward_risk)
    if edge <= 0:
        return 0.0
    return edge / reward_risk


def kelly_fraction_fractional(
    win_rate: float, reward_risk: float, fraction: float = 0.25
) -> float:
    """A conservative fraction of full Kelly. This is what practitioners use.

    Full Kelly is optimal only if your win rate and reward:risk are known
    exactly. They never are — they are estimates from a limited sample, and
    overestimating the edge means overbetting, which compounds against you.

    Full Kelly also produces drawdowns most people cannot sit through: it has
    roughly a 1-in-3 chance of a 50% drawdown at some point. Quarter-Kelly
    gives about half the growth rate for a quarter of the variance, which is
    the trade almost everyone should take.
    """
    return kelly_fraction(win_rate, reward_risk) * fraction


# --- surviving ------------------------------------------------------------


@dataclass
class RuinResult:
    probability_of_ruin: float
    median_final_equity: float
    p05_final_equity: float      # 5th percentile — the bad-but-not-worst case
    p95_final_equity: float
    median_max_drawdown: float
    worst_max_drawdown: float


def risk_of_ruin(
    win_rate: float,
    reward_risk: float,
    risk_per_trade: float,
    trades: int = 500,
    ruin_threshold: float = 0.5,
    simulations: int = 10_000,
    seed: int | None = 42,
) -> RuinResult:
    """Monte Carlo probability of losing `ruin_threshold` of capital.

    Simulated rather than closed-form on purpose. The analytic risk-of-ruin
    formulas assume fixed-unit betting; real position sizing is fixed
    *fractional* (a percentage of current equity), which changes the dynamics —
    losses shrink the next bet, so ruin becomes asymptotic rather than certain,
    and drawdown distribution matters more than a single ruin probability.

    `ruin_threshold` of 0.5 means "lost half the account". That is the
    realistic ruin point for a person, not zero: almost nobody keeps trading a
    strategy after a 50% drawdown, so the account is functionally dead well
    before the balance is.
    """
    if not 0.0 < risk_per_trade < 1.0:
        raise ValueError("risk_per_trade must be between 0 and 1")

    rng = random.Random(seed)
    ruined = 0
    finals: list[float] = []
    drawdowns: list[float] = []

    for _ in range(simulations):
        equity = 1.0
        peak = 1.0
        max_dd = 0.0
        hit_ruin = False

        for _ in range(trades):
            risked = equity * risk_per_trade
            if rng.random() < win_rate:
                equity += risked * reward_risk
            else:
                equity -= risked

            peak = max(peak, equity)
            max_dd = max(max_dd, (peak - equity) / peak)

            if equity <= (1.0 - ruin_threshold):
                hit_ruin = True
                break

        ruined += hit_ruin
        finals.append(equity)
        drawdowns.append(max_dd)

    finals.sort()
    drawdowns.sort()

    def pct(values: list[float], q: float) -> float:
        idx = min(int(q * len(values)), len(values) - 1)
        return values[idx]

    return RuinResult(
        probability_of_ruin=ruined / simulations,
        median_final_equity=pct(finals, 0.5),
        p05_final_equity=pct(finals, 0.05),
        p95_final_equity=pct(finals, 0.95),
        median_max_drawdown=pct(drawdowns, 0.5),
        worst_max_drawdown=drawdowns[-1],
    )


# --- leverage -------------------------------------------------------------


def liquidation_distance_pct(leverage: float, maintenance_margin: float = 0.005) -> float:
    """How far price may move against a leveraged position before liquidation.

    Approximately 1/leverage, less the maintenance margin the exchange keeps:

        distance ≈ (1 / leverage) - maintenance_margin

    The number this produces at high leverage is the entire argument against
    high leverage, and it is arithmetic rather than opinion. At 100x a 0.5%
    move ends the position. At 200x it is 0.0%: the maintenance margin alone
    consumes the whole buffer, so the position is liquidated by ordinary
    spread and funding before price does anything at all.
    """
    if leverage <= 0:
        raise ValueError("leverage must be positive")
    return max(0.0, (1.0 / leverage) - maintenance_margin)


def survival_probability(
    leverage: float,
    volatility_pct: float,
    maintenance_margin: float = 0.005,
) -> float:
    """Rough probability a position is NOT liquidated by ordinary noise.

    Models the adverse excursion over one holding period as a half-normal
    draw with standard deviation `volatility_pct` (use ATR% for the timeframe
    you hold). Returns the probability that excursion stays inside the
    liquidation distance.

    This deliberately ignores direction and edge. That is the point: it
    measures whether the position survives long enough for any edge to matter.
    A correct directional call is worth nothing if noise closes the position
    first, and at high leverage that is the normal outcome.
    """
    distance = liquidation_distance_pct(leverage, maintenance_margin)
    if distance <= 0:
        return 0.0
    if volatility_pct <= 0:
        return 1.0
    # P(|Z| < d/sigma) for a normal centred at zero.
    return math.erf((distance / volatility_pct) / math.sqrt(2))


def max_safe_leverage(
    volatility_pct: float,
    survival_target: float = 0.99,
    maintenance_margin: float = 0.005,
) -> float:
    """Highest leverage that keeps liquidation risk under (1 - survival_target).

    Inverts survival_probability: find the distance giving the target survival
    rate, then the leverage that provides it.
    """
    if volatility_pct <= 0:
        raise ValueError("volatility_pct must be positive")
    # Inverse of erf via bisection — avoids a scipy dependency for one call.
    lo, hi = 0.0, 10.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if math.erf(mid / math.sqrt(2)) < survival_target:
            lo = mid
        else:
            hi = mid
    z = (lo + hi) / 2
    required_distance = z * volatility_pct
    return 1.0 / (required_distance + maintenance_margin)


# --- sample size ----------------------------------------------------------

def trades_needed_for_significance(
    edge_r: float, trade_std_r: float = 1.0, confidence_z: float = 1.96
) -> int:
    """How many trades before a measured edge is distinguishable from luck.

    n ≈ (z * sigma / edge)^2

    This is the number that makes most "my strategy works" claims untestable.
    A +0.1R edge with 1R-ish per-trade variability needs roughly 385 trades
    before a 95% confidence interval excludes zero. On 15m bars taking a
    handful of trades a week, that is well over a year of data.

    A 20-trade winning streak is not evidence of anything, in either
    direction.
    """
    if edge_r <= 0:
        return -1  # a non-positive edge is never "significantly" profitable
    return math.ceil((confidence_z * trade_std_r / edge_r) ** 2)
