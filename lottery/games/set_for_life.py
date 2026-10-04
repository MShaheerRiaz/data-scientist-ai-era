from lottery.games.base import GameConfig, PrizeTier

# Top prize: £10,000/month for 30 years = £3,600,000 nominal
# NPV at 3% discount rate ≈ £2,380,000

GAME_CONFIG = GameConfig(
    slug="set-for-life",
    display_name="Set For Life",
    main_pool=47,
    main_pick=5,
    bonus_pool=10,      # Life Ball
    bonus_count=1,
    bonus_shared_pool=False,
    draw_days=("Monday", "Thursday"),
    xml_slug="set-for-life",
    ticket_cost_gbp=1.50,
    prize_tiers=(
        PrizeTier("Match 5 + Life Ball",  5, 1, 15_339_390, "monthly",
                  fixed_value=3_600_000, description="£10,000/month for 30 years"),
        PrizeTier("Match 5",              5, 0,  1_704_377, "fixed",  fixed_value=10_000),
        PrizeTier("Match 4 + Life Ball",  4, 1,    341_808, "fixed",  fixed_value=250),
        PrizeTier("Match 4",              4, 0,     37_990, "fixed",  fixed_value=50),
        PrizeTier("Match 3 + Life Ball",  3, 1,      8_002, "fixed",  fixed_value=30),
        PrizeTier("Match 3",              3, 0,        888, "fixed",  fixed_value=20),
        PrizeTier("Match 2 + Life Ball",  2, 1,        188, "fixed",  fixed_value=10),
        PrizeTier("Match 1 + Life Ball",  1, 1,         35, "fixed",  fixed_value=4),
    ),
)
