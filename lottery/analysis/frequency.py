from collections import Counter, defaultdict
from datetime import datetime


class DrawFrequencyAnalyzer:
    def __init__(self, draws: list, game_config):
        self.draws = draws
        self.game = game_config

    # ------------------------------------------------------------------ #
    # Filtered draw helpers
    # ------------------------------------------------------------------ #

    def _since_date_draws(self, since_date=None) -> list:
        if since_date is None:
            return self.draws
        return [d for d in self.draws if d.draw_date >= since_date]

    def _recent_draws(self, last_n: int) -> list:
        return self.draws[:last_n]

    # ------------------------------------------------------------------ #
    # Main ball frequencies
    # ------------------------------------------------------------------ #

    def main_ball_frequencies(self, since_date=None) -> dict:
        """Raw count of appearances per main ball number."""
        counter: Counter = Counter()
        for draw in self._since_date_draws(since_date):
            counter.update(draw.main_balls)
        return dict(counter)

    def bonus_ball_frequencies(self, since_date=None) -> dict:
        """Raw count of bonus ball appearances (excluded from main if shared pool)."""
        counter: Counter = Counter()
        for draw in self._since_date_draws(since_date):
            counter.update(draw.bonus_balls)
        return dict(counter)

    def expected_frequency(self, n_draws: int) -> float:
        """Expected appearances per ball = n_draws × (picks / pool_size)."""
        return n_draws * (self.game.main_pick / self.game.main_pool)

    def deviation_from_expected(self, since_date=None) -> dict:
        """
        (actual - expected) / expected per ball number.
        Positive = hot (drawn more than expected), negative = cold.
        """
        freqs = self.main_ball_frequencies(since_date)
        n_draws = len(self._since_date_draws(since_date))
        if n_draws == 0:
            return {n: 0.0 for n in range(1, self.game.main_pool + 1)}
        expected = self.expected_frequency(n_draws)
        return {
            n: (freqs.get(n, 0) - expected) / expected
            for n in range(1, self.game.main_pool + 1)
        }

    def overdue_balls(self, threshold_draws: int = 20) -> list:
        """Main balls not seen in the last `threshold_draws` draws."""
        recent = set()
        for draw in self.draws[:threshold_draws]:
            recent.update(draw.main_balls)
        all_balls = set(range(1, self.game.main_pool + 1))
        return sorted(all_balls - recent)

    def recent_frequency(self, last_n: int = 52) -> dict:
        """Frequency over the most recent N draws."""
        return self.main_ball_frequencies() if len(self.draws) <= last_n else \
            self._freq_from_draws(self._recent_draws(last_n))

    def _freq_from_draws(self, draws: list) -> dict:
        counter: Counter = Counter()
        for draw in draws:
            counter.update(draw.main_balls)
        return dict(counter)

    def hot_balls(self, top_n: int = 10, since_date=None) -> list:
        """Top N most frequently drawn main balls."""
        freqs = self.main_ball_frequencies(since_date)
        return sorted(freqs, key=freqs.get, reverse=True)[:top_n]

    def cold_balls(self, top_n: int = 10, since_date=None) -> list:
        """Top N least frequently drawn main balls (from full pool)."""
        freqs = self.main_ball_frequencies(since_date)
        all_balls = list(range(1, self.game.main_pool + 1))
        return sorted(all_balls, key=lambda n: freqs.get(n, 0))[:top_n]

    def co_occurrence_matrix(self, since_date=None) -> dict:
        """How often each pair of main balls appears together."""
        co: dict = defaultdict(int)
        for draw in self._since_date_draws(since_date):
            balls = sorted(draw.main_balls)
            for i in range(len(balls)):
                for j in range(i + 1, len(balls)):
                    co[(balls[i], balls[j])] += 1
        return dict(co)

    def number_summary(self, since_date=None) -> list:
        """Return sorted list of (ball, count, deviation) for all main balls."""
        freqs = self.main_ball_frequencies(since_date)
        devs = self.deviation_from_expected(since_date)
        n_draws = len(self._since_date_draws(since_date))
        expected = self.expected_frequency(n_draws) if n_draws else 0
        result = []
        for n in range(1, self.game.main_pool + 1):
            result.append({
                "ball": n,
                "count": freqs.get(n, 0),
                "expected": round(expected, 1),
                "deviation": round(devs.get(n, 0.0) * 100, 1),  # as percentage
            })
        return result
