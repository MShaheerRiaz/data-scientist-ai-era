"""Generating ticket sets.

The generator's objective is **not** to find numbers more likely to be
drawn — no such numbers exist in a fair game.  It is to find combinations
that are unusually *unpopular* with other players, so that a win is shared
fewer ways, while keeping the selection statistically indistinguishable
from random.

That last constraint matters more than it looks.  A naive "avoid popular
numbers" rule sends everyone to the same corner of the space: high
numbers, no patterns, ugly-looking spreads.  If enough people did that,
those combinations would stop being unpopular.  Two defences are built in
here:

* every generated set is **salted** — pass a different ``salt`` and you get
  a different set of equally unpopular combinations, so two users of this
  library do not collide;
* the optimiser targets a low-popularity *region*, not the single minimum,
  keeping plenty of diversity among near-optimal picks.

A blunt reminder before you use any of this: it improves the payout you
receive *conditional on winning*.  It does not improve your chance of
winning, and it does not make a negative-EV game positive.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional, Sequence

from .combinatorics import comb, random_combination
from .config import BonusMode, LotteryConfig
from .popularity import PopularityModel

__all__ = [
    "TicketSet",
    "GeneratedTicket",
    "generate_random",
    "generate_unpopular",
    "generate_diverse",
    "coverage_overlap",
]


@dataclass
class GeneratedTicket:
    """One generated ticket with its popularity assessment."""

    main: tuple[int, ...]
    bonus: tuple[int, ...] = ()
    popularity: float = 1.0
    effective_popularity: float = 1.0

    def format(self) -> str:
        """Render as a playable line."""
        body = " ".join(f"{v:2d}" for v in self.main)
        if self.bonus:
            body += "  +  " + " ".join(f"{v:2d}" for v in self.bonus)
        return body


@dataclass
class TicketSet:
    """A generated set of tickets plus diagnostics."""

    config: LotteryConfig
    tickets: list[GeneratedTicket] = field(default_factory=list)
    strategy: str = "random"
    mean_popularity: float = 1.0
    mean_effective_popularity: float = 1.0
    max_pairwise_overlap: int = 0

    def cost(self) -> float:
        """Total price of the set."""
        return len(self.tickets) * self.config.ticket_price

    def payout_uplift(self) -> float:
        """Expected jackpot-share improvement versus average-popularity picks.

        A value of 1.15 means that *when* one of these tickets wins a shared
        prize, it should pay roughly 15% more than an average pick would,
        because fewer other players hold it.
        """
        if self.mean_effective_popularity <= 0:
            return 1.0
        return 1.0 / self.mean_effective_popularity

    def to_text(self) -> str:
        """Formatted output for the terminal."""
        cfg = self.config
        lines = ["=" * 78,
                 f"GENERATED TICKETS  -  {cfg.name}  ({self.strategy})",
                 "=" * 78]
        for i, ticket in enumerate(self.tickets, 1):
            lines.append(f"  {i:>3}.  {ticket.format()}"
                         f"    [popularity {ticket.effective_popularity:.3f}x]")
        lines.append("")
        lines.append(f"  tickets                        : {len(self.tickets)}")
        lines.append(f"  total cost                     : {self.cost():,.2f} {cfg.currency}")
        lines.append(f"  mean popularity (raw)          : {self.mean_popularity:.3f}x")
        lines.append(f"  mean popularity (after QP mix) : {self.mean_effective_popularity:.3f}x")
        lines.append(f"  max overlap between own tickets: {self.max_pairwise_overlap}")
        lines.append("")
        lines.append(f"  Expected payout uplift when a shared prize is won: "
                     f"{(self.payout_uplift() - 1) * 100:+.1f}%")
        lines.append("")
        lines.append("  This does NOT change your probability of winning, which depends only")
        lines.append("  on how many tickets you hold. It changes how many people you split")
        lines.append("  with. The game remains negative-EV.")
        lines.append("=" * 78)
        return "\n".join(lines)


def _bonus_for(cfg: LotteryConfig, rng: random.Random) -> tuple[int, ...]:
    """Random bonus numbers appropriate to the game's bonus mode."""
    if cfg.bonus_mode is BonusMode.SEPARATE_POOL:
        return tuple(sorted(rng.sample(range(1, cfg.bonus_pool + 1), cfg.bonus_pick)))
    return ()


def _finalise(
    cfg: LotteryConfig,
    model: PopularityModel,
    combos: Sequence[tuple[int, ...]],
    rng: random.Random,
    strategy: str,
) -> TicketSet:
    """Wrap raw combinations into a scored :class:`TicketSet`."""
    tickets = [
        GeneratedTicket(
            main=c,
            bonus=_bonus_for(cfg, rng),
            popularity=model.multiplier(c),
            effective_popularity=model.effective_multiplier(c),
        )
        for c in combos
    ]
    mean_raw = sum(t.popularity for t in tickets) / len(tickets) if tickets else 1.0
    mean_eff = sum(t.effective_popularity for t in tickets) / len(tickets) if tickets else 1.0
    return TicketSet(
        config=cfg,
        tickets=tickets,
        strategy=strategy,
        mean_popularity=mean_raw,
        mean_effective_popularity=mean_eff,
        max_pairwise_overlap=coverage_overlap([t.main for t in tickets]),
    )


