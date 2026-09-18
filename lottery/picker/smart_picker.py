"""
SmartPicker v2 — research-upgraded.

Changes from v1:
  - Removed hot/cold frequency weighting (zero predictive value per academic consensus)
  - Now uses PURE popularity model (the only proven edge)
  - New filters: sum range, odd/even balance, high/low balance
  - Updated Lucky Star strategy: prefer 10, 11, 12 (under-picked)
  - Avoids most popular pairs (23+44, 20+23, 42+44)
  - Avoids full multiples-of-7 subsets

Based on:
  - Henze & Riedwyl (1998): sum heuristic
  - Wang et al. (2016): number 7 at 1.55×
  - Simon (1999): birthday bias quantification
  - Research finding: 70% of EuroMillions draws have sum 100–175
  - Research finding: 3+2 odd/even split in 33.7% of draws
"""
import random
from dataclasses import dataclass

from lottery.analysis.popularity import HumanBiasModel

# Most commonly co-drawn pairs — also likely to be picked by stats-aware players
POPULAR_PAIRS = {(19, 44), (20, 23), (23, 44), (42, 44), (17, 29)}

# Multiples of 7 set (Southampton study: most popular UK pattern)
MULTIPLES_OF_7 = {7, 14, 21, 28, 35, 42, 49}


@dataclass
class PickResult:
    main_balls: tuple
    bonus_balls: tuple
    ev_multiplier: float
    popularity_score: float
    birthday_count: int
    spread: int
    ball_sum: int
    odd_count: int
    strategy: str
    rationale: str


