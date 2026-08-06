"""End-to-end tour of lotterylab.

Run with::

    python examples/demo.py

Everything below uses synthetic fair draws, so the audit results are what
an honest lottery looks like. Point it at real data with ``load_csv``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lotterylab import PRESETS, DIGIT_PRESETS, synthesize, SynthBias
from lotterylab.combinatorics import jackpot_probability, odds_string
from lotterylab.digits import DigitHistory, derive_myanmar_2d, digit_audit
from lotterylab.ev import (
    EVAssumptions,
    break_even_jackpot,
    kelly_fraction,
    rolldown_ev,
    ticket_ev,
    ziemba_break_even_factor,
)
from lotterylab.fairness import audit, power_analysis
from lotterylab.generate import generate_random, generate_unpopular
from lotterylab.popularity import PopularityModel, share_factor
from lotterylab.simulate import jackpot_waiting_time, simulate_play
from lotterylab.wheels import covering_design, guarantee_report, schonheim_bound


def banner(text: str) -> None:
    print("\n" + "=" * 78)
    print(text)
    print("=" * 78)


def main() -> None:
    cfg = PRESETS["canada_649"]

    banner("1. THE ODDS")
    for key in ("canada_649", "uk_lotto", "euromillions", "powerball"):
        game = PRESETS[key]
        print(f"  {game.name:<24} {odds_string(jackpot_probability(game))}")

    banner("2. IS THE DRAW FAIR? (2,000 synthetic fair draws)")
    history = synthesize(cfg, 2000, seed=42)
    report = audit(history, include_pair_test=False)
    for test in report.tests:
        print("  " + str(test))
    print("\n  " + report.verdict())

    banner("3. ...BUT COULD YOU EVEN TELL?")
    power = power_analysis(cfg, 2000)
    print(f"  {power['note']}\n")
    for lift, needed in sorted(power["draws_required"].items()):
        print(f"    {(lift - 1) * 100:>5.0f}% hot ball -> {needed:>12,.0f} draws "
              f"({needed / 104:>8,.0f} years)")

    banner("4. THE AUDIT DOES CATCH REAL BIAS")
    rigged = synthesize(cfg, 2000, seed=7, bias=SynthBias(weights={17: 2.0}))
    rigged_report = audit(rigged, include_pair_test=False)
    print(f"  Injected: ball 17 weighted 2x")
    print(f"  Flagged after FDR correction: "
          f"{[b.ball for b in rigged_report.flagged_balls] or 'none'}")

    banner("5. WHAT IS A TICKET WORTH? (jackpot sharing included)")
    powerball = PRESETS["powerball"]
    print(f"  {'jackpot':>15}{'sales':>15}{'co-winners':>12}{'you keep':>10}{'EV':>8}{'net':>9}")
    for jackpot in (3e8, 1.586e9, 5e9):
        assumptions = EVAssumptions(jackpot=jackpot, cash_value_ratio=0.52, tax_rate=0.37,
                                    sales_base=20e6, sales_per_jackpot_unit=0.39)
        result = ticket_ev(powerball, assumptions)
        jack = [row for row in result.tiers if row.tier.is_jackpot][0]
        print(f"  {jackpot:>15,.0f}{assumptions.effective_sales(jackpot):>15,}"
              f"{jack.expected_cowinners:>12.2f}{jack.share:>10.3f}"
              f"{result.expected_value:>8.3f}{result.net_ev:>+9.3f}")
    unreachable = break_even_jackpot(
        powerball,
        EVAssumptions(cash_value_ratio=0.52, tax_rate=0.37,
                      sales_base=20e6, sales_per_jackpot_unit=0.39),
    )
    print(f"\n  Break-even jackpot: {unreachable or 'UNREACHABLE AT ANY SIZE'}")
    print("  Sales grow with the prize, so the crowd you split with grows just as fast.")

    banner("6. THE SHARING TERM")
    for lam in (0.1, 0.5, 1.0, 3.0, 10.0):
        print(f"  expected other winners {lam:>5} -> you keep {share_factor(lam):.3f}")

    banner("7. WHICH COMBINATIONS DO OTHER PLAYERS PICK?")
    model = PopularityModel(cfg)
    for label, combo in [
        ("1,2,3,4,5,6", (1, 2, 3, 4, 5, 6)),
        ("all birthdays", (3, 7, 12, 19, 24, 31)),
        ("evenly spread", (4, 12, 20, 28, 36, 44)),
        ("high, irregular", (2, 29, 37, 42, 44, 48)),
    ]:
        print(f"  {label:<18} {model.multiplier(combo):>7.3f}x raw   "
              f"{model.effective_multiplier(combo):>6.3f}x after quick-pick dilution")
    print(f"\n  Ziemba break-even: every number must be "
          f"{(ziemba_break_even_factor() - 1) * 100:.1f}% under-bet just to reach a fair bet.")

    banner("8. GENERATING TICKETS")
    print(generate_unpopular(cfg, 4, salt="demo").to_text())

    banner("9. WHEELS - GUARANTEES THAT ARE VERIFIED, NOT ASSERTED")
    wheel = covering_design(range(1, 13), 6, 4, seed=1)
    print(f"  {wheel.describe()}")
    print(f"  Schoenheim lower bound: {schonheim_bound(12, 6, 4)}\n")
    for hits, best in sorted(guarantee_report(wheel, 6).items()):
        print(f"    {hits} of your numbers drawn -> at least {best} match(es)")

    banner("10. THE ONE STRUCTURE THAT GENUINELY PAID: ROLL-DOWNS")
    from lotterylab.config import LotteryConfig, PrizeTier

    winfall = LotteryConfig(
        name="Cash WinFall (MA 6/46)", main_pool=46, main_pick=6, ticket_price=2.0,
        tiers=(PrizeTier("6", 6, 0, 0.0, is_jackpot=True, is_parimutuel=True),
               PrizeTier("5", 5, 0, 4000.0),
               PrizeTier("4", 4, 0, 150.0),
               PrizeTier("3", 3, 0, 5.0)),
    )
    rolled = rolldown_ev(winfall, rolldown_pool=2_000_000, tickets_sold=1_000_000,
                         eligible_tiers=["5", "4", "3"])
    for row in rolled.tiers:
        if row.tier.payout > 0:
            print(f"    {row.tier.name:<4} ${row.tier.payout:>7,.0f} -> "
                  f"${row.gross_payout:>9,.0f}  (x{row.gross_payout / row.tier.payout:.2f})")
    print(f"\n  Return: {rolled.return_ratio:.3f} on a $2 ticket "
          f"({'POSITIVE EV' if rolled.net_ev > 0 else 'negative'})")
    print("  Historical record: x5.75 / x5.33 / x5.20, syndicates reported 15-20%.")

    banner("11. MYANMAR 2D")
    print(f"  SET index 1443.79, turnover 24,221.65M -> "
          f"2D = {derive_myanmar_2d(1443.79, 24221.65):02d}   (published: 91)")
    print(f"  Folklore 'last two digits of index' would give "
          f"{int(1443.79) % 100:02d} - wrong.\n")
    import random as _random

    rng = _random.Random(3)
    digits_history = DigitHistory.from_values(
        DIGIT_PRESETS["myanmar_2d"], [rng.randrange(100) for _ in range(4000)]
    )
    for test in digit_audit(digits_history).tests:
        print("  " + str(test))

    banner("12. WHAT ACTUALLY HAPPENS IF YOU PLAY")
    sim = simulate_play(cfg, n_players=5000, n_draws=520, tickets_per_draw=1,
                        starting_bankroll=3000.0, jackpot=20_000_000.0, seed=1)
    print(sim.to_text())
    wait = jackpot_waiting_time(cfg, tickets_per_draw=1)
    print(f"\n  Expected wait for a jackpot: {wait['expected_years']:,.0f} years")
    print(f"  Chance across 50 years of play: {wait['odds_string_50y']}")
    print(f"  Kelly stake for this ticket: "
          f"{kelly_fraction(jackpot_probability(cfg), 20e6 / cfg.ticket_price):.3e}"
          f"   (negative = do not bet)")


if __name__ == "__main__":
    main()
