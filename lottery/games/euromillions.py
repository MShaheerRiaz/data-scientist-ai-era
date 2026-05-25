from lottery.games.base import GameConfig, PrizeTier

GAME_CONFIG = GameConfig(
    slug="euromillions",
    display_name="EuroMillions",
    main_pool=50,
    main_pick=5,
    bonus_pool=12,      # Lucky Stars
    bonus_count=2,
    bonus_shared_pool=False,
    draw_days=("Tuesday", "Friday"),
    xml_slug="euromillions",
    ticket_cost_gbp=2.50,
    has_raffle=True,
    prize_tiers=(
        PrizeTier("Jackpot (5+2)",          5, 2, 139_838_160, "pari_mutuel", description="Shared EU jackpot"),
        PrizeTier("Match 5+1",              5, 1,   6_991_908, "pari_mutuel"),
        PrizeTier("Match 5",                5, 0,   3_107_515, "pari_mutuel"),
        PrizeTier("Match 4+2",              4, 2,     621_503, "pari_mutuel"),
        PrizeTier("Match 4+1",              4, 1,      26_126, "pari_mutuel"),
        PrizeTier("Match 4",                4, 0,      13_811, "fixed", fixed_value=100),
        PrizeTier("Match 3+2",              3, 2,       6_531, "fixed", fixed_value=100),
        PrizeTier("Match 3+1",              3, 1,         988, "fixed", fixed_value=13),
        PrizeTier("Match 2+2",              2, 2,         985, "fixed", fixed_value=10),
        PrizeTier("Match 3",                3, 0,         569, "fixed", fixed_value=10),
        PrizeTier("Match 1+2",              1, 2,         235, "fixed", fixed_value=7),
        PrizeTier("Match 2+1",              2, 1,         173, "fixed", fixed_value=6),
        PrizeTier("Match 2",                2, 0,          22, "fixed", fixed_value=5),
        PrizeTier("UK Millionaire Maker",   0, 0,   6_000_000, "raffle", fixed_value=1_000_000,
                  description="Guaranteed £1M raffle with every ticket"),
    ),
)