class SmartPicker:

    def __init__(
        self,
        game_config,
        draws: list,
        strategy: str = "ev",
        bias_preset: str = "research",
        n_candidates: int = 80_000,
    ):
        self.game = game_config
        self.draws = draws
        self.strategy = strategy
        self.n_candidates = n_candidates
        self.bias_model = HumanBiasModel(preset=bias_preset)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def generate(self, count: int = 5) -> list:
        number_scores = self._build_number_scores()
        bonus_scores = self._build_bonus_scores()

        candidates = self._sample_candidates(number_scores, self.n_candidates)
        scored = [self._score_candidate(c) for c in candidates]
        scored = [s for s in scored if self._passes_filters(s)]
        scored.sort(key=lambda p: p.ev_multiplier, reverse=True)

        # Deduplicate
        seen = set()
        unique = []
        for pick in scored:
            if pick.main_balls not in seen:
                seen.add(pick.main_balls)
                unique.append(pick)

        results = []
        for pick in unique:
            bonus = self._pick_bonus_balls(bonus_scores)
            results.append(PickResult(
                main_balls=pick.main_balls,
                bonus_balls=bonus,
                ev_multiplier=pick.ev_multiplier,
                popularity_score=pick.popularity_score,
                birthday_count=pick.birthday_count,
                spread=pick.spread,
                ball_sum=pick.ball_sum,
                odd_count=pick.odd_count,
                strategy=self.strategy,
                rationale=self._build_rationale(pick, bonus),
            ))
            if len(results) >= count:
                break

        while len(results) < count:
            results.append(self._fallback_pick(bonus_scores))

        return results[:count]

    # ------------------------------------------------------------------ #
    # Number scoring — pure popularity model (hot/cold removed)
    # ------------------------------------------------------------------ #

    def _build_number_scores(self) -> dict:
        """
        Score each number purely by unpopularity (inverse of player preference).
        Hot/cold frequency weighting removed — zero academic support for predictive value.
        """
        scores = {}
        for n in range(1, self.game.main_pool + 1):
            pop = self.bias_model.number_popularity_score(n, self.game)
            scores[n] = 1.0 / pop  # higher = less popular = better EV
        return scores

    def _build_bonus_scores(self) -> dict:
        scores = {}
        for n in range(1, self.game.bonus_pool + 1):
            pop = self.bias_model.bonus_popularity_score(n, self.game)
            scores[n] = 1.0 / pop
        return scores

    # ------------------------------------------------------------------ #
    # Sampling
    # ------------------------------------------------------------------ #

    def _weighted_sample_no_replace(self, pool: list, weights: list, k: int) -> list:
        result = []
        remaining_pool = list(pool)
        remaining_weights = list(weights)
        for _ in range(k):
            if not remaining_pool:
                break
            total = sum(remaining_weights)
            r = random.uniform(0, total)
            cumulative = 0.0
            chosen_idx = len(remaining_pool) - 1
            for i, w in enumerate(remaining_weights):
                cumulative += w
                if cumulative >= r:
                    chosen_idx = i
                    break
            result.append(remaining_pool[chosen_idx])
            remaining_pool.pop(chosen_idx)
            remaining_weights.pop(chosen_idx)
        return result

    def _sample_candidates(self, scores: dict, n: int) -> list:
        pool = list(scores.keys())
        weights = [scores[k] for k in pool]
        candidates = set()
        pick_size = self.game.main_pick
        attempts = 0
        max_attempts = n * 4
        while len(candidates) < n and attempts < max_attempts:
            balls = self._weighted_sample_no_replace(pool, weights, pick_size)
            candidates.add(tuple(sorted(balls)))
            attempts += 1
        return list(candidates)

    def _score_candidate(self, combo: tuple) -> PickResult:
        pop_score = self.bias_model.combination_popularity_score(combo, self.game)
        ev_mult = self.bias_model.ev_improvement_vs_random(combo, self.game)
        birthday_count = sum(1 for n in combo if n <= 31)
        spread = max(combo) - min(combo)
        ball_sum = sum(combo)
        odd_count = sum(1 for n in combo if n % 2 == 1)
        return PickResult(
            main_balls=combo,
            bonus_balls=(),
            ev_multiplier=ev_mult,
            popularity_score=pop_score,
            birthday_count=birthday_count,
            spread=spread,
            ball_sum=ball_sum,
            odd_count=odd_count,
            strategy=self.strategy,
            rationale="",
        )

    # ------------------------------------------------------------------ #
    # Filters — research-grounded
    # ------------------------------------------------------------------ #

    def _passes_filters(self, pick: PickResult) -> bool:
        balls = sorted(pick.main_balls)
        pick_size = self.game.main_pick
        pool = self.game.main_pool

        # Max 2 birthday numbers (Simon 1999: over-represented in player choices)
        if pool > 31 and pick.birthday_count > 2:
            return False

        # Sum range filter (Henze & Riedwyl; 70% of EuroMillions draws in 100–175)
        if pick_size == 5:
            if not (95 <= pick.ball_sum <= 175):
                return False
        elif pick_size == 6:
            if not (110 <= pick.ball_sum <= 210):
                return False

        # Minimum spread
        min_spread = 28 if pick_size >= 5 else 20
        if pick.spread < min_spread:
            return False

        # No 4+ consecutive numbers (heavily played patterns)
        if self._has_consecutive_run(balls, 4):
            return False

        # Odd/even balance: reject all-odd or all-even
        if pick.odd_count == 0 or pick.odd_count == pick_size:
            return False

        # High/low balance: reject all numbers below 15 or all above 40
        if all(n < 15 for n in balls) or all(n > 40 for n in balls):
            return False

        # Avoid most popular pairs (also likely picked by stats-aware players)
        for pair in POPULAR_PAIRS:
            if pair[0] in pick.main_balls and pair[1] in pick.main_balls:
                return False

        # Reject 4+ multiples of 7 in one combo (Southampton: most popular UK pattern)
        if sum(1 for n in pick.main_balls if n in MULTIPLES_OF_7) >= 4:
            return False

        # Not all numbers ending in same digit
        if len({n % 10 for n in balls}) <= 1:
            return False

        return True

    def _has_consecutive_run(self, balls: list, length: int) -> bool:
        run = 1
        for i in range(1, len(balls)):
            if balls[i] == balls[i - 1] + 1:
                run += 1
                if run >= length:
                    return True
            else:
                run = 1
        return False

    # ------------------------------------------------------------------ #
    # Bonus balls
    # ------------------------------------------------------------------ #

    def _pick_bonus_balls(self, bonus_scores: dict) -> tuple:
        if self.game.bonus_count == 0:
            return ()
        pool = list(bonus_scores.keys())
        weights = [bonus_scores[n] for n in pool]

        if self.game.slug == "euromillions":
            # Strongly prefer Stars 9, 10, 11, 12 (under-picked by players)
            # Avoid both Stars being in {1,2,3,7} (over-picked)
            for _ in range(200):
                chosen = self._weighted_sample_no_replace(pool, weights, 2)
                chosen_set = set(chosen)
                over_picked = {1, 2, 3, 7}
                # Allow max 1 over-picked star
                if len(chosen_set & over_picked) <= 1:
                    return tuple(sorted(chosen))
            # Fallback
            chosen = self._weighted_sample_no_replace(pool, weights, 2)
            return tuple(sorted(chosen))

        chosen = self._weighted_sample_no_replace(pool, weights, self.game.bonus_count)
        return tuple(sorted(chosen))

    # ------------------------------------------------------------------ #
    # Rationale
    # ------------------------------------------------------------------ #

    def _build_rationale(self, pick: PickResult, bonus: tuple) -> str:
        parts = []
        high = sum(1 for n in pick.main_balls if n > 31)
        if high >= 3:
            parts.append(f"{high}/{pick.ball_sum} — {high} numbers above 31 (avoids birthday bias)")
        if pick.ev_multiplier >= 10:
            parts.append(f"~{pick.ev_multiplier:.0f}× expected jackpot share vs average ticket")
        odd_even = f"{pick.odd_count} odd / {self.game.main_pick - pick.odd_count} even"
        parts.append(odd_even)
        if self.game.slug == "euromillions" and bonus:
            under_picked_stars = [s for s in bonus if s >= 9]
            if under_picked_stars:
                parts.append(f"Lucky Stars {bonus[0]}&{bonus[1]} — both under-picked by players")
        if not parts:
            parts.append("statistically under-picked combination")
        return "; ".join(parts)

    def _fallback_pick(self, bonus_scores: dict) -> PickResult:
        high_pool = list(range(max(32, self.game.main_pool // 2), self.game.main_pool + 1))
        if len(high_pool) >= self.game.main_pick:
            balls = tuple(sorted(random.sample(high_pool, self.game.main_pick)))
        else:
            balls = tuple(sorted(random.sample(range(1, self.game.main_pool + 1), self.game.main_pick)))
        bonus = self._pick_bonus_balls(bonus_scores)
        pop = self.bias_model.combination_popularity_score(balls, self.game)
        ev = self.bias_model.ev_improvement_vs_random(balls, self.game)
        return PickResult(
            main_balls=balls,
            bonus_balls=bonus,
            ev_multiplier=ev,
            popularity_score=pop,
            birthday_count=sum(1 for n in balls if n <= 31),
            spread=max(balls) - min(balls),
            ball_sum=sum(balls),
            odd_count=sum(1 for n in balls if n % 2 == 1),
            strategy=self.strategy,
            rationale="fallback high-range pick",
        )
