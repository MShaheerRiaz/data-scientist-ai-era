"""Command-line interface.

Run ``python -m lotterylab --help`` for the full list of commands.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import Optional, Sequence

from . import __version__
from .combinatorics import (
    all_tier_probabilities,
    any_prize_probability,
    jackpot_probability,
    odds_string,
    total_combinations,
)
from .config import DIGIT_PRESETS, PRESETS, get_preset, list_presets
from .data import load_csv, save_csv, synthesize


def _load_history(args: argparse.Namespace):
    """Load a draw history from CSV, or synthesise one for demonstration."""
    config = get_preset(args.game)
    if getattr(args, "csv", None):
        history = load_csv(args.csv, config)
        if history.warnings:
            print(f"  note: {len(history.warnings)} warning(s) while loading:", file=sys.stderr)
            for w in history.warnings[:10]:
                print(f"    - {w}", file=sys.stderr)
        if not history.draws:
            raise SystemExit("no usable draws were loaded - check the CSV layout")
        return history
    n = getattr(args, "synth", None) or 2000
    print(f"  [no --csv given, using {n} synthetic fair draws for demonstration]\n")
    return synthesize(config, n, seed=getattr(args, "seed", 0))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_games(args: argparse.Namespace) -> int:
    """List the built-in game presets and their odds."""
    print("DRAW GAMES")
    print(f"  {'key':<16}{'game':<26}{'combinations':>16}{'jackpot odds':>24}")
    for key in list_presets():
        cfg = PRESETS[key]
        print(f"  {key:<16}{cfg.name:<26}{total_combinations(cfg):>16,}"
              f"{odds_string(jackpot_probability(cfg)):>24}")
    print("\nDIGIT GAMES")
    print(f"  {'key':<16}{'game':<34}{'edge':>8}")
    for key, cfg in sorted(DIGIT_PRESETS.items()):
        print(f"  {key:<16}{cfg.name:<34}{cfg.house_edge:>8.1%}")
    return 0


def cmd_odds(args: argparse.Namespace) -> int:
    """Print the exact prize-tier odds for a game."""
    cfg = get_preset(args.game)
    print("=" * 78)
    print(f"ODDS  -  {cfg.describe()}")
    print("=" * 78)
    print(f"  total distinct tickets: {total_combinations(cfg):,}")
    print()
    print(f"  {'tier':<20}{'probability':>16}{'odds':>24}{'payout':>14}")
    for tier, p in all_tier_probabilities(cfg):
        payout = "jackpot" if tier.is_jackpot else f"{tier.payout:,.0f}"
        print(f"  {tier.name:<20}{p:>16.6e}{odds_string(p):>24}{payout:>14}")
    print()
    print(f"  any prize: {odds_string(any_prize_probability(cfg))}")
    if cfg.notes:
        print(f"\n  {cfg.notes}")
    print("=" * 78)
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    """Run the fairness audit battery on a draw history."""
    from .fairness import audit

    history = _load_history(args)
    report = audit(history, include_pair_test=not args.fast,
                   pair_reps=args.pair_reps)
    print(report.to_text(top_balls=args.top))
    return 0


def cmd_power(args: argparse.Namespace) -> int:
    """Show what size of bias a given amount of history could detect."""
    from .fairness import power_analysis

    cfg = get_preset(args.game)
    result = power_analysis(cfg, args.draws)
    print("=" * 78)
    print(f"POWER ANALYSIS  -  {cfg.name}")
    print("=" * 78)
    print(f"  history available          : {args.draws:,} draws")
    print(f"  per-ball probability        : {result['p_null']:.6f}")
    print(f"  smallest detectable bias    : "
          f"{(float(result['min_detectable_lift']) - 1) * 100:.1f}% lift")
    print()
    print("  Draws required to detect a given bias at 80% power:")
    for lift, needed in sorted(result["draws_required"].items()):  # type: ignore[union-attr]
        print(f"    {(lift - 1) * 100:>5.0f}% hot ball -> {needed:>13,.0f} draws "
              f"({needed / 104:>10,.0f} years at 2 draws/week)")
    print()
    print(f"  {result['note']}")
    print("=" * 78)
    return 0


def cmd_ev(args: argparse.Namespace) -> int:
    """Compute expected value for a ticket, including jackpot sharing."""
    from .ev import EVAssumptions, break_even_jackpot, ticket_ev

    cfg = get_preset(args.game)
    assumptions = EVAssumptions(
        jackpot=args.jackpot,
        tickets_sold=args.sales,
        cash_value_ratio=args.cash_ratio,
        tax_rate=args.tax,
        popularity_multiplier=args.popularity,
        sales_base=args.sales_base if args.sales_growth else 0.0,
        sales_per_jackpot_unit=args.sales_growth,
    )
    print(ticket_ev(cfg, assumptions).to_text())
    be = break_even_jackpot(cfg, assumptions)
    if be is None:
        print("\n  Break-even jackpot: UNREACHABLE at any size.")
        print("  Because sales grow with the jackpot, the number of people you would")
        print("  split with grows just as fast as the prize. Expected value converges")
        print("  to a ceiling below the ticket price.")
    else:
        print(f"\n  Break-even jackpot: {be:,.0f} {cfg.currency}")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    """Generate tickets, optionally optimised against player popularity."""
    from .generate import generate_diverse, generate_random, generate_unpopular

    cfg = get_preset(args.game)
    if args.strategy == "random":
        result = generate_random(cfg, args.count, salt=args.salt)
    elif args.strategy == "unpopular":
        result = generate_unpopular(cfg, args.count, salt=args.salt)
    else:
        result = generate_diverse(cfg, args.count, salt=args.salt)
    print(result.to_text())
    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    """Explain how popular a specific combination is with other players."""
    from .popularity import PopularityModel

    cfg = get_preset(args.game)
    numbers = tuple(sorted(args.numbers))
    if len(numbers) != cfg.main_pick:
        raise SystemExit(f"{cfg.name} needs exactly {cfg.main_pick} numbers, got {len(numbers)}")
    for value in numbers:
        if not 1 <= value <= cfg.main_pool:
            raise SystemExit(f"number {value} is outside 1..{cfg.main_pool}")
    print(PopularityModel(cfg).explain(numbers))
    return 0


def cmd_wheel(args: argparse.Namespace) -> int:
    """Build a covering-design wheel with a verified guarantee."""
    from .wheels import covering_design, full_wheel, guarantee_report, schonheim_bound

    cfg = get_preset(args.game)
    numbers = list(args.numbers) if args.numbers else list(range(1, args.pool + 1))
    if args.full:
        wheel = full_wheel(numbers, cfg.main_pick)
    else:
        wheel = covering_design(numbers, cfg.main_pick, args.coverage, seed=args.seed)

    print("=" * 78)
    print(f"WHEEL  -  {cfg.name}")
    print("=" * 78)
    print(f"  {wheel.describe()}")
    print(f"  cost: {wheel.cost(cfg.ticket_price):,.2f} {cfg.currency}")
    if not args.full:
        lb = schonheim_bound(len(numbers), cfg.main_pick, args.coverage)
        print(f"  Schoenheim lower bound: {lb} tickets "
              f"(this wheel is {wheel.size / lb:.2f}x the theoretical minimum)")
    print()
    if args.show:
        for i, block in enumerate(wheel.blocks, 1):
            print(f"  {i:>4}.  " + " ".join(f"{v:2d}" for v in block))
        print()
    print("  GUARANTEE TABLE")
    for hits, best in sorted(guarantee_report(wheel, cfg.main_pick).items()):
        print(f"    {hits} of your numbers drawn -> at least {best} match(es)")
    print()
    print("  A wheel does not improve your jackpot odds, which scale with ticket")
    print("  count alone. It converts a random scatter of small prizes into a")
    print("  guaranteed floor - it trades variance for certainty, at a price.")
    print("=" * 78)
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    """Compare number-picking strategies against a properly calibrated null."""
    from .backtest import STRATEGIES, compare_strategies, permutation_test

    history = _load_history(args)
    print(compare_strategies(history, tickets_per_draw=args.tickets,
                             warmup=args.warmup, repeats=args.repeats))
    if args.permutation:
        print("\nPERMUTATION TEST (scrambled chronology null)")
        print(f"  {'strategy':<12}{'observed':>11}{'null mean':>11}{'z':>8}{'p':>8}")
        for name in ("hot", "cold", "due", "random"):
            result = permutation_test(history, STRATEGIES[name], name=name,
                                      reps=args.reps, tickets_per_draw=args.tickets,
                                      warmup=args.warmup)
            print(f"  {name:<12}{result['observed_mean_matches']:>11.5f}"
                  f"{result['null_mean']:>11.5f}{result['z']:>8.2f}{result['pvalue']:>8.3f}")
        print("\n  A strategy that used real time-structure would degrade when the")
        print("  chronology is scrambled. None of them do.")
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    """Simulate many players over many draws."""
    from .simulate import jackpot_waiting_time, simulate_play, time_to_ruin

    cfg = get_preset(args.game)
    result = simulate_play(cfg, n_players=args.players, n_draws=args.draws,
                           tickets_per_draw=args.tickets,
                           starting_bankroll=args.bankroll,
                           jackpot=args.jackpot, seed=args.seed)
    print(result.to_text())

    wait = jackpot_waiting_time(cfg, tickets_per_draw=args.tickets)
    print()
    print(f"  Expected wait for a jackpot at {args.tickets} ticket(s) per draw: "
          f"{wait['expected_years']:,.0f} years")
    print(f"  Chance of a jackpot across 50 years of play: {wait['odds_string_50y']}")
    ruin = time_to_ruin(cfg, bankroll=args.bankroll, tickets_per_draw=args.tickets,
                        jackpot=args.jackpot)
    if ruin.get("expected_draws") != float("inf"):
        print(f"  Expected bankroll lifetime: {ruin['expected_draws']:,.0f} draws "
              f"({ruin['years_twice_weekly']:,.1f} years at 2 draws/week)")
    return 0


def cmd_digits(args: argparse.Namespace) -> int:
    """Audit a digit game (2D, 3D, Pick 3/4, 4D)."""
    from .digits import DigitHistory, digit_audit, house_edge_table

    if args.compare:
        print("DIGIT GAME ECONOMICS")
        print(house_edge_table(list(DIGIT_PRESETS.values())))
        return 0

    cfg = DIGIT_PRESETS.get(args.game)
    if cfg is None:
        raise SystemExit(f"unknown digit game {args.game!r}; "
                         f"available: {', '.join(sorted(DIGIT_PRESETS))}")

    if args.values:
        values = [line.strip() for line in Path(args.values).read_text().split() if line.strip()]
        history = DigitHistory.from_values(cfg, values, source=args.values)
    else:
        n = args.synth or 3000
        print(f"  [no --values given, simulating {n} fair draws for demonstration]\n")
        rng = random.Random(args.seed)
        history = DigitHistory.from_values(
            cfg, [rng.randrange(cfg.outcomes) for _ in range(n)], source="synthetic"
        )
    print(digit_audit(history).to_text())
    return 0


def cmd_twod(args: argparse.Namespace) -> int:
    """Derive a Myanmar 2D number from Thai SET figures."""
    from .digits import derive_myanmar_2d

    value = derive_myanmar_2d(args.set_index, args.trading_value)
    top = int(args.set_index * 100) % 10
    bottom = int(args.trading_value) % 10
    print("=" * 78)
    print("MYANMAR 2D DERIVATION")
    print("=" * 78)
    print(f"  SET index          : {args.set_index:,.2f}   -> hundredths digit = {top}")
    print(f"  trading value (M฿) : {args.trading_value:,.2f}   -> units digit    = {bottom}")
    print(f"\n  2D result          : {value:02d}")
    print()
    print(f"  The widely repeated 'last two digits of the index' rule would give "
          f"{int(args.set_index) % 100:02d},")
    print("  which is wrong. Verified against 12 historical records from two")
    print("  independent sources.")
    print("=" * 78)
    return 0


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Construct the full argument parser."""
    parser = argparse.ArgumentParser(
        prog="lotterylab",
        description="Probability, game theory and fairness auditing for lotteries.",
        epilog="For a fair lottery, past draws contain no information about future "
               "draws. This toolkit is built around that fact, not against it.",
    )
    parser.add_argument("--version", action="version", version=f"lotterylab {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("games", help="list built-in games")
    p.set_defaults(func=cmd_games)

    p = sub.add_parser("odds", help="exact prize-tier odds")
    p.add_argument("game", nargs="?", default="canada_649")
    p.set_defaults(func=cmd_odds)

    p = sub.add_parser("audit", help="fairness audit of a draw history")
    p.add_argument("game", nargs="?", default="canada_649")
    p.add_argument("--csv", help="draw history CSV")
    p.add_argument("--synth", type=int, help="synthesise N fair draws instead")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--top", type=int, default=10, help="how many extreme balls to show")
    p.add_argument("--fast", action="store_true", help="skip the Monte Carlo pair test")
    p.add_argument("--pair-reps", type=int, default=500)
    p.set_defaults(func=cmd_audit)

    p = sub.add_parser("power", help="what size of bias could your data detect?")
    p.add_argument("game", nargs="?", default="canada_649")
    p.add_argument("--draws", type=int, default=3000)
    p.set_defaults(func=cmd_power)

    p = sub.add_parser("ev", help="expected value including jackpot sharing")
    p.add_argument("game", nargs="?", default="powerball")
    p.add_argument("--jackpot", type=float, default=100_000_000.0)
    p.add_argument("--sales", type=int, default=0, help="fixed ticket sales")
    p.add_argument("--sales-growth", type=float, default=None,
                   help="tickets sold per unit of jackpot (e.g. 0.39 for Powerball)")
    p.add_argument("--sales-base", type=float, default=20e6,
                   help="baseline sales when using --sales-growth")
    p.add_argument("--cash-ratio", type=float, default=1.0,
                   help="lump sum as a fraction of the advertised annuity")
    p.add_argument("--tax", type=float, default=0.0)
    p.add_argument("--popularity", type=float, default=1.0,
                   help="how over-picked your combination is")
    p.set_defaults(func=cmd_ev)

    p = sub.add_parser("generate", help="generate tickets")
    p.add_argument("game", nargs="?", default="canada_649")
    p.add_argument("-n", "--count", type=int, default=5)
    p.add_argument("--strategy", choices=["random", "unpopular", "diverse"], default="unpopular")
    p.add_argument("--salt", default="0",
                   help="change this to get a different, equally unpopular set")
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("explain", help="how popular is a specific combination?")
    p.add_argument("game")
    p.add_argument("numbers", type=int, nargs="+")
    p.set_defaults(func=cmd_explain)

    p = sub.add_parser("wheel", help="build a wheel with a verified guarantee")
    p.add_argument("game", nargs="?", default="canada_649")
    p.add_argument("--numbers", type=int, nargs="+", help="your chosen pool")
    p.add_argument("--pool", type=int, default=12, help="use 1..POOL if --numbers is omitted")
    p.add_argument("--coverage", type=int, default=4, help="guarantee level t")
    p.add_argument("--full", action="store_true", help="build the full wheel instead")
    p.add_argument("--show", action="store_true", help="print every ticket")
    p.add_argument("--seed", type=int, default=0)
    p.set_defaults(func=cmd_wheel)

    p = sub.add_parser("backtest", help="compare strategies against a null")
    p.add_argument("game", nargs="?", default="canada_649")
    p.add_argument("--csv")
    p.add_argument("--synth", type=int, default=2000)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--tickets", type=int, default=5)
    p.add_argument("--warmup", type=int, default=100)
    p.add_argument("--repeats", type=int, default=10)
    p.add_argument("--permutation", action="store_true", help="also run the permutation test")
    p.add_argument("--reps", type=int, default=50)
    p.set_defaults(func=cmd_backtest)

    p = sub.add_parser("simulate", help="simulate many players over many draws")
    p.add_argument("game", nargs="?", default="canada_649")
    p.add_argument("--players", type=int, default=10000)
    p.add_argument("--draws", type=int, default=520)
    p.add_argument("--tickets", type=int, default=1)
    p.add_argument("--bankroll", type=float, default=5000.0)
    p.add_argument("--jackpot", type=float, default=50_000_000.0)
    p.add_argument("--seed", type=int, default=0)
    p.set_defaults(func=cmd_simulate)

    p = sub.add_parser("digits", help="audit a digit game (2D/3D/Pick3/4D)")
    p.add_argument("game", nargs="?", default="myanmar_2d")
    p.add_argument("--values", help="file of results, whitespace separated")
    p.add_argument("--synth", type=int, help="simulate N fair draws instead")
    p.add_argument("--compare", action="store_true", help="compare house edges only")
    p.add_argument("--seed", type=int, default=0)
    p.set_defaults(func=cmd_digits)

    p = sub.add_parser("2d", help="derive a Myanmar 2D number from SET figures")
    p.add_argument("set_index", type=float, help="SET index, e.g. 1443.79")
    p.add_argument("trading_value", type=float, help="trading value in millions of baht")
    p.set_defaults(func=cmd_twod)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
