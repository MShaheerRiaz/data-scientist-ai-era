"""Expected value, jackpot sharing, and when a lottery is actually worth playing.

Most published lottery EV figures are wrong in the same way: they divide
the advertised jackpot by the odds and stop.  That ignores four things
that all cut the same direction.

1. **Sharing.** A jackpot big enough to be worth chasing attracts the
   crowd that will split it with you.  This is modelled here with the
   Poisson co-winner distribution.
2. **The cash/annuity gap.** The advertised figure is usually the annuity.
   The lump sum is typically 50-60% of it.
3. **Tax.** Often 25-40% on top.
4. **Rollover caps and roll-downs**, which change the structure entirely.

Put those together and the "break-even jackpot" for a game like Powerball
sits *above* any jackpot that can realistically be reached, because sales
grow with the jackpot and drag the sharing term up with them.  That is the
central result of this module, and it is why the genuinely profitable
historical plays (Cash WinFall, Michigan Winfall) were all *roll-down*
games where the money went to low tiers that are hit predictably — not to
a jackpot that gets split.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Sequence

from .combinatorics import (
    all_tier_probabilities,
    jackpot_probability,
    match_probability,
    total_combinations,
)
from .config import LotteryConfig, PrizeTier
from .popularity import share_factor

__all__ = [
    "EVAssumptions",
    "TierEV",
    "EVResult",
    "ticket_ev",
    "break_even_jackpot",
    "rolldown_ev",
    "kelly_fraction",
]


@dataclass
class EVAssumptions:
    """Everything outside the combinatorics that determines a ticket's value."""

    jackpot: float = 0.0
    tickets_sold: int = 0
    # Fraction of the advertised annuity you actually receive as a lump sum.
    cash_value_ratio: float = 1.0
    # Combined tax rate applied to winnings.
    tax_rate: float = 0.0
    # How over-picked your own combination is, after quick-pick dilution.
    popularity_multiplier: float = 1.0
    # Treat non-jackpot pari-mutuel tiers as shared too.
    share_lower_tiers: bool = False
    # If set, sales are modelled as growing with the jackpot rather than fixed.
    sales_per_jackpot_unit: Optional[float] = None
    # Baseline sales that occur regardless of jackpot size.
    sales_base: float = 0.0

    def effective_sales(self, jackpot: float) -> int:
        """Ticket sales, optionally as a function of jackpot size.

        Sales responding to jackpot size is what makes big jackpots a trap:
        the prize grows linearly, but so does the crowd you must split it
        with, and the two effects very nearly cancel.

        The relationship is affine, not proportional — a game sells plenty
        of tickets even at its floor jackpot.  Calibrated against Powerball:
        roughly 20 million baseline tickets plus 0.39 per dollar of
        advertised jackpot reproduces both the ~35M tickets sold at a $40M
        jackpot and the ~635M sold at the record $1.586bn draw of 13 January
        2016 (which duly produced 3 winners against an expectation of 2.17).
        """
        if self.sales_per_jackpot_unit is not None:
            return int(max(0.0, self.sales_base + self.sales_per_jackpot_unit * jackpot))
        return self.tickets_sold


@dataclass
class TierEV:
    """Expected value contributed by one prize tier."""

    tier: PrizeTier
    probability: float
    gross_payout: float
    net_payout: float
    contribution: float
    expected_cowinners: float = 0.0
    share: float = 1.0


