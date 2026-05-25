"""
SmartPicker — generates number combinations that maximise expected jackpot share.

Core algorithm:
  1. Score each ball number using popularity model + frequency deviation
  2. Generate N candidate combinations via weighted sampling
  3. Score each candidate by combination_popularity_score (lower = better EV)
  4. Filter out hard-excluded patterns (sequential, all-birthday, etc.)
  5. Return top K combinations with full rationale
"""
import math
import random
from dataclasses import dataclass

from lottery.analysis.frequency import DrawFrequencyAnalyzer
from lottery.analysis.popularity import HumanBiasModel


@dataclass
class PickResult:
    main_balls: tuple
    bonus_balls: tuple
    ev_multiplier: float       # expected jackpot share vs average ticket
    popularity_score: float    # lower = fewer people would choose this
    birthday_count: int        # how many balls <= 31
    spread: int                # max - min of main balls
    strategy: str
    rationale: str


class SmartPicker:
    STRATEGIES = ("ev", "cold", "balanced")

    def __init__(
        self,
        game_config,
        draws: list,
        strategy: str = "ev",
        bias_preset: str = "research",
        n_candidates: int = 50_000,
    ):
        self.game = game_config
        self.draws = draws
        self.strategy = strategy
        self.n_candidates = n_candidates
        self.bias_model = HumanBiasModel(preset=bias_preset)
        self.freq_analyzer = DrawFrequencyAnalyzer(draws, game_config)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def generate(self, count: int = 5) -> list:
        """Return `count` PickResult objects, best first."""
        number_scores = self._build_number_scores()
        bonus_scores = self._build_bonus_scores()

        candidates = self._sample_candidates(number_scores, count * 200)
        scored = [self._score_candidate(c) for c in candidates]
        scored = [s for s in scored if self._passes_filters(s)]

        # Deduplicate
        seen = set()
        unique = []
        for pick in scored:
            key = pick.main_balls
            if key not in seen:
                seen.add(key)
                unique.append(pick)

        unique.sort(key=lambda p: p.ev_multiplier, reverse=True)

        # Now attach bonus balls to each pick
        bonus_ball = self._pick_bonus_ball(bonus_scores)
        for pick in unique:
            object.__setattr__(pick, "bonus_balls", bonus_ball) if False else None
            pick = PickResult(
                main_balls=pick.main_balls,
                bonus_balls=self._pick_bonus_ball(bonus_scores),
                ev_multiplier=pick.ev_multiplier,
                popularity_score=pick.popularity_score,
                birthday_count=pick.birthday_count,
                spread=pick.spread,
                strategy=self.strategy,
                rationale=pick.rationale,
            )

        # Rebuild after bonus assignment
        results = []
        seen = set()
        for pick in unique:
            key = pick.main_balls
            if key not in seen:
                seen.add(key)
                bonus = self._pick_bonus_ball(bonus_scores)
                results.append(PickResult(
                    main_balls=pick.main_balls,
                    bonus_balls=bonus,
                    ev_multiplier=pick.ev_multiplier,
                    popularity_score=pick.popularity_score,
                    birthday_count=pick.birthday_count,
                    spread=pick.spread,
                    strategy=self.strategy,
                    rationale=self._build_rationale(pick),
                ))
            if len(results) >= count:
                break

        # Pad if not enough candidates pass filters
        while len(results) < count:
            results.append(self._fallback_pick(bonus_scores))

        return results[:count]

    # ------------------------------------------------------------------ #
    # Scoring
    # ------------------------------------------------------------------ #

    def _build_number_scores(self) -> dict:
        """Composite score per ball: higher = more desirable for this strategy."""
        devs = self.freq_analyzer.deviation_from_expected()
        scores = {}
        for n in range(1, self.game.main_pool + 1):
            pop = self.bias_model.number_popularity_score(n, self.game)
            freq_dev = devs.get(n, 0.0)

            if self.strategy == "ev":
                # Prefer under-picked (low popularity) — maximise expected share
                bias_weight, freq_weight = 0.85, 0.15
            elif self.strategy == "cold":
                # Prefer cold (under-drawn) and under-picked
                bias_weight, freq_weight = 0.50, 0.50
            else:  # balanced
                bias_weight, freq_weight = 0.70, 0.30

            # bias component: high when popularity is LOW (inverted)
            bias_component = 1.0 / pop
            # freq component: high when ball is cold (negative deviation)
            freq_component = 1.0 - freq_dev  # cold balls have negative dev

            scores[n] = bias_weight * bias_component + freq_weight * freq_component

        return scores

    def _build_bonus_scores(self) -> dict:
        """Score for bonus ball pool (separate from main)."""
        bonus_freqs = self.freq_analyzer.bonus_ball_frequencies()
        n_draws = len(self.draws)
        scores = {}
        for n in range(1, self.game.bonus_pool + 1):
            pop = self.bias_model.bonus_popularity_score(n, self.game)
            freq = bonus_freqs.get(n, 0)
            expected = n_draws * (self.game.bonus_count / self.game.bonus_pool) if n_draws else 1
            deviation = (freq - expected) / expected if expected else 0
            scores[n] = (1.0 / pop) * (1.0 - deviation * 0.3)
        return scores

    # ------------------------------------------------------------------ #
    # Sampling
    # ------------------------------------------------------------------ #

    def _weighted_sample_no_replace(self, pool: list, weights: list, k: int) -> list:
        """Weighted sampling without replacement using stdlib random."""
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
        weights = [scores[n] for n in pool]
        candidates = set()
        pick_size = self.game.main_pick
        attempts = 0
        max_attempts = n * 3
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
        return PickResult(
            main_balls=combo,
            bonus_balls=(),
            ev_multiplier=ev_mult,
            popularity_score=pop_score,
            birthday_count=birthday_count,
            spread=spread,
            strategy=self.strategy,
            rationale="",
        )

    # ------------------------------------------------------------------ #
    # Filtering
    # ------------------------------------------------------------------ #

    def _passes_filters(self, pick: PickResult) -> bool:
        balls = sorted(pick.main_balls)
        pick_size = self.game.main_pick

        # No more than 2 birthday numbers for games with pool > 31
        if self.game.main_pool > 31 and pick.birthday_count > 2:
            return False

        # Minimum spread
        min_spread = 30 if pick_size >= 6 else 20
        if pick.spread < min_spread:
            return False

        # No 4+ consecutive numbers
        if self._has_consecutive_run(balls, 4):
            return False

        # Not all numbers ending in same digit
        endings = [n % 10 for n in balls]
        if len(set(endings)) <= 1:
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
    # Bonus ball + rationale
    # ------------------------------------------------------------------ #

    def _pick_bonus_ball(self, bonus_scores: dict) -> tuple:
        if self.game.bonus_count == 0:
            return ()
        pool = list(bonus_scores.keys())
        weights = [bonus_scores[n] for n in pool]
        count = self.game.bonus_count
        chosen = self._weighted_sample_no_replace(pool, weights, count)
        return tuple(sorted(chosen))

    def _build_rationale(self, pick: PickResult) -> str:
        parts = []
        high_balls = [n for n in pick.main_balls if n > 31]
        if high_balls:
            parts.append(f"{len(high_balls)} numbers above 31 (avoids birthday bias)")
        if pick.spread > 40:
            parts.append(f"wide spread of {pick.spread} (avoids popular clustered picks)")
        if pick.ev_multiplier > 1.5:
            parts.append(f"~{pick.ev_multiplier:.1f}× expected jackpot share vs average ticket")
        if not parts:
            parts.append("statistically under-picked combination")
        return "; ".join(parts)

    def _fallback_pick(self, bonus_scores: dict) -> PickResult:
        """Fallback: simple high-number pick when candidates run out."""
        high_pool = list(range(max(32, self.game.main_pool // 2), self.game.main_pool + 1))
        if len(high_pool) >= self.game.main_pick:
            balls = tuple(sorted(random.sample(high_pool, self.game.main_pick)))
        else:
            balls = tuple(sorted(random.sample(range(1, self.game.main_pool + 1), self.game.main_pick)))
        bonus = self._pick_bonus_ball(bonus_scores)
        pop = self.bias_model.combination_popularity_score(balls, self.game)
        ev = self.bias_model.ev_improvement_vs_random(balls, self.game)
        return PickResult(
            main_balls=balls,
            bonus_balls=bonus,
            ev_multiplier=ev,
            popularity_score=pop,
            birthday_count=sum(1 for n in balls if n <= 31),
            spread=max(balls) - min(balls),
            strategy=self.strategy,
            rationale="fallback high-range pick",
        )
