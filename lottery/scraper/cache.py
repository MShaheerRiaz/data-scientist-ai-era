import csv
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass
class DrawResult:
    draw_date: datetime
    draw_number: int
    main_balls: tuple        # sorted tuple of main ball integers
    bonus_balls: tuple       # tuple of bonus ball integers
    jackpot_value: int = 0   # in pence, 0 if unknown


CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "cache"

# Which weekdays each game draws on (0=Monday)
DRAW_WEEKDAYS = {
    "lotto":        {2, 5},        # Wed, Sat
    "euromillions": {1, 4},        # Tue, Fri
    "set-for-life": {0, 3},        # Mon, Thu
    "thunderball":  {1, 2, 4, 5},  # Tue, Wed, Fri, Sat
}

COLUMNS = {
    "lotto":        ["draw_date", "draw_number", "b1", "b2", "b3", "b4", "b5", "b6", "bonus1", "jackpot_pence"],
    "euromillions": ["draw_date", "draw_number", "b1", "b2", "b3", "b4", "b5", "ls1", "ls2", "jackpot_pence"],
    "set-for-life": ["draw_date", "draw_number", "b1", "b2", "b3", "b4", "b5", "life_ball", "jackpot_pence"],
    "thunderball":  ["draw_date", "draw_number", "b1", "b2", "b3", "b4", "b5", "thunderball", "jackpot_pence"],
}


class DrawCache:
    def __init__(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _path(self, slug: str) -> Path:
        return CACHE_DIR / f"{slug}.csv"

    def load(self, slug: str) -> list:
        path = self._path(slug)
        if not path.exists():
            return []
        draws = []
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    draws.append(self._row_to_draw(slug, row))
                except (ValueError, KeyError):
                    continue
        return sorted(draws, key=lambda d: d.draw_date, reverse=True)

    def save(self, slug: str, draws: list):
        existing = {d.draw_number: d for d in self.load(slug)}
        for d in draws:
            existing[d.draw_number] = d
        merged = sorted(existing.values(), key=lambda d: d.draw_date, reverse=True)
        cols = COLUMNS[slug]
        path = self._path(slug)
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            for draw in merged:
                writer.writerow(self._draw_to_row(slug, draw))

    def is_stale(self, slug: str) -> bool:
        path = self._path(slug)
        if not path.exists():
            return True
        draws = self.load(slug)
        if not draws:
            return True
        most_recent = draws[0].draw_date
        # Consider stale if we've passed a draw day by more than 6 hours
        now = datetime.now(timezone.utc)
        weekdays = DRAW_WEEKDAYS.get(slug, set())
        draw_time_utc = most_recent.replace(hour=20, minute=0, second=0, microsecond=0,
                                             tzinfo=timezone.utc)
        for i in range(1, 8):
            candidate = draw_time_utc + timedelta(days=i)
            if candidate.weekday() in weekdays:
                return now > candidate + timedelta(hours=6)
        return False

    def most_recent_date(self, slug: str):
        draws = self.load(slug)
        return draws[0].draw_date if draws else None

    def _row_to_draw(self, slug: str, row: dict) -> DrawResult:
        date = datetime.fromisoformat(row["draw_date"]).replace(tzinfo=timezone.utc)
        num = int(row["draw_number"])
        jackpot = int(row.get("jackpot_pence", 0) or 0)

        if slug == "lotto":
            main = tuple(sorted(int(row[f"b{i}"]) for i in range(1, 7)))
            bonus = (int(row["bonus1"]),)
        elif slug == "euromillions":
            main = tuple(sorted(int(row[f"b{i}"]) for i in range(1, 6)))
            bonus = (int(row["ls1"]), int(row["ls2"]))
        elif slug == "set-for-life":
            main = tuple(sorted(int(row[f"b{i}"]) for i in range(1, 6)))
            bonus = (int(row["life_ball"]),)
        elif slug == "thunderball":
            main = tuple(sorted(int(row[f"b{i}"]) for i in range(1, 6)))
            bonus = (int(row["thunderball"]),)
        else:
            raise ValueError(f"Unknown slug: {slug}")

        return DrawResult(draw_date=date, draw_number=num, main_balls=main,
                          bonus_balls=bonus, jackpot_value=jackpot)

    def _draw_to_row(self, slug: str, draw: DrawResult) -> dict:
        row = {
            "draw_date": draw.draw_date.strftime("%Y-%m-%d"),
            "draw_number": draw.draw_number,
            "jackpot_pence": draw.jackpot_value,
        }
        if slug == "lotto":
            for i, b in enumerate(draw.main_balls, 1):
                row[f"b{i}"] = b
            row["bonus1"] = draw.bonus_balls[0]
        elif slug == "euromillions":
            for i, b in enumerate(draw.main_balls, 1):
                row[f"b{i}"] = b
            row["ls1"] = draw.bonus_balls[0]
            row["ls2"] = draw.bonus_balls[1]
        elif slug == "set-for-life":
            for i, b in enumerate(draw.main_balls, 1):
                row[f"b{i}"] = b
            row["life_ball"] = draw.bonus_balls[0]
        elif slug == "thunderball":
            for i, b in enumerate(draw.main_balls, 1):
                row[f"b{i}"] = b
            row["thunderball"] = draw.bonus_balls[0]
        return row
