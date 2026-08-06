"""Monte Carlo simulation of playing over time.

Expected value tells you the average.  It does not tell you what actually
happens to a person, and for lotteries the gap between those two things is
the whole story.  The distribution of outcomes is so skewed that the median
player's experience looks nothing like the mean, and "positive expected
value" can still mean near-certain ruin over any human timescale.

That last point is the historically decisive one.  Chernoff's real
unpopular-numbers experiment in the Massachusetts numbers game failed for
exactly two reasons: other players learned, and **the bankroll ran out
before the tail event arrived**.  This module measures that.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Optional, Sequence

from . import mathx as M
from .combinatorics import all_tier_probabilities, classify_ticket, random_combination
from .config import BonusMode, LotteryConfig
from .ev import EVAssumptions, ticket_ev

__all__ = ["SimulationResult", "simulate_play", "time_to_ruin", "jackpot_waiting_time"]


@dataclass
class SimulationResult:
    """Distribution of outcomes across many simulated players."""

    config: LotteryConfig
    n_players: int
    n_draws: int
    tickets_per_draw: int
    final_bankrolls: list[float] = field(default_factory=list)
    ruined: int = 0
    ever_hit_jackpot: int = 0
    tier_totals: dict[str, int] = field(default_factory=dict)
    starting_bankroll: float = 0.0

    def percentile(self, q: float) -> float:
        """The ``q``-th percentile of final bankroll (q in 0..100)."""
        if not self.final_bankrolls:
            return 0.0
        ordered = sorted(self.final_bankrolls)
        idx = min(len(ordered) - 1, max(0, int(round(q / 100 * (len(ordered) - 1)))))
        return ordered[idx]

    @property
    def mean_final(self) -> float:
        """Mean final bankroll across simulated players."""
        return M.mean(self.final_bankrolls) if self.final_bankrolls else 0.0

    @property
    def ruin_rate(self) -> float:
        """Fraction of players who went broke."""
        return self.ruined / self.n_players if self.n_players else 0.0

    def to_text(self) -> str:
        """Formatted summary of the simulated outcome distribution."""
        cfg = self.config
        spend = self.n_draws * self.tickets_per_draw * cfg.ticket_price
        lines = ["=" * 78,
                 f"SIMULATION  -  {cfg.name}",
                 f"{self.n_players:,} players x {self.n_draws:,} draws x "
                 f"{self.tickets_per_draw} ticket(s)",
                 "=" * 78,
                 "",
                 f"  starting bankroll        : {self.starting_bankroll:>14,.2f} {cfg.currency}",
                 f"  total staked per player  : {spend:>14,.2f} {cfg.currency}",
                 "",
                 "  FINAL BANKROLL DISTRIBUTION"]
        for q in (1, 5, 25, 50, 75, 95, 99):
            lines.append(f"    {q:>3}th percentile      : {self.percentile(q):>14,.2f}")
        lines.append(f"    mean                   : {self.mean_final:>14,.2f}")
        lines.append(f"    best                   : {max(self.final_bankrolls):>14,.2f}"
                     if self.final_bankrolls else "")
        lines.append("")
        lines.append(f"  players who went broke   : {self.ruined:,} ({self.ruin_rate:.2%})")
        lines.append(f"  players who hit a jackpot: {self.ever_hit_jackpot:,} "
                     f"({self.ever_hit_jackpot / self.n_players:.4%})")
        lines.append("")
        median = self.percentile(50)
        lines.append(f"  The median player finished with {median:,.2f} - a "
                     f"{(median - self.starting_bankroll):+,.2f} change.")

        # Only claim skew when the run actually shows it. With a modest number
        # of simulated players nobody hits a jackpot, and then the mean and
        # median coincide - which is its own, sharper point.
        gap = self.mean_final - median
        scale = max(abs(median), 1.0)
        if self.ever_hit_jackpot == 0:
            lines.append("")
            lines.append(f"  Not one of the {self.n_players:,} simulated players hit the jackpot.")
            lines.append("  With no tail event to skew it, the mean and median coincide and every")
            lines.append("  player simply lost at the house edge. To see the skew that carries the")
            lines.append("  average, you need enough players for someone to actually win - which")
            lines.append("  is the point: the outcome the advertising depicts is absent from a")
            lines.append("  simulation of five thousand lifetimes of play.")
        elif gap / scale > 0.02:
            lines.append("")
            lines.append(f"  The mean ({self.mean_final:,.2f}) sits {gap:,.2f} above the median.")
            lines.append("  That gap is the whole business model: a few enormous wins carry an")
            lines.append("  average that almost nobody experiences.")
        lines.append("=" * 78)
        return "\n".join(lines)


def simulate_play(
    config: LotteryConfig,
    *,
    n_players: int = 10000,
    n_draws: int = 520,
    tickets_per_draw: int = 1,
    starting_bankroll: float = 5000.0,
    jackpot: float = 50_000_000.0,
    stop_on_ruin: bool = True,
    seed: int = 0,
) -> SimulationResult:
    """Simulate many players buying tickets over many draws.

    Ten years of weekly play is ``n_draws=520``.  The output is the honest
    answer to "what happens if I play regularly?" — not the expected value,
    but the distribution of what actually occurs.
    """
    rng = random.Random(seed)
    tiers = [(t, p) for t, p in all_tier_probabilities(config) if p > 0]
    # Cumulative table for fast sampling of a ticket's outcome.
    cumulative: list[tuple[float, object]] = []
    acc = 0.0
    for tier, p in tiers:
        acc += p
        cumulative.append((acc, tier))
    lose_threshold = acc

    finals: list[float] = []
    ruined = 0
    jackpot_hits = 0
    tier_totals: dict[str, int] = {}

    for _ in range(n_players):
        bankroll = starting_bankroll
        hit_jackpot = False
        for _ in range(n_draws):
            if stop_on_ruin and bankroll < config.ticket_price * tickets_per_draw:
                ruined += 1
                break
            for _ in range(tickets_per_draw):
                bankroll -= config.ticket_price
                roll = rng.random()
                if roll >= lose_threshold:
                    continue
                for threshold, tier in cumulative:
                    if roll < threshold:
                        payout = jackpot if tier.is_jackpot else tier.payout  # type: ignore[union-attr]
                        bankroll += payout
                        name = tier.name  # type: ignore[union-attr]
                        tier_totals[name] = tier_totals.get(name, 0) + 1
                        if tier.is_jackpot:  # type: ignore[union-attr]
                            hit_jackpot = True
                        break
        else:
            pass
        if hit_jackpot:
            jackpot_hits += 1
        finals.append(bankroll)

    return SimulationResult(
        config=config, n_players=n_players, n_draws=n_draws,
        tickets_per_draw=tickets_per_draw, final_bankrolls=finals,
        ruined=ruined, ever_hit_jackpot=jackpot_hits, tier_totals=tier_totals,
        starting_bankroll=starting_bankroll,
    )


def time_to_ruin(
    config: LotteryConfig,
    *,
    bankroll: float,
    tickets_per_draw: int = 1,
    jackpot: float = 50_000_000.0,
) -> dict[str, float]:
    """Analytic estimate of how long a bankroll survives.

    Uses the per-ticket expected loss, which is the correct first-order
    answer because the small frequent prizes dominate the drift while the
    jackpot contributes almost nothing to the median path.
    """
    result = ticket_ev(config, EVAssumptions(jackpot=jackpot))
    loss_per_ticket = -result.net_ev
    if loss_per_ticket <= 0:
        return {"expected_draws": math.inf,
                "note": "Positive expected value - no systematic ruin, though variance still bites."}
    per_draw = loss_per_ticket * tickets_per_draw
    draws = bankroll / per_draw
    return {
        "expected_loss_per_ticket": loss_per_ticket,
        "expected_loss_per_draw": per_draw,
        "expected_draws": draws,
        "years_weekly": draws / 52,
        "years_twice_weekly": draws / 104,
    }


def jackpot_waiting_time(
    config: LotteryConfig,
    *,
    tickets_per_draw: int = 1,
    draws_per_year: float = 104,
) -> dict[str, float]:
    """How long until you would expect to win the jackpot.

    The number that makes the scale concrete.  For Powerball at one ticket
    twice a week, the expected wait exceeds the age of the universe by a
    wide margin.
    """
    from .combinatorics import jackpot_probability

    p = jackpot_probability(config)
    expected_draws = 1.0 / (p * tickets_per_draw)
    years = expected_draws / draws_per_year
    # Probability of at least one jackpot across a 50-year playing lifetime.
    lifetime_draws = draws_per_year * 50
    p_lifetime = 1 - (1 - p) ** (lifetime_draws * tickets_per_draw)
    return {
        "jackpot_probability": p,
        "expected_draws": expected_draws,
        "expected_years": years,
        "p_win_in_50_years": p_lifetime,
        "odds_string_50y": f"1 in {1 / p_lifetime:,.0f}" if p_lifetime > 0 else "never",
    }
