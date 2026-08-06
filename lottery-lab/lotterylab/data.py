"""Loading, validating and synthesising draw histories.

The CSV reader is deliberately forgiving, because real lottery history
files come in every shape imaginable: one column per ball, one
comma-separated column, dates in six different formats, stray bonus
columns.  Anything it cannot parse is reported rather than silently
dropped — silently dropping draws is how you end up "discovering" a bias
that is really just a broken import.
"""

from __future__ import annotations

import csv
import random
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Iterator, Optional, Sequence

from .config import BonusMode, LotteryConfig

__all__ = ["Draw", "DrawHistory", "load_csv", "save_csv", "synthesize", "SynthBias"]


_DATE_FORMATS = (
    "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d",
    "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y", "%Y%m%d",
)


def _parse_date(raw: str) -> Optional[date]:
    """Best-effort date parsing across the formats real files actually use."""
    text = raw.strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


@dataclass(frozen=True)
class Draw:
    """A single draw result."""

    main: tuple[int, ...]
    bonus: tuple[int, ...] = ()
    draw_date: Optional[date] = None
    index: int = 0

    def __post_init__(self) -> None:
        if len(set(self.main)) != len(self.main):
            raise ValueError(f"draw has repeated main numbers: {self.main}")

    @property
    def total(self) -> int:
        """Sum of the main numbers."""
        return sum(self.main)

    @property
    def odd_count(self) -> int:
        """How many main numbers are odd."""
        return sum(1 for v in self.main if v % 2)

    @property
    def spread(self) -> int:
        """Range from lowest to highest main number."""
        return max(self.main) - min(self.main)

    def sorted_main(self) -> tuple[int, ...]:
        """Main numbers in ascending order."""
        return tuple(sorted(self.main))


@dataclass
class DrawHistory:
    """An ordered collection of draws for one game."""

    config: LotteryConfig
    draws: list[Draw] = field(default_factory=list)
    source: str = "<memory>"
    warnings: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.draws)

    def __iter__(self) -> Iterator[Draw]:
        return iter(self.draws)

    def __getitem__(self, item):  # type: ignore[no-untyped-def]
        return self.draws[item]

    @property
    def n_draws(self) -> int:
        """Number of draws in the history."""
        return len(self.draws)

    def main_counts(self) -> list[int]:
        """Appearance count for every ball, indexed ``1..main_pool``.

        Element 0 is unused so that ``counts[ball]`` reads naturally.
        """
        counts = [0] * (self.config.main_pool + 1)
        for draw in self.draws:
            for value in draw.main:
                if 1 <= value <= self.config.main_pool:
                    counts[value] += 1
        return counts

    def bonus_counts(self) -> list[int]:
        """Appearance count for every bonus ball."""
        pool = self.config.bonus_pool or self.config.main_pool
        counts = [0] * (pool + 1)
        for draw in self.draws:
            for value in draw.bonus:
                if 1 <= value <= pool:
                    counts[value] += 1
        return counts

    def validate(self) -> list[str]:
        """Check every draw against the game's declared structure."""
        problems: list[str] = []
        cfg = self.config
        for i, draw in enumerate(self.draws):
            where = f"draw {i}" + (f" ({draw.draw_date})" if draw.draw_date else "")
            if len(draw.main) != cfg.main_pick:
                problems.append(f"{where}: expected {cfg.main_pick} main numbers, got {len(draw.main)}")
            for value in draw.main:
                if not 1 <= value <= cfg.main_pool:
                    problems.append(f"{where}: main number {value} outside 1..{cfg.main_pool}")
            if cfg.bonus_mode is BonusMode.SEPARATE_POOL:
                if len(draw.bonus) != cfg.bonus_pick:
                    problems.append(f"{where}: expected {cfg.bonus_pick} bonus, got {len(draw.bonus)}")
                for value in draw.bonus:
                    if not 1 <= value <= cfg.bonus_pool:
                        problems.append(f"{where}: bonus {value} outside 1..{cfg.bonus_pool}")
            elif cfg.bonus_mode is BonusMode.FROM_REMAINING:
                for value in draw.bonus:
                    if value in draw.main:
                        problems.append(f"{where}: bonus {value} duplicates a main number")
        return problems

    def duplicates(self) -> list[tuple[int, int, tuple[int, ...]]]:
        """Find repeated main-number combinations.

        Genuine repeats do happen (famously, Bulgaria's 6/49 repeated a
        combination four days apart in 2009, which triggered an
        investigation that found nothing wrong).  Repeats are only
        suspicious if there are *more* than chance predicts.
        """
        seen: dict[tuple[int, ...], int] = {}
        out: list[tuple[int, int, tuple[int, ...]]] = []
        for i, draw in enumerate(self.draws):
            key = draw.sorted_main()
            if key in seen:
                out.append((seen[key], i, key))
            else:
                seen[key] = i
        return out


