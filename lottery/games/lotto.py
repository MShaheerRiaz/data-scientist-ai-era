from lottery.games.base import GameConfig, PrizeTier

GAME_CONFIG = GameConfig(
    slug="lotto",
    display_name="Lotto",
    main_pool=59,
    main_pick=6,
    bonus_pool=59,
    bonus_count=1,
    bonus_shared_pool=True,
    draw_days=("Wednesday", "Saturday"),
    xml_slug="lotto",
    ticket_cost_gbp=2.0,
    prize_tiers=(
        PrizeTier("Jackpot",          6, 0, 45_057_474, "pari_mutuel", prize_fund_pct=0.57),
        PrizeTier("Match 5 + Bonus",  5, 1,  7_509_579, "pari_mutuel", prize_fund_pct=0.0, description="~£1M"),
        PrizeTier("Match 5",          5, 0,    144_415, "pari_mutuel", prize_fund_pct=0.0, description="~£1,750"),
        PrizeTier("Match 4",          4, 0,      2_180, "fixed",       fixed_value=140),
        PrizeTier("Match 3",          3, 0,         97, "fixed",       fixed_value=30),
        PrizeTier("Match 2",          2, 0,         11, "fixed",       fixed_value=2),
    ),
)