@dataclass
class EVResult:
    """Full expected-value breakdown for one ticket."""

    config: LotteryConfig
    assumptions: EVAssumptions
    tiers: list[TierEV] = field(default_factory=list)
    expected_value: float = 0.0
    ticket_price: float = 0.0

    @property
    def net_ev(self) -> float:
        """Expected profit per ticket (negative for essentially every real game)."""
        return self.expected_value - self.ticket_price

    @property
    def return_ratio(self) -> float:
        """Expected return per unit staked. 1.0 is break-even."""
        return self.expected_value / self.ticket_price if self.ticket_price else float("nan")

    @property
    def house_edge(self) -> float:
        """Operator's expected take per unit staked."""
        return 1.0 - self.return_ratio

    def to_text(self) -> str:
        """Formatted breakdown suitable for a terminal."""
        cfg = self.config
        lines = ["=" * 78,
                 f"EXPECTED VALUE  -  {cfg.name}",
                 "=" * 78,
                 f"  ticket price        : {self.ticket_price:>18,.2f} {cfg.currency}",
                 f"  advertised jackpot  : {self.assumptions.jackpot:>18,.0f} {cfg.currency}"]
        if self.assumptions.cash_value_ratio != 1.0:
            lines.append(f"  cash value ratio    : {self.assumptions.cash_value_ratio:>18.2%}")
        if self.assumptions.tax_rate:
            lines.append(f"  tax rate            : {self.assumptions.tax_rate:>18.2%}")
        sales = self.assumptions.effective_sales(self.assumptions.jackpot)
        lines.append(f"  tickets sold        : {sales:>18,}")
        lines.append(f"  your pick popularity: {self.assumptions.popularity_multiplier:>18.3f}x")
        lines.append("")
        lines.append(f"  {'tier':<18}{'probability':>16}{'net payout':>16}"
                     f"{'share':>8}{'EV':>12}")
        for row in sorted(self.tiers, key=lambda r: -r.contribution):
            lines.append(f"  {row.tier.name:<18}{row.probability:>16.3e}"
                         f"{row.net_payout:>16,.0f}{row.share:>8.3f}{row.contribution:>12.4f}")
        lines.append("")
        lines.append(f"  expected value per ticket : {self.expected_value:>12,.4f} {cfg.currency}")
        lines.append(f"  cost                      : {self.ticket_price:>12,.4f} {cfg.currency}")
        lines.append(f"  net per ticket            : {self.net_ev:>12,.4f} {cfg.currency}")
        lines.append(f"  return per unit staked    : {self.return_ratio:>12.4f}")
        lines.append(f"  house edge                : {self.house_edge:>12.2%}")
        lines.append("")
        if self.net_ev > 0:
            lines.append("  This ticket is positive-EV. That is rare and almost always means a")
            lines.append("  roll-down, a capped rollover, or a promotional draw. Check the sharing")
            lines.append("  assumption carefully before acting - it is what usually kills the edge.")
        else:
            lines.append("  Negative EV, as expected. No choice of numbers changes this; picking")
            lines.append("  unpopular combinations only reduces how badly you lose when you win.")
        lines.append("=" * 78)
        return "\n".join(lines)


def ticket_ev(
    config: LotteryConfig,
    assumptions: Optional[EVAssumptions] = None,
) -> EVResult:
    """Expected value of a single ticket, including the sharing effect."""
    a = assumptions or EVAssumptions()
    sales = a.effective_sales(a.jackpot)
    rows: list[TierEV] = []
    total = 0.0

    for tier in config.tiers:
        p = match_probability(config, tier)
        if p <= 0:
            continue

        gross = a.jackpot if tier.is_jackpot else tier.payout
        if tier.is_jackpot:
            gross *= a.cash_value_ratio

        net = gross * (1.0 - a.tax_rate)

        # Sharing: only jackpots (and optionally other pari-mutuel tiers) split.
        share = 1.0
        others = 0.0
        if sales > 0 and (tier.is_jackpot or (a.share_lower_tiers and tier.is_parimutuel)):
            multiplier = a.popularity_multiplier if tier.is_jackpot else 1.0
            others = sales * p * multiplier
            share = share_factor(others)

        contribution = p * net * share
        total += contribution
        rows.append(TierEV(tier=tier, probability=p, gross_payout=gross,
                           net_payout=net, contribution=contribution,
                           expected_cowinners=others, share=share))

    return EVResult(config=config, assumptions=a, tiers=rows,
                    expected_value=total, ticket_price=config.ticket_price)


def break_even_jackpot(
    config: LotteryConfig,
    assumptions: Optional[EVAssumptions] = None,
    *,
    max_jackpot: float = 1e12,
) -> Optional[float]:
    """Smallest jackpot that makes a ticket break even, or ``None`` if unreachable.

    Returns ``None`` when no jackpot works.  That is the common answer for
    games whose sales scale with the jackpot: raising the prize also raises
    the expected number of co-winners, and the two effects cancel, so the
    expected value approaches a ceiling below the ticket price no matter
    how large the prize grows.
    """
    a = assumptions or EVAssumptions()

    def net_at(jackpot: float) -> float:
        trial = EVAssumptions(
            jackpot=jackpot,
            tickets_sold=a.tickets_sold,
            cash_value_ratio=a.cash_value_ratio,
            tax_rate=a.tax_rate,
            popularity_multiplier=a.popularity_multiplier,
            share_lower_tiers=a.share_lower_tiers,
            sales_per_jackpot_unit=a.sales_per_jackpot_unit,
        )
        return ticket_ev(config, trial).net_ev

    if net_at(0.0) > 0:
        return 0.0
    if net_at(max_jackpot) < 0:
        return None

    lo, hi = 0.0, max_jackpot
    for _ in range(300):
        mid = (lo + hi) / 2
        if net_at(mid) < 0:
            lo = mid
        else:
            hi = mid
    return hi


