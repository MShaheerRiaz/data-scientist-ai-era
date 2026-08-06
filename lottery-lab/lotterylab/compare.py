"""Which UK game should you actually play?

Most lottery advice answers the wrong question. It optimises for the
jackpot, which nobody wins, or for "value", which nobody experiences.

The right question depends on what you would consider a win. Someone who
would be pleased with a four-figure prize and indifferent to £10 should
play a completely different game from someone chasing a jackpot — and the
gap between the right and wrong choice is enormous. For a £1,000-plus
prize, the best UK option is roughly **72 times** more likely per pound
than the obvious one.

This module ranks every UK option by two things that actually matter:

* **Access** — your chance of winning at least £X per pound staked.
* **Value** — return to player, i.e. how fast the money drains.

They usually disagree, and when they do this module says so rather than
picking one and hiding the trade-off.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from .combinatorics import all_tier_probabilities, odds_string
from .config import HOTPICKS, PRESETS, UK_GAMES, HotPicksConfig, LotteryConfig

__all__ = ["Option", "uk_options", "best_for", "compare_table", "budget_outcome"]


@dataclass
class Option:
    """One playable bet: a game, or one pick size of a HotPicks game."""

    label: str
    game_key: str
    prize: float
    probability: float
    ticket_price: float
    currency: str = "GBP"
    shared: bool = False
    is_jackpot: bool = False
    note: str = ""

    @property
    def cost_per_shot(self) -> float:
        """Pounds staked per expected occurrence of this prize.

        The single most useful comparison number: how much you must spend,
        on average, to hit this prize once.
        """
        if self.probability <= 0:
            return float("inf")
        return self.ticket_price / self.probability

    @property
    def expected_return(self) -> float:
        """Return per unit staked from this tier alone."""
        return self.probability * self.prize / self.ticket_price

    def chance_over(self, lines: int) -> float:
        """P(at least one hit) across ``lines`` independent lines."""
        return 1.0 - (1.0 - self.probability) ** lines


def uk_options(
    *,
    jackpot_assumptions: Optional[dict[str, float]] = None,
) -> list[Option]:
    """Every distinct UK bet, flattened into comparable options.

    Jackpot tiers need an assumed prize because they are pari-mutuel and
    have no fixed value; the defaults are typical rather than exceptional,
    since an exceptional jackpot is exactly when sharing is worst.
    """
    jackpots = {
        "uk_lotto": 4_000_000.0,
        "euromillions": 50_000_000.0,
        **(jackpot_assumptions or {}),
    }

    options: list[Option] = []

    for key in UK_GAMES:
        cfg = PRESETS[key]
        for tier, p in all_tier_probabilities(cfg):
            prize = jackpots.get(key, tier.payout) if tier.is_jackpot else tier.payout
            if prize <= 0:
                continue
            options.append(Option(
                label=f"{cfg.name} - {tier.name}",
                game_key=key,
                prize=prize,
                probability=p,
                ticket_price=cfg.ticket_price,
                currency=cfg.currency,
                shared=tier.is_parimutuel,
                is_jackpot=tier.is_jackpot,
                note="prize shared with other winners" if tier.is_parimutuel else "",
            ))

    for key, hp in HOTPICKS.items():
        for picks in sorted(hp.payouts):
            options.append(Option(
                label=f"{hp.name} pick-{picks}",
                game_key=key,
                prize=hp.payouts[picks],
                probability=hp.probability(picks),
                ticket_price=hp.ticket_price,
                currency=hp.currency,
                shared=False,
                note="fixed prize, never shared",
            ))

    return options


def best_for(
    target: float,
    *,
    options: Optional[Iterable[Option]] = None,
    limit: int = 6,
) -> list[Option]:
    """Rank the cheapest routes to a prize of at least ``target``.

    Sorted by cost per shot — pounds staked per expected hit — which is the
    honest way to compare bets at different ticket prices.
    """
    candidates = [o for o in (options or uk_options()) if o.prize >= target]
    candidates.sort(key=lambda o: o.cost_per_shot)
    return candidates[:limit]


def compare_table(
    targets: tuple[float, ...] = (1_000, 10_000, 20_000, 1_000_000),
    *,
    limit: int = 4,
) -> str:
    """Formatted answer to 'which game should I play?' at several prize levels."""
    width = 88
    lines = ["=" * width,
             "WHICH UK GAME GIVES THE BEST SHOT AT A MEANINGFUL PRIZE?",
             "=" * width]

    for target in targets:
        lines.append("")
        lines.append(f"  --- Best routes to GBP {target:,.0f} or more ---")
        lines.append(f"  {'option':<34}{'prize':>11}{'odds':>18}{'per line':>10}"
                     f"{'GBP per shot':>14}")
        for option in best_for(target, limit=limit):
            lines.append(
                f"  {option.label:<34}{option.prize:>11,.0f}"
                f"{odds_string(option.probability):>18}{option.ticket_price:>10.2f}"
                f"{option.cost_per_shot:>14,.0f}"
            )

    lines.append("")
    lines.append("  'GBP per shot' is what you must stake, on average, to hit that prize once.")
    lines.append("  Lower is better. It is the only fair way to compare bets priced differently.")
    lines.append("=" * width)
    return "\n".join(lines)


def budget_outcome(
    option: Option,
    weekly_spend: float,
    weeks: int = 52,
) -> dict[str, float]:
    """What a realistic budget actually buys on one option."""
    total = weekly_spend * weeks
    lines = int(total / option.ticket_price)
    chance = option.chance_over(lines)
    return {
        "total_spend": total,
        "lines": float(lines),
        "p_win": chance,
        "odds": (1 / chance) if chance > 0 else float("inf"),
        "expected_returned": total * option.expected_return,
    }


def value_table() -> str:
    """Rank every UK option by return to player — how fast money drains."""
    rows: list[tuple[str, float, float]] = []

    jackpots = {"uk_lotto": 4_000_000.0, "euromillions": 50_000_000.0}
    for key in UK_GAMES:
        cfg = PRESETS[key]
        total = 0.0
        for tier, p in all_tier_probabilities(cfg):
            prize = jackpots.get(key, tier.payout) if tier.is_jackpot else tier.payout
            total += p * prize
        rows.append((cfg.name, cfg.ticket_price, total / cfg.ticket_price))

    for hp in HOTPICKS.values():
        for picks in sorted(hp.payouts):
            rows.append((f"{hp.name} pick-{picks}", hp.ticket_price,
                         hp.expected_return(picks)))

    rows.sort(key=lambda r: -r[2])
    width = 72
    lines = ["=" * width,
             "VALUE: HOW FAST DOES THE MONEY DRAIN?",
             "=" * width,
             f"  {'option':<34}{'price':>8}{'RTP':>10}{'house edge':>14}"]
    for name, price, rtp in rows:
        lines.append(f"  {name:<34}{price:>8.2f}{rtp:>10.1%}{1 - rtp:>14.1%}")
    lines.append("")
    lines.append("  Jackpot tiers assume a typical jackpot (Lotto GBP 4m, EuroMillions GBP 50m)")
    lines.append("  and ignore sharing, so the two main games are flattered here, not penalised.")
    lines.append("=" * width)
    return "\n".join(lines)
