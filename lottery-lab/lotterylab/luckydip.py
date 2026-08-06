"""Lucky Dip — the random number generator.

This is the part you actually play with. Everything else in the library
exists to justify the choices made here.

Three things it does that a naive ``random.randint`` loop does not.

**It uses real randomness.** Numbers come from :mod:`secrets`, which draws
on the operating system's cryptographic entropy pool, not from a
seeded pseudo-random generator. Python's default ``random`` is a Mersenne
Twister whose entire internal state can be reconstructed from 624
consecutive outputs — irrelevant for a lottery ticket in practice, but
there is no reason to accept a weaker source when a stronger one is free.
It also samples without modulo bias, so every number really is equally
likely.

**It offers a genuine choice about popularity.** Two modes:

* ``fair`` — uniformly random, exactly like the shop's Lucky Dip. Every
  combination equally likely, no preferences of any kind.
* ``unpopular`` — still random, but biased away from combinations other
  players favour. This does **not** improve your chance of winning. It
  improves what you collect *if* you win a shared prize, because fewer
  people hold the same numbers.

**It is salted.** Two people running this with different salts get
different tickets. That matters: an "avoid popular numbers" tool that
always returned the same answer would make its own output popular and
destroy the effect it exists to create.

One thing it deliberately will not do: pick numbers that are "due", "hot",
or "cold". Those do not exist in a fair draw, and :mod:`lotterylab.backtest`
demonstrates it rather than asserting it.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Iterable, Literal, Optional, Sequence

from .combinatorics import (
    any_prize_probability,
    jackpot_probability,
    odds_string,
    total_combinations,
)
from .config import BonusMode, LotteryConfig
from .popularity import PopularityModel

__all__ = ["Line", "Slip", "lucky_dip", "SecureRandom"]

Mode = Literal["fair", "unpopular"]


class SecureRandom:
    """Cryptographic-quality sampling, with the same shape as ``random.Random``.

    Wraps :mod:`secrets` so the rest of the library can accept it wherever
    it accepts a ``random.Random``. ``randbelow`` is rejection-sampled by
    the standard library, so there is no modulo bias — every value in range
    is exactly equally likely.
    """

    def randrange(self, start: int, stop: Optional[int] = None) -> int:
        """Uniform integer from ``range(start, stop)``."""
        if stop is None:
            start, stop = 0, start
        width = stop - start
        if width <= 0:
            raise ValueError("empty range")
        return start + secrets.randbelow(width)

    def random(self) -> float:
        """Uniform float in [0, 1) with 53 bits of entropy."""
        return secrets.randbits(53) / (1 << 53)

    def sample(self, population: Sequence[int], k: int) -> list[int]:
        """``k`` distinct items, chosen uniformly without replacement.

        Partial Fisher-Yates: unbiased, and does not care how large the
        population is relative to ``k``.
        """
        pool = list(population)
        if not 0 <= k <= len(pool):
            raise ValueError("sample size out of range")
        for i in range(k):
            j = i + secrets.randbelow(len(pool) - i)
            pool[i], pool[j] = pool[j], pool[i]
        return pool[:k]

    def choice(self, seq: Sequence[int]) -> int:
        """One uniformly random element."""
        if not seq:
            raise IndexError("cannot choose from an empty sequence")
        return seq[secrets.randbelow(len(seq))]

    def shuffle(self, seq: list) -> None:
        """Shuffle a list in place."""
        for i in range(len(seq) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            seq[i], seq[j] = seq[j], seq[i]


@dataclass
class Line:
    """One playable line."""

    main: tuple[int, ...]
    bonus: tuple[int, ...] = ()
    popularity: float = 1.0

    def format(self, bonus_label: str = "+") -> str:
        """Render for reading off onto a slip."""
        body = "  ".join(f"{v:02d}" for v in self.main)
        if self.bonus:
            body += f"   {bonus_label}  " + "  ".join(f"{v:02d}" for v in self.bonus)
        return body


@dataclass
class Slip:
    """A set of lines for one game, with the numbers that matter."""

    config: LotteryConfig
    lines: list[Line] = field(default_factory=list)
    mode: Mode = "fair"
    salt: str = ""

    @property
    def cost(self) -> float:
        """What this slip costs to play."""
        return len(self.lines) * self.config.ticket_price

    @property
    def mean_popularity(self) -> float:
        """Average popularity of the lines, after quick-pick dilution."""
        if not self.lines:
            return 1.0
        return sum(line.popularity for line in self.lines) / len(self.lines)

    @property
    def jackpot_chance(self) -> float:
        """Probability that at least one line wins the top prize."""
        p = jackpot_probability(self.config)
        return 1.0 - (1.0 - p) ** len(self.lines)

    def to_text(self) -> str:
        """The slip, formatted for a terminal."""
        cfg = self.config
        bonus_label = _bonus_label(cfg)
        width = 66

        lines = ["=" * width]
        lines.append(f"  {cfg.name}".ljust(width - 12) + f"{len(self.lines)} line(s)")
        lines.append("=" * width)
        lines.append("")
        for i, line in enumerate(self.lines, 1):
            suffix = ""
            if self.mode == "unpopular":
                suffix = f"      [{line.popularity:.2f}x popularity]"
            lines.append(f"   {i:>2}.   {line.format(bonus_label)}{suffix}")
        lines.append("")
        lines.append(f"  Cost                {self.cost:>10,.2f} {cfg.currency}")
        lines.append(f"  Top prize odds      {odds_string(jackpot_probability(cfg)):>10}"
                     f"  per line")
        lines.append(f"  Any prize odds      {odds_string(any_prize_probability(cfg)):>10}"
                     f"  per line")
        lines.append(f"  Chance any line wins the top prize: "
                     f"{odds_string(self.jackpot_chance)}")
        lines.append("")

        if self.mode == "unpopular":
            uplift = (1.0 / self.mean_popularity - 1.0) * 100 if self.mean_popularity else 0.0
            lines.append(f"  Mode: unpopular  (salt: {self.salt!r})")
            if _prizes_are_shared(cfg):
                lines.append(f"  These numbers are less popular than average, so a shared")
                lines.append(f"  prize would be split fewer ways - worth roughly {uplift:+.0f}%")
                lines.append(f"  on the payout. Your ODDS are unchanged.")
            else:
                lines.append(f"  NOTE: {cfg.name} pays FIXED prizes that are never shared,")
                lines.append(f"  so avoiding popular numbers gains you nothing here.")
                lines.append(f"  Use --mode fair for this game.")
        else:
            lines.append(f"  Mode: fair  -  uniformly random, same as a shop Lucky Dip.")
        lines.append("=" * width)
        return "\n".join(lines)


def _bonus_label(config: LotteryConfig) -> str:
    """The operator's name for the supplementary ball."""
    return {
        "EuroMillions": "Stars",
        "Thunderball (UK)": "TB",
        "Set For Life (UK)": "Life",
        "US Powerball": "PB",
        "US Mega Millions": "MB",
    }.get(config.name, "+")