def rolldown_ev(
    config: LotteryConfig,
    *,
    rolldown_pool: float,
    tickets_sold: int,
    eligible_tiers: Optional[Sequence[str]] = None,
    tax_rate: float = 0.0,
) -> EVResult:
    """Expected value when an unhit jackpot rolls *down* into lower tiers.

    This is the structure that made Massachusetts Cash WinFall and Michigan
    Winfall genuinely beatable, and it is the only mechanism in this
    library that has ever produced a durable real-world edge.

    Why it works where a big jackpot does not: the roll-down money lands in
    tiers that are hit *often* and *predictably*.  Buying hundreds of
    thousands of tickets turns those frequent small wins into a near-certain
    average by the law of large numbers, whereas a jackpot play stays a
    lottery no matter how many tickets you buy.

    The pool is allocated in proportion to each tier's *expected base
    payout* (``probability * base prize``), which makes every eligible
    tier's prize scale by a common multiplier.  That matches what actually
    happened: Cash WinFall's roll-down took match-5 from $4,000 to about
    $23,000 (x5.75), match-4 from $150 to about $800 (x5.33) and match-3
    from $5 to about $26 (x5.20) — near-identical multipliers.

    Allocating in proportion to tier *probability* instead is a tempting
    mistake and a degenerate one: the extra per winner works out to
    ``pool / (sum_p * sales)``, with the tier probability cancelling
    entirely, so every tier would receive the same absolute bonus.
    """
    names = set(eligible_tiers) if eligible_tiers else None
    targets = [
        t for t in config.tiers
        if not t.is_jackpot and (names is None or t.name in names)
    ]
    if not targets:
        raise ValueError("no eligible tiers for the roll-down")

    weights = {
        t.name: match_probability(config, t) * t.payout
        for t in targets
    }
    weight_sum = sum(weights.values())
    if weight_sum <= 0:
        raise ValueError(
            "eligible tiers have zero expected base payout; roll-down allocation "
            "needs non-zero base prizes to scale"
        )

    rows: list[TierEV] = []
    total = 0.0
    for tier in config.tiers:
        p = match_probability(config, tier)
        if p <= 0:
            continue
        gross = tier.payout
        if tier in targets and tickets_sold > 0:
            # Extra money per winning ticket in this tier: the tier's slice of
            # the pool divided by how many tickets are expected to win it.
            slice_value = rolldown_pool * weights[tier.name] / weight_sum
            expected_winners = max(1.0, tickets_sold * p)
            gross += slice_value / expected_winners
        net = gross * (1.0 - tax_rate)
        contribution = p * net
        total += contribution
        rows.append(TierEV(tier=tier, probability=p, gross_payout=gross,
                           net_payout=net, contribution=contribution))

    return EVResult(
        config=config,
        assumptions=EVAssumptions(jackpot=0.0, tickets_sold=tickets_sold, tax_rate=tax_rate),
        tiers=rows,
        expected_value=total,
        ticket_price=config.ticket_price,
    )


def ziemba_expected_return(
    underbet_factors: Sequence[float],
    base_return: float = 0.45,
) -> float:
    """Ziemba's canonical unpopular-numbers formula for a 6/49 game.

        EV = base_return * F1 * F2 * ... * Fk

    Each ``F`` is the ratio of the uniform selection probability to the
    number's actual estimated selection probability, so ``F > 1`` means the
    number is under-bet.  ``base_return`` of 0.45 reflects the Canadian
    6/49 take and consolation pools, and rises when a carryover is present.

    The sixth power is what makes this both attractive and treacherous:
    :func:`ziemba_break_even_factor` shows every number must be under-bet
    by about 14% just to reach break-even, and the return then climbs very
    steeply.  Being slightly wrong about the factors moves the answer a
    long way.
    """
    result = base_return
    for f in underbet_factors:
        if f <= 0:
            raise ValueError("under-betting factors must be positive")
        result *= f
    return result


def ziemba_break_even_factor(picks: int = 6, base_return: float = 0.45) -> float:
    """Uniform under-betting factor needed to break even under Ziemba's formula.

    For the classic 6/49 at a 0.45 base this is ``(1/0.45)**(1/6) = 1.142``
    — every one of your six numbers must be roughly 14% under-bet before
    the ticket is even a fair bet.
    """
    if not 0 < base_return:
        raise ValueError("base_return must be positive")
    return (1.0 / base_return) ** (1.0 / picks)


def kelly_fraction(win_probability: float, net_odds: float) -> float:
    """Kelly-optimal stake as a fraction of bankroll.

    ``net_odds`` is profit per unit staked on a win.  The formula is
    ``(p*b - q)/b``.

    Two facts worth stating plainly.  For any negative-EV bet Kelly returns
    a negative number, whose correct interpretation is "bet nothing" — there
    is no bankroll management that rescues a losing game.  And even for a
    genuinely positive-EV lottery, the Kelly fraction is minuscule, because
    the win probability is tiny and the variance enormous.  A 2x-EV Powerball
    ticket would still justify staking well under a millionth of a bankroll
    per draw, which is why the real-world syndicates played roll-downs with
    frequent mid-tier hits rather than jackpots.
    """
    if net_odds <= 0:
        return 0.0
    p = win_probability
    q = 1.0 - p
    return (p * net_odds - q) / net_odds
