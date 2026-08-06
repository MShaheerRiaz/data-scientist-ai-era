"""Game definitions.

A ``LotteryConfig`` fully describes the combinatorial structure of a draw
game, which is all the rest of the toolkit needs in order to compute exact
odds, expected values and coverage guarantees.

The bundled presets are *representative* — operators change pools, prices
and prize tables more often than you would think (Mega Millions changed
both its bonus pool and its ticket price in April 2025, for instance).
Always confirm the current rules with the operator before betting real
money on numbers that came out of this library.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Optional

__all__ = [
    "BonusMode",
    "PrizeTier",
    "LotteryConfig",
    "DigitGameConfig",
    "PRESETS",
    "DIGIT_PRESETS",
    "get_preset",
    "list_presets",
]


class BonusMode(str, Enum):
    """How a game's supplementary ball is drawn.

    The distinction matters for the odds: a bonus drawn from a *separate*
    pool is independent of the main draw, whereas one drawn from the
    *remaining* main balls is not, and the two give materially different
    tier probabilities.
    """

    NONE = "none"
    SEPARATE_POOL = "separate_pool"      # Powerball, EuroMillions, Mega Millions
    FROM_REMAINING = "from_remaining"    # UK Lotto bonus ball, Canada 6/49


@dataclass(frozen=True)
class PrizeTier:
    """One row of a prize table.

    ``payout`` is the cash amount for fixed-prize tiers.  For pari-mutuel
    tiers it is a *representative* amount only — the real figure depends on
    sales and the number of winners, which is exactly what the EV engine
    models.

    ``bonus_any`` marks a tier that pays on the main matches alone, with the
    bonus ball irrelevant.  This is easy to get wrong and it matters: UK
    Lotto's "Match 4" pays whether or not the bonus was also hit, so its
    true odds are 1 in 2,180, not the 1 in 2,265 you get by insisting the
    bonus was missed.
    """

    name: str
    main_match: int
    bonus_match: int = 0
    payout: float = 0.0
    is_jackpot: bool = False
    is_parimutuel: bool = False
    bonus_any: bool = False

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.name


@dataclass(frozen=True)
class LotteryConfig:
    """Combinatorial description of a draw-style lottery."""

    name: str
    main_pool: int
    main_pick: int
    bonus_mode: BonusMode = BonusMode.NONE
    bonus_pool: int = 0
    bonus_pick: int = 0
    ticket_price: float = 2.0
    currency: str = "USD"
    tiers: tuple[PrizeTier, ...] = field(default_factory=tuple)
    # Fraction of ticket revenue that flows into the prize pool.  Used by the
    # EV engine when a jackpot figure is not supplied directly.
    prize_payout_ratio: float = 0.50
    # Rows on the physical bet slip, used by the popularity model to detect
    # geometric patterns (columns, diagonals) that players actually draw.
    slip_columns: int = 7
    notes: str = ""

    def __post_init__(self) -> None:
        if self.main_pick <= 0 or self.main_pool <= 0:
            raise ValueError("main_pool and main_pick must be positive")
        if self.main_pick > self.main_pool:
            raise ValueError("cannot pick more numbers than the pool holds")
        if self.bonus_mode is BonusMode.SEPARATE_POOL:
            if self.bonus_pool <= 0 or self.bonus_pick <= 0:
                raise ValueError("separate-pool bonus needs bonus_pool and bonus_pick")
            if self.bonus_pick > self.bonus_pool:
                raise ValueError("cannot pick more bonus numbers than the bonus pool holds")
        if self.bonus_mode is BonusMode.FROM_REMAINING:
            if self.bonus_pick != 1:
                raise ValueError("from-remaining bonus currently supports exactly one ball")
            if self.main_pick >= self.main_pool:
                raise ValueError("no balls left to draw a bonus from")

    @property
    def has_bonus(self) -> bool:
        """Whether the game draws any supplementary ball."""
        return self.bonus_mode is not BonusMode.NONE

    @property
    def jackpot_tier(self) -> Optional[PrizeTier]:
        """The top tier, if the prize table defines one."""
        for tier in self.tiers:
            if tier.is_jackpot:
                return tier
        return None

    def with_price(self, price: float) -> "LotteryConfig":
        """Return a copy at a different ticket price."""
        return replace(self, ticket_price=price)

    def describe(self) -> str:
        """One-line human-readable summary of the game's structure."""
        base = f"{self.name}: pick {self.main_pick} of {self.main_pool}"
        if self.bonus_mode is BonusMode.SEPARATE_POOL:
            base += f" + {self.bonus_pick} of {self.bonus_pool} (separate pool)"
        elif self.bonus_mode is BonusMode.FROM_REMAINING:
            base += " + 1 bonus from remaining balls"
        return base + f" @ {self.ticket_price:.2f} {self.currency}"


