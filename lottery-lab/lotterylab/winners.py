"""Why somebody wins every week — and why that says nothing about you.

The most common reason people start playing seriously is noticing that
somebody wins a large prize almost every week. That observation is
completely correct, and it is *designed*. This module quantifies it.

Three separate mechanisms make UK millionaires on a fixed schedule:

1. **EuroMillions UK Millionaire Maker** attaches a raffle code to every
   UK ticket and guarantees at least one UK millionaire in **every draw**.
   Twice a week, unconditionally. Nobody has to match anything — the code
   is drawn from the codes actually sold, so a winner is certain.
2. **Lotto's Match 5 + Bonus** tier pays a flat GBP 1,000,000 at odds of
   1 in 7,509,579. With millions of lines in play, one or more winners per
   draw is the normal outcome, not a surprise.
3. **Jackpots** in Lotto and EuroMillions.

Put together, the UK reliably produces several new millionaires a week.
The number of winners is a function of how many tickets are sold — it
scales with the crowd. Your personal probability does not change at all.

This is the "someone has to win" fallacy in its most persuasive form.
"Somebody wins" and "I have a realistic chance of winning" are different
statements, and the first is engineered precisely to make the second feel
true.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import mathx as M
from .combinatorics import all_tier_probabilities, odds_string
from .config import PRESETS, LotteryConfig

__all__ = [
    "TierWinners",
    "WinnerForecast",
    "expected_winners",
    "uk_millionaire_summary",
    "GUARANTEED_UK_MILLIONAIRES_PER_WEEK",
    "TYPICAL_LINES_SOLD",
]

#: EuroMillions runs the UK Millionaire Maker raffle on both weekly draws,
#: each guaranteeing at least one UK millionaire regardless of the numbers.
GUARANTEED_UK_MILLIONAIRES_PER_WEEK: int = 2

#: Rough lines sold per draw, for putting winner counts in context.
#: These move with jackpot size and are estimates, not operator figures —
#: pass your own via ``lines_sold`` for anything that matters.
TYPICAL_LINES_SOLD: dict[str, int] = {
    "uk_lotto": 15_000_000,
    "euromillions": 30_000_000,
    "thunderball": 4_000_000,
    "set_for_life": 1_500_000,
}


@dataclass
class TierWinners:
    """Expected winners in one prize tier for one draw."""

    tier_name: str
    probability: float
    expected_winners: float
    payout: float
    is_jackpot: bool = False

    @property
    def p_at_least_one(self) -> float:
        """Probability that this tier produces at least one winner."""
        return 1.0 - M.poisson_pmf(0, self.expected_winners)


@dataclass
class WinnerForecast:
    """Expected winners across every tier of a game."""

    config: LotteryConfig
    lines_sold: int
    tiers: list[TierWinners] = field(default_factory=list)

    def big_winners(self, threshold: float) -> list[TierWinners]:
        """Tiers paying at least ``threshold``."""
        return [t for t in self.tiers if t.payout >= threshold or t.is_jackpot]

    def expected_above(self, threshold: float) -> float:
        """Expected number of winners of at least ``threshold`` per draw."""
        return sum(t.expected_winners for t in self.big_winners(threshold))

    def to_text(self) -> str:
        """Formatted forecast."""
        cfg = self.config
        width = 78
        lines = ["=" * width,
                 f"EXPECTED WINNERS PER DRAW  -  {cfg.name}",
                 f"{self.lines_sold:,} lines in play",
                 "=" * width,
                 "",
                 f"  {'tier':<20}{'odds':>20}{'winners/draw':>15}{'P(>=1)':>10}"]
        for tier in self.tiers:
            lines.append(f"  {tier.tier_name:<20}{odds_string(tier.probability):>20}"
                         f"{tier.expected_winners:>15,.2f}{tier.p_at_least_one:>10.1%}")
        lines.append("")
        million = self.expected_above(1_000_000)
        if million > 0:
            lines.append(f"  Expected prizes of {cfg.currency} 1,000,000 or more per draw: "
                         f"{million:,.2f}")
            lines.append(f"  Probability at least one such prize is won: "
                         f"{1 - M.poisson_pmf(0, million):.1%}")
        lines.append("=" * width)
        return "\n".join(lines)


def expected_winners(
    config: LotteryConfig,
    lines_sold: Optional[int] = None,
    *,
    game_key: Optional[str] = None,
) -> WinnerForecast:
    """Expected winners in each tier, given how many lines are in play.

    Winner counts are Poisson with mean ``lines_sold * p``. This is the
    calculation that explains a weekly stream of millionaires without any
    appeal to luck: multiply a tiny probability by a very large number of
    tickets and you get a number comfortably above one.
    """
    if lines_sold is None:
        key = game_key or next(
            (k for k, v in PRESETS.items() if v.name == config.name), None
        )
        lines_sold = TYPICAL_LINES_SOLD.get(key or "", 10_000_000)

    tiers = [
        TierWinners(
            tier_name=tier.name,
            probability=p,
            expected_winners=lines_sold * p,
            payout=tier.payout,
            is_jackpot=tier.is_jackpot,
        )
        for tier, p in all_tier_probabilities(config)
        if p > 0
    ]
    return WinnerForecast(config=config, lines_sold=lines_sold, tiers=tiers)


def uk_millionaire_summary(
    *,
    lotto_lines: Optional[int] = None,
    euromillions_lines: Optional[int] = None,
    your_lines_per_week: int = 1,
) -> str:
    """How many UK millionaires a week, and how that relates to you.

    Answers the question that starts most lottery habits: "somebody won a
    million again last week, so it must be possible."
    """
    lotto = PRESETS["uk_lotto"]
    euro = PRESETS["euromillions"]

    lotto_sold = lotto_lines or TYPICAL_LINES_SOLD["uk_lotto"]
    euro_sold = euromillions_lines or TYPICAL_LINES_SOLD["euromillions"]

    lotto_forecast = expected_winners(lotto, lotto_sold, game_key="uk_lotto")
    euro_forecast = expected_winners(euro, euro_sold, game_key="euromillions")

    # Lotto: 2 draws a week; the flat GBP 1m tier plus the jackpot.
    lotto_millionaires = lotto_forecast.expected_above(1_000_000) * 2
    # EuroMillions: 2 draws a week; jackpot winners are shared across nine
    # countries, so only a fraction land in the UK.
    euro_jackpot = sum(t.expected_winners for t in euro_forecast.tiers if t.is_jackpot) * 2
    guaranteed = GUARANTEED_UK_MILLIONAIRES_PER_WEEK

    total = lotto_millionaires + guaranteed + euro_jackpot * 0.15

    width = 78
    out = ["=" * width,
           "WHY SOMEBODY WINS A MILLION ALMOST EVERY WEEK",
           "=" * width,
           "",
           "  SOURCES OF UK MILLIONAIRES PER WEEK",
           "",
           f"  EuroMillions UK Millionaire Maker        {guaranteed:>8.2f}   guaranteed by design",
           f"  Lotto Match 5 + Bonus (flat GBP 1m)      {lotto_millionaires:>8.2f}   "
           f"from {lotto_sold:,} lines x 2 draws",
           f"  EuroMillions jackpot, UK share (~15%)    {euro_jackpot * 0.15:>8.2f}   estimate",
           "  " + "-" * (width - 4),
           f"  Expected new UK millionaires per week    {total:>8.2f}",
           "",
           "  The Millionaire Maker raffle alone guarantees two, every single week,",
           "  with no matching required - the code is drawn from codes actually sold,",
           "  so a winner is certain before the draw happens. Seeing a winner is not",
           "  evidence of anything. It is the product working as designed.",
           "",
           "  NOW YOUR SIDE OF IT",
           ""]

    p_lotto_million = sum(
        p for tier, p in all_tier_probabilities(lotto)
        if tier.payout >= 1_000_000 or tier.is_jackpot
    )
    weekly = 1.0 - (1.0 - p_lotto_million) ** (your_lines_per_week * 2)
    years_50 = 1.0 - (1.0 - p_lotto_million) ** (your_lines_per_week * 2 * 52 * 50)

    out += [
        f"  Playing {your_lines_per_week} Lotto line(s) per draw, both draws a week:",
        f"    chance of winning GBP 1m or more in a given week : {odds_string(weekly)}",
        f"    chance across 50 years of never missing a draw   : {odds_string(years_50)}",
        f"    cost across those 50 years                       : "
        f"GBP {your_lines_per_week * 2 * 52 * 50 * lotto.ticket_price:,.0f}",
        "",
        "  Both facts are true at once: several people become millionaires every",
        "  week, and your own chance is roughly 1 in "
        f"{1 / years_50:,.0f} even after fifty years",
        "  of playing every single draw. The weekly winners come from the size of",
        "  the crowd, not from the odds - which never move.",
        "=" * width,
    ]
    return "\n".join(out)
