"""
Human number-picking bias model.

Based on research literature:
  - Henze & Riedwyl (1998) "How to Win More" — lottery number selection patterns
  - Simon (1999) UK Lottery study — birthday bias quantification
  - Cook & Clotfelter (1993) — systematic lottery number preferences

The model assigns a popularity multiplier to each number.
1.0 = average pick rate, >1.0 = over-picked by players, <1.0 = under-picked.

Expected value of jackpot share ∝ 1 / combination_popularity_score.
So the lower the score of your pick, the more you keep if you win.
"""

BIRTHDAY_RANGE = set(range(1, 32))    # 1–31 (date of month)

# Numbers ending in 0 or 5 are round/milestone — over-picked
ROUND_NUMBERS = {5, 10, 15, 20, 25, 30, 35, 40, 45, 50}

# Culturally popular "lucky" singles
POPULAR_SINGLES = {3, 7, 9, 11, 13, 21, 22}

# Numbers that end in 7 (e.g. 7, 17, 27, 37, 47) — "lucky 7" effect
SEVENS = {n for n in range(1, 60) if n % 10 == 7}

# Known sequential combos people play heavily
POPULAR_PATTERNS = [
    tuple(range(1, 7)),   # 1,2,3,4,5,6
    tuple(range(1, 8)),
    (7, 14, 21, 28, 35, 42),
    (5, 10, 15, 20, 25, 30),
    (1, 11, 21, 31, 41, 51),
    (2, 4, 6, 8, 10, 12),
]


class HumanBiasModel:
    """
    Calibrated bias multipliers for UK lottery player preferences.

    Presets:
      "research"     — literature-calibrated values (default)
      "conservative" — smaller adjustment factors
    """

    PRESETS = {
        "research": {
            "birthday_mult":   1.75,
            "round_mult":      1.30,
            "popular_mult":    1.25,
            "sevens_mult":     1.15,
            "first_number_mult": 1.20,
            "high_discount":   0.72,   # numbers > 31
            "very_high_discount": 0.85, # numbers > 45 (applied after high_discount)
        },
        "conservative": {
            "birthday_mult":   1.35,
            "round_mult":      1.15,
            "popular_mult":    1.10,
            "sevens_mult":     1.08,
            "first_number_mult": 1.10,
            "high_discount":   0.85,
            "very_high_discount": 0.92,
        },
    }

    def __init__(self, preset: str = "research"):
        self.cfg = self.PRESETS.get(preset, self.PRESETS["research"])

    def number_popularity_score(self, n: int, game) -> float:
        """
        Returns relative popularity multiplier for ball number n.
        Higher = more players choose this number.
        """
        cfg = self.cfg
        score = 1.0

        if n in BIRTHDAY_RANGE:
            score *= cfg["birthday_mult"]
        if n in ROUND_NUMBERS and n <= game.main_pool:
            score *= cfg["round_mult"]
        if n in POPULAR_SINGLES and n <= game.main_pool:
            score *= cfg["popular_mult"]
        if n in SEVENS and n <= game.main_pool:
            score *= cfg["sevens_mult"]
        if n == 1:
            score *= cfg["first_number_mult"]
        if n > 31:
            score *= cfg["high_discount"]
        if n > 45:
            score *= cfg["very_high_discount"]

        return round(score, 4)

    def bonus_popularity_score(self, n: int, game) -> float:
        """
        Popularity score for bonus ball numbers (separate smaller pool).
        EuroMillions Lucky Stars: 7 and 11 are heavily over-picked.
        """
        score = 1.0
        if n in POPULAR_SINGLES:
            score *= self.cfg["popular_mult"]
        if n in ROUND_NUMBERS:
            score *= self.cfg["round_mult"]
        if n <= min(12, game.bonus_pool):  # small pools — birthday bias compresses
            score *= 1.1
        return round(score, 4)

    def combination_popularity_score(self, combo: tuple, game) -> float:
        """
        Product of individual popularity scores for the combination.
        Lower = fewer players choose this combo = higher expected share if won.
        """
        score = 1.0
        for n in combo:
            score *= self.number_popularity_score(n, game)
        # Penalise fully sequential runs (these are heavy lottery plays)
        sorted_combo = sorted(combo)
        if self._has_sequential_run(sorted_combo, length=4):
            score *= 1.5
        # Penalise known popular patterns
        if sorted_combo in [list(p) for p in POPULAR_PATTERNS]:
            score *= 3.0
        return round(score, 6)

    def _has_sequential_run(self, balls: list, length: int = 4) -> bool:
        run = 1
        for i in range(1, len(balls)):
            if balls[i] == balls[i - 1] + 1:
                run += 1
                if run >= length:
                    return True
            else:
                run = 1
        return False

    def unpopularity_ranking(self, game) -> list:
        """All main ball numbers ranked from LEAST to MOST popular."""
        scores = [
            (n, self.number_popularity_score(n, game))
            for n in range(1, game.main_pool + 1)
        ]
        return sorted(scores, key=lambda x: x[1])

    def ev_improvement_vs_random(self, combo: tuple, game) -> float:
        """
        How many times better your expected jackpot share is vs a random pick.
        E.g. 3.2 means if you win, you'd expect ~3.2× more than an average ticket.
        """
        avg_score = sum(
            self.number_popularity_score(n, game)
            for n in range(1, game.main_pool + 1)
        ) / game.main_pool

        expected_combo_score = avg_score ** game.main_pick
        your_score = self.combination_popularity_score(combo, game)
        if your_score == 0:
            return 1.0
        return round(expected_combo_score / your_score, 2)