@dataclass(frozen=True)
class DigitGameConfig:
    """Description of a digit game (2D, 3D, Pick 3, 4D and friends).

    Digit games are structurally different from ball draws: positions are
    drawn *with* replacement, so every position is independent and uniform
    over 0-9 under fairness.  That makes them far easier to audit, and it
    makes the house edge purely a function of the quoted payout.
    """

    name: str
    digits: int
    payout_straight: float          # Return per 1 unit staked on an exact match.
    stake: float = 1.0
    currency: str = "USD"
    draws_per_day: int = 1
    source: str = "physical draw"
    notes: str = ""
    # True overall return to player, for games that pay across several tiers.
    # Without this a multi-tier game such as 4D - which pays 23 winning
    # numbers across first/second/third/starter/consolation - would be scored
    # from its first prize alone and look far worse than it is.
    rtp_override: Optional[float] = None

    @property
    def outcomes(self) -> int:
        """Size of the outcome space (10 ** digits)."""
        return 10 ** self.digits

    @property
    def fair_payout(self) -> float:
        """The payout multiple that would make the bet break even."""
        return float(self.outcomes)

    @property
    def is_multi_tier(self) -> bool:
        """Whether the quoted payout covers only part of the prize structure."""
        return self.rtp_override is not None

    @property
    def expected_return(self) -> float:
        """Expected value returned per unit staked.

        Uses the whole prize structure when the game defines one, and the
        single quoted payout otherwise.
        """
        if self.rtp_override is not None:
            return self.rtp_override
        return self.payout_straight / self.outcomes

    @property
    def house_edge(self) -> float:
        """Operator's expected take as a fraction of every unit staked.

        For a single-payout game this is ``1 - payout / outcomes``.  A 2D
        game paying 80x when the fair payout is 100x carries a 20% edge —
        an enormous number next to roulette (5.26%) or blackjack (<1%).
        """
        return 1.0 - self.expected_return

    def describe(self) -> str:
        """One-line human-readable summary of the game's economics."""
        if self.is_multi_tier:
            return (
                f"{self.name}: {self.digits} digits ({self.outcomes:,} outcomes), "
                f"multi-tier prize structure, return to player "
                f"{self.expected_return:.1%}, house edge {self.house_edge:.2%}"
            )
        return (
            f"{self.name}: {self.digits} digits ({self.outcomes:,} outcomes), "
            f"pays {self.payout_straight:g}x vs fair {self.fair_payout:g}x, "
            f"house edge {self.house_edge:.2%}"
        )


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------

_POWERBALL = LotteryConfig(
    name="US Powerball",
    main_pool=69,
    main_pick=5,
    bonus_mode=BonusMode.SEPARATE_POOL,
    bonus_pool=26,
    bonus_pick=1,
    ticket_price=2.0,
    currency="USD",
    slip_columns=10,
    tiers=(
        PrizeTier("5 + Powerball", 5, 1, 0.0, is_jackpot=True, is_parimutuel=True),
        PrizeTier("5", 5, 0, 1_000_000.0),
        PrizeTier("4 + Powerball", 4, 1, 50_000.0),
        PrizeTier("4", 4, 0, 100.0),
        PrizeTier("3 + Powerball", 3, 1, 100.0),
        PrizeTier("3", 3, 0, 7.0),
        PrizeTier("2 + Powerball", 2, 1, 7.0),
        PrizeTier("1 + Powerball", 1, 1, 4.0),
        PrizeTier("0 + Powerball", 0, 1, 4.0),
    ),
    notes="Jackpot odds 1 in 292,201,338. Fixed prizes shown; Power Play multiplier not modelled.",
)

_MEGA_MILLIONS = LotteryConfig(
    name="US Mega Millions",
    main_pool=70,
    main_pick=5,
    bonus_mode=BonusMode.SEPARATE_POOL,
    bonus_pool=24,
    bonus_pick=1,
    ticket_price=5.0,
    currency="USD",
    slip_columns=10,
    tiers=(
        PrizeTier("5 + Mega Ball", 5, 1, 0.0, is_jackpot=True, is_parimutuel=True),
        PrizeTier("5", 5, 0, 1_000_000.0),
        PrizeTier("4 + Mega Ball", 4, 1, 10_000.0),
        PrizeTier("4", 4, 0, 500.0),
        PrizeTier("3 + Mega Ball", 3, 1, 200.0),
        PrizeTier("3", 3, 0, 10.0),
        PrizeTier("2 + Mega Ball", 2, 1, 10.0),
        PrizeTier("1 + Mega Ball", 1, 1, 4.0),
        PrizeTier("0 + Mega Ball", 0, 1, 2.0),
    ),
    notes=(
        "Reflects the April 2025 revamp: $5 ticket, Mega Ball pool cut to 24, "
        "built-in multiplier. Base prizes shown without the multiplier."
    ),
)