def generate_random(
    config: LotteryConfig,
    count: int = 1,
    *,
    salt: int | str = 0,
) -> TicketSet:
    """Uniformly random tickets — the honest baseline.

    Worth stating plainly: this is exactly as likely to win as any other
    strategy in this module, and equivalent to a quick pick.
    """
    rng = random.Random(_seed_from(salt, "random"))
    model = PopularityModel(config)
    combos = [random_combination(config.main_pool, config.main_pick, rng) for _ in range(count)]
    return _finalise(config, model, combos, rng, "uniform random (quick-pick equivalent)")


def generate_unpopular(
    config: LotteryConfig,
    count: int = 1,
    *,
    salt: int | str = 0,
    candidates_per_ticket: int = 400,
    max_overlap: Optional[int] = None,
    model: Optional[PopularityModel] = None,
) -> TicketSet:
    """Generate tickets biased toward combinations other players avoid.

    Samples a pool of random candidates per ticket and keeps a low-popularity
    one, rather than searching for the global minimum.  Sampling keeps the
    output diverse and salt-dependent — important, because a deterministic
    "most unpopular combination" would be self-defeating the moment more
    than one person used it.

    ``max_overlap`` caps how many numbers any two of your own tickets may
    share, so a multi-ticket purchase spreads across the space instead of
    clustering.
    """
    rng = random.Random(_seed_from(salt, "unpopular"))
    model = model or PopularityModel(config)
    cap = max_overlap if max_overlap is not None else max(1, config.main_pick - 2)

    chosen: list[tuple[int, ...]] = []
    for _ in range(count):
        best: Optional[tuple[int, ...]] = None
        best_score = math.inf
        for _ in range(candidates_per_ticket):
            candidate = random_combination(config.main_pool, config.main_pick, rng)
            if chosen and max(len(set(candidate) & set(c)) for c in chosen) > cap:
                continue
            score = model.effective_multiplier(candidate)
            if score < best_score:
                best_score, best = score, candidate
        if best is None:
            best = random_combination(config.main_pool, config.main_pick, rng)
        chosen.append(best)

    return _finalise(config, model, chosen, rng, "unpopularity-optimised")


def generate_diverse(
    config: LotteryConfig,
    count: int,
    *,
    salt: int | str = 0,
    max_overlap: Optional[int] = None,
    iterations: int = 3000,
    unpopularity_weight: float = 1.0,
    model: Optional[PopularityModel] = None,
) -> TicketSet:
    """Optimise a whole ticket *set* jointly by simulated annealing.

    Balances two objectives: keep every ticket unpopular, and keep the
    tickets spread apart so they do not duplicate each other's coverage.
    Better than per-ticket selection when buying more than a handful of
    lines, because overlap between your own tickets is pure waste.
    """
    rng = random.Random(_seed_from(salt, "diverse"))
    model = model or PopularityModel(config)
    cap = max_overlap if max_overlap is not None else max(1, config.main_pick - 2)

    current = [random_combination(config.main_pool, config.main_pick, rng) for _ in range(count)]

    def energy(tickets: Sequence[tuple[int, ...]]) -> float:
        pop = sum(model.effective_multiplier(t) for t in tickets) / len(tickets)
        penalty = 0.0
        for i in range(len(tickets)):
            for j in range(i + 1, len(tickets)):
                excess = len(set(tickets[i]) & set(tickets[j])) - cap
                if excess > 0:
                    penalty += excess ** 2
        return unpopularity_weight * pop + penalty

    current_energy = energy(current)
    temperature = 1.0

    for step in range(iterations):
        temperature = max(1e-4, 1.0 * (1.0 - step / iterations))
        idx = rng.randrange(len(current))
        proposal = list(current)
        proposal[idx] = random_combination(config.main_pool, config.main_pick, rng)
        proposal_energy = energy(proposal)
        delta = proposal_energy - current_energy
        if delta < 0 or rng.random() < math.exp(-delta / temperature):
            current, current_energy = proposal, proposal_energy

    return _finalise(config, model, current, rng, "set-level annealing (unpopular + diverse)")


def coverage_overlap(tickets: Sequence[Sequence[int]]) -> int:
    """Largest number of shared numbers between any two tickets in a set."""
    worst = 0
    for i in range(len(tickets)):
        for j in range(i + 1, len(tickets)):
            worst = max(worst, len(set(tickets[i]) & set(tickets[j])))
    return worst


def _seed_from(salt: int | str, tag: str) -> int:
    """Derive a reproducible seed from a salt and a strategy tag."""
    if isinstance(salt, int):
        base = salt
    else:
        base = int.from_bytes(str(salt).encode("utf-8")[:8].ljust(8, b"\0"), "big")
    return (base * 1_000_003 + hash(tag) % 1_000_003) % (2 ** 63)