# ---------------------------------------------------------------------------
# CSV I/O
# ---------------------------------------------------------------------------

_NUM_RE = re.compile(r"\d+")


def load_csv(
    path: str | Path,
    config: LotteryConfig,
    *,
    date_column: Optional[str] = None,
    main_columns: Optional[Sequence[str]] = None,
    bonus_columns: Optional[Sequence[str]] = None,
    strict: bool = False,
) -> DrawHistory:
    """Read a draw history from CSV, guessing the layout when not told.

    Recognises both "one column per ball" layouts and single columns
    holding all the numbers together.  Rows that cannot be parsed are
    collected into ``history.warnings`` unless ``strict`` is set, in which
    case the first bad row raises.
    """
    path = Path(path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        return DrawHistory(config=config, draws=[], source=str(path),
                           warnings=["file contained no data rows"])

    headers = list(rows[0].keys())
    lowered = {h.lower().strip(): h for h in headers if h}

    # --- work out which columns hold what -------------------------------
    if date_column is None:
        for candidate in ("date", "draw_date", "drawdate", "draw date", "when"):
            if candidate in lowered:
                date_column = lowered[candidate]
                break

    if main_columns is None:
        guessed = [lowered[k] for k in sorted(lowered)
                   if re.fullmatch(r"(n|ball|num|number|winning_number)_?\d+", k)]
        if len(guessed) >= config.main_pick:
            main_columns = guessed[: config.main_pick]
        else:
            for candidate in ("numbers", "winning_numbers", "main", "balls", "result"):
                if candidate in lowered:
                    main_columns = [lowered[candidate]]
                    break

    if bonus_columns is None and config.has_bonus:
        guessed_b = [lowered[k] for k in sorted(lowered)
                     if re.fullmatch(r"(bonus|powerball|mega_?ball|star|lucky_?star|pb|extra)_?\d*", k)]
        if guessed_b:
            bonus_columns = guessed_b[: max(1, config.bonus_pick)]

    warnings: list[str] = []
    draws: list[Draw] = []

    def extract(row: dict[str, str], columns: Optional[Sequence[str]], want: int) -> list[int]:
        if not columns:
            return []
        values: list[int] = []
        for column in columns:
            cell = (row.get(column) or "").strip()
            values.extend(int(m) for m in _NUM_RE.findall(cell))
        return values[:want] if want and len(values) > want else values

    for line_no, row in enumerate(rows, start=2):
        try:
            main = extract(row, main_columns, config.main_pick)
            if len(main) != config.main_pick:
                raise ValueError(
                    f"found {len(main)} main numbers, expected {config.main_pick}"
                )
            want_bonus = config.bonus_pick if config.has_bonus else 0
            bonus = extract(row, bonus_columns, want_bonus)
            when = _parse_date(row.get(date_column, "")) if date_column else None
            draws.append(Draw(main=tuple(main), bonus=tuple(bonus),
                              draw_date=when, index=len(draws)))
        except (ValueError, TypeError) as exc:
            message = f"line {line_no}: {exc}"
            if strict:
                raise ValueError(f"{path}: {message}") from exc
            warnings.append(message)

    # Oldest-first ordering, so "gaps" and serial tests read chronologically.
    if all(d.draw_date for d in draws) and len(draws) > 1:
        draws.sort(key=lambda d: d.draw_date)  # type: ignore[arg-type,return-value]
        draws = [Draw(d.main, d.bonus, d.draw_date, i) for i, d in enumerate(draws)]

    history = DrawHistory(config=config, draws=draws, source=str(path), warnings=warnings)
    problems = history.validate()
    if problems:
        history.warnings.extend(problems[:50])
        if len(problems) > 50:
            history.warnings.append(f"...and {len(problems) - 50} further validation problems")
    return history


def save_csv(history: DrawHistory, path: str | Path) -> None:
    """Write a history back out in the canonical one-column-per-ball layout."""
    path = Path(path)
    cfg = history.config
    header = ["date"] + [f"n{i + 1}" for i in range(cfg.main_pick)]
    if cfg.has_bonus:
        header += [f"bonus{i + 1}" for i in range(max(1, cfg.bonus_pick))]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for draw in history.draws:
            row = [draw.draw_date.isoformat() if draw.draw_date else ""]
            row += list(draw.sorted_main())
            if cfg.has_bonus:
                row += list(draw.bonus) + [""] * (max(1, cfg.bonus_pick) - len(draw.bonus))
            writer.writerow(row)


# ---------------------------------------------------------------------------
# Synthetic histories
# ---------------------------------------------------------------------------


@dataclass
class SynthBias:
    """A deliberate flaw to inject into a synthetic history.

    Used to measure what the audit battery can actually detect.  A test
    you have never seen fire on known-bad data is not evidence of
    anything.
    """

    # Multiplicative weight per ball; ball b gets weight ``weights.get(b, 1.0)``.
    weights: dict[int, float] = field(default_factory=dict)
    # Probability that a draw simply repeats the previous draw's first number,
    # a crude stand-in for serial dependence.
    sticky: float = 0.0


def synthesize(
    config: LotteryConfig,
    n_draws: int,
    *,
    seed: Optional[int] = None,
    bias: Optional[SynthBias] = None,
    start: Optional[date] = None,
) -> DrawHistory:
    """Generate a synthetic draw history, fair by default.

    With ``bias`` supplied the generator produces a *known-bad* history,
    which is how the power of each test in the audit battery is measured.
    """
    rng = random.Random(seed)
    cfg = config
    draws: list[Draw] = []
    previous: tuple[int, ...] = ()

    weights = (bias.weights if bias else {}) or {}
    pool = list(range(1, cfg.main_pool + 1))

    for i in range(n_draws):
        if weights:
            main = _weighted_sample(pool, weights, cfg.main_pick, rng)
        else:
            main = rng.sample(pool, cfg.main_pick)

        if bias and bias.sticky > 0 and previous and rng.random() < bias.sticky:
            keep = previous[0]
            if keep not in main:
                main[rng.randrange(len(main))] = keep
                main = list(dict.fromkeys(main))
                while len(main) < cfg.main_pick:
                    candidate = rng.choice(pool)
                    if candidate not in main:
                        main.append(candidate)

        main_sorted = tuple(sorted(main))

        if cfg.bonus_mode is BonusMode.SEPARATE_POOL:
            bonus = tuple(sorted(rng.sample(range(1, cfg.bonus_pool + 1), cfg.bonus_pick)))
        elif cfg.bonus_mode is BonusMode.FROM_REMAINING:
            remaining = [v for v in pool if v not in main_sorted]
            bonus = (rng.choice(remaining),)
        else:
            bonus = ()

        when = None
        if start is not None:
            from datetime import timedelta
            when = start + timedelta(days=3 * i)

        draws.append(Draw(main=main_sorted, bonus=bonus, draw_date=when, index=i))
        previous = main_sorted

    label = "synthetic (fair)" if not weights and not (bias and bias.sticky) else "synthetic (biased)"
    return DrawHistory(config=cfg, draws=draws, source=label)


def _weighted_sample(
    pool: Sequence[int],
    weights: dict[int, float],
    k: int,
    rng: random.Random,
) -> list[int]:
    """Draw ``k`` distinct values with per-value weights, without replacement."""
    available = list(pool)
    current = [weights.get(v, 1.0) for v in available]
    chosen: list[int] = []
    for _ in range(k):
        total = sum(current)
        target = rng.random() * total
        acc = 0.0
        for idx, weight in enumerate(current):
            acc += weight
            if acc >= target:
                chosen.append(available[idx])
                available.pop(idx)
                current.pop(idx)
                break
        else:  # pragma: no cover - only on pathological float error
            chosen.append(available.pop())
            current.pop()
    return chosen