_EUROMILLIONS = LotteryConfig(
    name="EuroMillions",
    main_pool=50,
    main_pick=5,
    bonus_mode=BonusMode.SEPARATE_POOL,
    bonus_pool=12,
    bonus_pick=2,
    ticket_price=2.50,
    currency="EUR",
    slip_columns=10,
    tiers=(
        PrizeTier("5 + 2 stars", 5, 2, 0.0, is_jackpot=True, is_parimutuel=True),
        PrizeTier("5 + 1 star", 5, 1, 130_000.0, is_parimutuel=True),
        PrizeTier("5", 5, 0, 30_000.0, is_parimutuel=True),
        PrizeTier("4 + 2 stars", 4, 2, 2_000.0, is_parimutuel=True),
        PrizeTier("4 + 1 star", 4, 1, 150.0, is_parimutuel=True),
        PrizeTier("4", 4, 0, 60.0, is_parimutuel=True),
        PrizeTier("3 + 2 stars", 3, 2, 50.0, is_parimutuel=True),
        PrizeTier("2 + 2 stars", 2, 2, 20.0, is_parimutuel=True),
        PrizeTier("3 + 1 star", 3, 1, 12.0, is_parimutuel=True),
        PrizeTier("3", 3, 0, 11.0, is_parimutuel=True),
        PrizeTier("1 + 2 stars", 1, 2, 10.0, is_parimutuel=True),
        PrizeTier("2 + 1 star", 2, 1, 8.0, is_parimutuel=True),
        PrizeTier("2", 2, 0, 4.0, is_parimutuel=True),
    ),
    notes="Every tier is pari-mutuel; payouts shown are typical, not fixed. Jackpot odds 1 in 139,838,160.",
)

_UK_LOTTO = LotteryConfig(
    name="UK Lotto",
    main_pool=59,
    main_pick=6,
    bonus_mode=BonusMode.FROM_REMAINING,
    bonus_pool=0,
    bonus_pick=1,
    ticket_price=2.0,
    currency="GBP",
    slip_columns=10,
    tiers=(
        PrizeTier("6", 6, 0, 0.0, is_jackpot=True, is_parimutuel=True),
        PrizeTier("5 + bonus", 5, 1, 1_000_000.0),
        PrizeTier("5", 5, 0, 1_750.0),
        PrizeTier("4", 4, 0, 140.0, bonus_any=True),
        PrizeTier("3", 3, 0, 30.0, bonus_any=True),
        PrizeTier("2", 2, 0, 2.0, bonus_any=True),
    ),
    notes="Match 2 pays a free Lucky Dip, valued here at the ticket price. Jackpot odds 1 in 45,057,474.",
)

_CANADA_649 = LotteryConfig(
    name="Canada Lotto 6/49",
    main_pool=49,
    main_pick=6,
    bonus_mode=BonusMode.FROM_REMAINING,
    bonus_pool=0,
    bonus_pick=1,
    ticket_price=3.0,
    currency="CAD",
    slip_columns=10,
    tiers=(
        PrizeTier("6", 6, 0, 0.0, is_jackpot=True, is_parimutuel=True),
        PrizeTier("5 + bonus", 5, 1, 0.0, is_parimutuel=True),
        PrizeTier("5", 5, 0, 0.0, is_parimutuel=True),
        PrizeTier("4", 4, 0, 0.0, is_parimutuel=True, bonus_any=True),
        PrizeTier("3", 3, 0, 10.0, bonus_any=True),
        PrizeTier("2 + bonus", 2, 1, 5.0),
        PrizeTier("2", 2, 0, 3.0),
    ),
    notes=(
        "The classic 6/49 studied in the academic literature. Jackpot odds 1 in 13,983,816. "
        "Match 2 pays a free play, valued here at the ticket price; including it reproduces "
        "the published 1-in-6.6 odds of winning any prize."
    ),
)

_LOTTO_MAX = LotteryConfig(
    name="Canada Lotto Max",
    main_pool=50,
    main_pick=7,
    bonus_mode=BonusMode.FROM_REMAINING,
    bonus_pool=0,
    bonus_pick=1,
    ticket_price=5.0,
    currency="CAD",
    slip_columns=10,
    tiers=(
        PrizeTier("7", 7, 0, 0.0, is_jackpot=True, is_parimutuel=True),
        PrizeTier("6 + bonus", 6, 1, 0.0, is_parimutuel=True),
        PrizeTier("6", 6, 0, 0.0, is_parimutuel=True),
        PrizeTier("5", 5, 0, 0.0, is_parimutuel=True, bonus_any=True),
        PrizeTier("4", 4, 0, 20.0, bonus_any=True),
        PrizeTier("3 + bonus", 3, 1, 20.0),
        PrizeTier("3", 3, 0, 5.0),
    ),
    notes=(
        "Jackpot odds 1 in 33,294,800 per selection. Note a $5 Lotto Max ticket buys THREE "
        "selections, so the operator's headline '1 in 7' odds of winning any prize are "
        "per ticket; this config models a single selection (1 in 20.9)."
    ),
)