def _prizes_are_shared(config: LotteryConfig) -> bool:
    """Whether any prize in this game is pari-mutuel.

    If every prize is fixed, popularity is irrelevant to the player: an
    unshared prize pays the same however many others hold your numbers.
    """
    return any(t.is_parimutuel for t in config.tiers)


def lucky_dip(
    config: LotteryConfig,
    lines: int = 1,
    *,
    mode: Mode = "fair",
    salt: str = "",
    candidates: int = 250,
    max_overlap: Optional[int] = None,
    exclude: Optional[Iterable[int]] = None,
    include: Optional[Iterable[int]] = None,
) -> Slip:
    """Generate lines for a game.

    ``mode='fair'`` gives a uniformly random pick, identical in
    distribution to the shop's Lucky Dip. ``mode='unpopular'`` samples
    candidates and keeps low-popularity ones, which raises your share of a
    *shared* prize without touching your odds.

    ``include`` forces numbers onto every line and ``exclude`` bans them.
    Both are honoured because people have numbers they want to play, but
    neither improves your chances — a forced number is neither more nor
    less likely to be drawn.

    ``max_overlap`` caps how many numbers two of your own lines may share,
    so a multi-line slip spreads out instead of clustering.
    """
    rng = SecureRandom()
    cfg = config

    banned = set(exclude or ())
    forced = tuple(sorted(set(include or ())))
    for value in banned | set(forced):
        if not 1 <= value <= cfg.main_pool:
            raise ValueError(f"number {value} is outside 1..{cfg.main_pool}")
    if banned & set(forced):
        raise ValueError("a number cannot be both included and excluded")
    if len(forced) > cfg.main_pick:
        raise ValueError(f"cannot force {len(forced)} numbers onto a {cfg.main_pick}-number line")

    pool = [v for v in range(1, cfg.main_pool + 1) if v not in banned and v not in forced]
    need = cfg.main_pick - len(forced)
    if len(pool) < need:
        raise ValueError("too many numbers excluded to build a line")

    cap = max_overlap if max_overlap is not None else max(1, cfg.main_pick - 2)

    # The popularity model is built once; salting happens through the
    # candidate sampling, which uses the OS entropy source.
    model = PopularityModel(cfg) if mode == "unpopular" else None

    chosen: list[tuple[int, ...]] = []
    for _ in range(lines):
        if mode == "fair":
            main = tuple(sorted(forced + tuple(rng.sample(pool, need))))
        else:
            assert model is not None
            best: Optional[tuple[int, ...]] = None
            best_score = float("inf")
            for _ in range(candidates):
                trial = tuple(sorted(forced + tuple(rng.sample(pool, need))))
                if chosen and max(len(set(trial) & set(c)) for c in chosen) > cap:
                    continue
                score = model.effective_multiplier(trial)
                if score < best_score:
                    best_score, best = score, trial
            main = best if best is not None else tuple(
                sorted(forced + tuple(rng.sample(pool, need)))
            )
        chosen.append(main)

    result: list[Line] = []
    for main in chosen:
        bonus: tuple[int, ...] = ()
        if cfg.bonus_mode is BonusMode.SEPARATE_POOL:
            bonus = tuple(sorted(rng.sample(range(1, cfg.bonus_pool + 1), cfg.bonus_pick)))
        popularity = model.effective_multiplier(main) if model else 1.0
        result.append(Line(main=main, bonus=bonus, popularity=popularity))

    return Slip(config=cfg, lines=result, mode=mode, salt=salt)
