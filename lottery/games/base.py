from dataclasses import dataclass, field


@dataclass(frozen=True)
class PrizeTier:
    name: str
    main_matches: int
    bonus_matches: int        # 0, 1, or 2 (EuroMillions stars)
    odds: int                 # exact 1-in-N integer
    prize_type: str           # "fixed", "pari_mutuel", "monthly", "raffle"
    fixed_value: int = 0      # for fixed-prize tiers (in GBP)
    prize_fund_pct: float = 0.0  # for pari-mutuel tiers
    description: str = ""


@dataclass(frozen=True)
class GameConfig:
    slug: str
    display_name: str
    main_pool: int            # highest main ball number
    main_pick: int            # how many main balls drawn
    bonus_pool: int           # highest bonus ball number
    bonus_count: int          # 1 for most games, 2 for EuroMillions
    bonus_shared_pool: bool   # True for Lotto (bonus from same 59-ball pool)
    draw_days: tuple          # e.g. ("Wednesday", "Saturday")
    xml_slug: str             # slug used in national-lottery.co.uk URL
    prize_tiers: tuple        # tuple of PrizeTier
    has_raffle: bool = False  # EuroMillions UK Millionaire Maker
    ticket_cost_gbp: float = 2.0

    def __str__(self) -> str:
        return self.display_name