_GENERIC_649 = LotteryConfig(
    name="Generic 6/49",
    main_pool=49,
    main_pick=6,
    bonus_mode=BonusMode.NONE,
    ticket_price=1.0,
    currency="USD",
    tiers=(
        PrizeTier("6", 6, 0, 0.0, is_jackpot=True, is_parimutuel=True),
        PrizeTier("5", 5, 0, 1_500.0),
        PrizeTier("4", 4, 0, 60.0),
        PrizeTier("3", 3, 0, 5.0),
    ),
    notes="Clean textbook game with no bonus ball — useful for teaching and for tests.",
)

PRESETS: dict[str, LotteryConfig] = {
    "powerball": _POWERBALL,
    "megamillions": _MEGA_MILLIONS,
    "euromillions": _EUROMILLIONS,
    "uk_lotto": _UK_LOTTO,
    "canada_649": _CANADA_649,
    "lotto_max": _LOTTO_MAX,
    "generic_649": _GENERIC_649,
}


# --- Digit games -----------------------------------------------------------

DIGIT_PRESETS: dict[str, DigitGameConfig] = {
    "myanmar_2d": DigitGameConfig(
        name="Myanmar 2D",
        digits=2,
        payout_straight=80.0,
        currency="MMK",
        draws_per_day=2,
        source="hundredths digit of SET index || units digit of integer millions of trading value",
        notes=(
            "Illegal but widely played. 80x is the payout that can actually be sourced; "
            "an 85x figure circulates but could not be verified, so 80x (a 20% edge) is "
            "the default here. Digits come from published Thai market figures rather than "
            "a ball draw, which changes the audit strategy completely - see "
            "docs/06-digit-games-2d-3d.md."
        ),
    ),
    "myanmar_3d": DigitGameConfig(
        name="Myanmar 3D",
        digits=3,
        payout_straight=500.0,
        currency="MMK",
        draws_per_day=1,
        source="commonly tied to Thai government lottery digits",
        notes="Payouts vary widely by bookmaker; 500x against a fair 1000x implies a 50% edge.",
    ),
    "pick3": DigitGameConfig(
        name="US Pick 3 (straight)",
        digits=3,
        payout_straight=500.0,
        stake=1.0,
        currency="USD",
        draws_per_day=2,
        source="state-run physical draw or certified RNG",
        notes="A 500x payout on 1000 outcomes is a 50% house edge - among the worst in regulated gambling.",
    ),
    "pick4": DigitGameConfig(
        name="US Pick 4 (straight)",
        digits=4,
        payout_straight=5000.0,
        stake=1.0,
        currency="USD",
        draws_per_day=2,
        source="state-run physical draw or certified RNG",
        notes="5000x on 10,000 outcomes is a 50% house edge.",
    ),
    "sg_4d": DigitGameConfig(
        name="Singapore Pools 4D (Big)",
        digits=4,
        payout_straight=2000.0,
        stake=1.0,
        currency="SGD",
        draws_per_day=1,
        source="physical draw machine",
        rtp_override=0.659,
        notes=(
            "4D pays 23 winning numbers per draw across first/second/third, 10 Starter "
            "and 10 Consolation. The 2000x figure is the first prize alone; scoring the "
            "game from it would imply an 80% edge, which is badly wrong. Summing the full "
            "structure per S$1 (2000 + 1000 + 490 + 10x250 + 10x60) / 10,000 gives a "
            "65.9% return, so the real edge is 34.1%."
        ),
    ),
    "my_4d": DigitGameConfig(
        name="Magnum 4D (Big)",
        digits=4,
        payout_straight=2500.0,
        stake=1.0,
        currency="MYR",
        draws_per_day=1,
        source="physical draw machine",
        rtp_override=0.64,
        notes=(
            "Same multi-tier structure as Singapore 4D: 1st RM2,500, 2nd RM1,000, "
            "3rd RM500, 10 Special at RM180, 10 Consolation at RM60 per RM1 staked, "
            "giving a 64% return and a 36% edge."
        ),
    ),
}


def get_preset(name: str) -> LotteryConfig:
    """Look up a draw-game preset by key, with a helpful error if missing."""
    key = name.strip().lower().replace("-", "_").replace(" ", "_")
    if key not in PRESETS:
        raise KeyError(
            f"unknown lottery preset {name!r}; available: {', '.join(sorted(PRESETS))}"
        )
    return PRESETS[key]


def list_presets() -> list[str]:
    """All available draw-game preset keys."""
    return sorted(PRESETS)
