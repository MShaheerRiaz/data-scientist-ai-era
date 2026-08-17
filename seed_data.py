"""
Seed script: generates synthetic but statistically realistic historical draw data
for all four UK National Lottery games. Run this once before using the picker.

Data is generated using uniform random sampling (matching the actual lottery RNG).
The frequency distribution will naturally approximate real historical data.
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

DATA_DIR = Path("data/cache")
DATA_DIR.mkdir(parents=True, exist_ok=True)

random.seed(42)  # reproducible seed — change for different random data


def draw_dates(start: date, end: date, weekdays: set) -> list:
    """Return all dates between start and end that fall on given weekdays (0=Mon)."""
    dates = []
    current = start
    while current <= end:
        if current.weekday() in weekdays:
            dates.append(current)
        current += timedelta(days=1)
    return dates


def pick_balls(pool: int, n: int) -> tuple:
    return tuple(sorted(random.sample(range(1, pool + 1), n)))


def generate_lotto():
    """Lotto: 6 from 1-59 + bonus from remaining 53. Wed & Sat since Oct 1994."""
    path = DATA_DIR / "lotto.csv"
    # Post-2015 pool (1-59). Use Oct 2015 onwards for current format.
    dates = draw_dates(date(2015, 10, 10), date(2025, 12, 31), {2, 5})
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["draw_date", "draw_number", "b1", "b2", "b3", "b4", "b5", "b6", "bonus1", "jackpot_pence"])
        for i, d in enumerate(reversed(dates), start=2200):
            main = pick_balls(59, 6)
            remaining = [n for n in range(1, 60) if n not in main]
            bonus = random.choice(remaining)
            jackpot = random.randint(2_000_000, 8_000_000) * 100
            writer.writerow([d.isoformat(), i, *main, bonus, jackpot])
    print(f"Lotto:      {len(dates):,} draws written → {path}")


def generate_euromillions():
    """EuroMillions: 5 from 1-50 + 2 Lucky Stars from 1-12. Tue & Fri since 2004."""
    path = DATA_DIR / "euromillions.csv"
    dates = draw_dates(date(2004, 2, 13), date(2025, 12, 31), {1, 4})
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["draw_date", "draw_number", "b1", "b2", "b3", "b4", "b5", "ls1", "ls2", "jackpot_pence"])
        for i, d in enumerate(reversed(dates), start=1):
            main = pick_balls(50, 5)
            stars = pick_balls(12, 2)
            jackpot = random.randint(17_000_000, 200_000_000) * 100
            writer.writerow([d.isoformat(), i, *main, *stars, jackpot])
    print(f"EuroMilli.: {len(dates):,} draws written → {path}")


def generate_set_for_life():
    """Set For Life: 5 from 1-47 + Life Ball from 1-10. Mon & Thu since Mar 2019."""
    path = DATA_DIR / "set-for-life.csv"
    dates = draw_dates(date(2019, 3, 18), date(2025, 12, 31), {0, 3})
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["draw_date", "draw_number", "b1", "b2", "b3", "b4", "b5", "life_ball", "jackpot_pence"])
        for i, d in enumerate(reversed(dates), start=1):
            main = pick_balls(47, 5)
            lb = random.randint(1, 10)
            jackpot = 360_000_000  # £3.6M in pence (annuity)
            writer.writerow([d.isoformat(), i, *main, lb, jackpot])
    print(f"Set 4 Life: {len(dates):,} draws written → {path}")


def generate_thunderball():
    """Thunderball: 5 from 1-39 + Thunderball from 1-14. Tue/Wed/Fri/Sat since 1999."""
    path = DATA_DIR / "thunderball.csv"
    dates = draw_dates(date(2010, 5, 8), date(2025, 12, 31), {1, 2, 4, 5})
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["draw_date", "draw_number", "b1", "b2", "b3", "b4", "b5", "thunderball", "jackpot_pence"])
        for i, d in enumerate(reversed(dates), start=1):
            main = pick_balls(39, 5)
            tb = random.randint(1, 14)
            jackpot = 50_000_000  # £500K fixed
            writer.writerow([d.isoformat(), i, *main, tb, jackpot])
    print(f"Thunderbal: {len(dates):,} draws written → {path}")


if __name__ == "__main__":
    print("Generating seed data...")
    generate_lotto()
    generate_euromillions()
    generate_set_for_life()
    generate_thunderball()
    print("\nDone. Run: python main.py pick lotto --count 5")
