from lottery.games.base import GameConfig, PrizeTier

# All prizes are FIXED — no jackpot sharing. Max prize £500,000.

GAME_CONFIG = GameConfig(
    slug="thunderball",
    display_name="Thunderball",
    main_pool=39,
    main_pick=5,
    bonus_pool=14,      # Thunderball
    bonus_count=1,
    bonus_shared_pool=False,
    draw_days=("Tuesday", "Wednesday", "Friday", "Saturday"),
    xml_slug="thunderball",
    ticket_cost_gbp=1.00,
    prize_tiers=(
        PrizeTier("Match 5 + Thunderball", 5, 1, 8_060_598, "fixed", fixed_value=500_000),
        PrizeTier("Match 5",               5, 0,   620_046, "fixed", fixed_value=5_000),
        PrizeTier("Match 4 + Thunderball", 4, 1,   114_008, "fixed", fixed_value=250),
        PrizeTier("Match 4",               4, 0,     8_770, "fixed", fixed_value=100),
        PrizeTier("Match 3 + Thunderball", 3, 1,     1_938, "fixed", fixed_value=20),
        PrizeTier("Match 3",               3, 0,       149, "fixed", fixed_value=10),
        PrizeTier("Match 2 + Thunderball", 2, 1,        80, "fixed", fixed_value=10),
        PrizeTier("Match 1 + Thunderball", 1, 1,        29, "fixed", fixed_value=5),
        PrizeTier("Match 0 + Thunderball", 0, 1,        13, "fixed", fixed_value=3),
    ),
)
