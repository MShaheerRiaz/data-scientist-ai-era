"""Tests for the trading mathematics.

Verified against hand-computable cases wherever a closed form exists, so the
numbers the bot reports about its own edge are trustworthy.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from quant import (  # noqa: E402
    breakeven_win_rate,
    expectancy_r,
    kelly_fraction,
    kelly_fraction_fractional,
    liquidation_distance_pct,
    max_safe_leverage,
    risk_of_ruin,
    survival_probability,
    trades_needed_for_significance,
)


# --- expectancy -----------------------------------------------------------


def test_coin_flip_at_even_money_has_zero_edge():
    assert abs(expectancy_r(0.5, 1.0)) < 1e-12


def test_expectancy_matches_hand_calculation():
    # 0.4 * 3 - 0.6 * 1 = 0.6
    assert abs(expectancy_r(0.4, 3.0) - 0.6) < 1e-12


def test_low_win_rate_with_high_reward_is_still_profitable():
    assert expectancy_r(0.30, 3.0) > 0


def test_high_win_rate_with_poor_reward_can_lose_money():
    """The result that surprises people: 70% winners, still negative."""
    assert expectancy_r(0.70, 0.4) < 0


def test_breakeven_win_rate_is_the_inverse_relation():
    assert abs(breakeven_win_rate(2.0) - 1 / 3) < 1e-12
    assert abs(breakeven_win_rate(1.0) - 0.5) < 1e-12
    assert abs(breakeven_win_rate(0.5) - 2 / 3) < 1e-12


def test_breakeven_is_consistent_with_expectancy():
    for rr in (0.5, 1.0, 2.0, 3.5):
        assert abs(expectancy_r(breakeven_win_rate(rr), rr)) < 1e-12


# --- kelly ----------------------------------------------------------------


def test_kelly_matches_the_textbook_case():
    # p=0.6, b=1 -> f* = (0.6*1 - 0.4)/1 = 0.20
    assert abs(kelly_fraction(0.6, 1.0) - 0.20) < 1e-12


def test_kelly_is_zero_for_a_losing_strategy():
    assert kelly_fraction(0.4, 1.0) == 0.0


def test_kelly_is_zero_at_exactly_breakeven():
    assert kelly_fraction(breakeven_win_rate(2.0), 2.0) == 0.0


def test_fractional_kelly_scales_down():
    full = kelly_fraction(0.6, 1.0)
    assert abs(kelly_fraction_fractional(0.6, 1.0, 0.25) - full * 0.25) < 1e-12


def test_kelly_grows_with_edge():
    assert kelly_fraction(0.7, 1.0) > kelly_fraction(0.6, 1.0)


# --- risk of ruin ---------------------------------------------------------


def test_negative_edge_ruins_almost_surely():
    result = risk_of_ruin(win_rate=0.40, reward_risk=1.0, risk_per_trade=0.02, trades=500)
    assert result.probability_of_ruin > 0.9


def test_positive_edge_at_sane_size_rarely_ruins():
    result = risk_of_ruin(win_rate=0.55, reward_risk=1.5, risk_per_trade=0.005, trades=500)
    assert result.probability_of_ruin < 0.05
    assert result.median_final_equity > 1.0


def test_overbetting_a_real_edge_still_ruins():
    """The central lesson of position sizing: a good edge bet too big loses.

    Identical win rate and reward:risk in both runs — only the size differs.
    Two times Kelly is the theoretical point where expected log growth falls
    to zero, so beyond it a genuinely positive edge still destroys the account.
    """
    edge = dict(win_rate=0.55, reward_risk=1.5, trades=500)
    kelly = kelly_fraction(0.55, 1.5)  # 25%

    modest = risk_of_ruin(**edge, risk_per_trade=0.01)
    double_kelly = risk_of_ruin(**edge, risk_per_trade=kelly * 2)

    assert modest.probability_of_ruin < 0.01
    assert double_kelly.probability_of_ruin > 0.90
    # Positive edge, yet the median path ends below where it started.
    assert double_kelly.median_final_equity < 1.0


def test_full_kelly_is_growth_optimal_but_brutal():
    """Why nobody actually trades full Kelly.

    It maximises growth — the median outcome is enormous — while spending most
    of its life in deep drawdown, and losing half the account at some point in
    a large minority of runs. Both facts are true at once, which is exactly
    why fractional Kelly is the practical answer.
    """
    kelly = kelly_fraction(0.55, 1.5)
    full = risk_of_ruin(0.55, 1.5, kelly, trades=500)
    quarter = risk_of_ruin(0.55, 1.5, kelly * 0.25, trades=500)

    assert full.median_final_equity > quarter.median_final_equity
    assert full.median_max_drawdown > 0.80
    assert full.probability_of_ruin > 0.30
    # A quarter of Kelly gives up growth for survivability.
    assert quarter.probability_of_ruin < 0.02
    assert quarter.median_max_drawdown < full.median_max_drawdown


def test_larger_size_produces_deeper_drawdowns():
    edge = dict(win_rate=0.55, reward_risk=1.5, trades=300)
    small = risk_of_ruin(**edge, risk_per_trade=0.005)
    large = risk_of_ruin(**edge, risk_per_trade=0.05)
    assert large.median_max_drawdown > small.median_max_drawdown


def test_results_are_reproducible_with_a_seed():
    a = risk_of_ruin(0.55, 1.5, 0.01, trades=200, simulations=1000, seed=7)
    b = risk_of_ruin(0.55, 1.5, 0.01, trades=200, simulations=1000, seed=7)
    assert a.probability_of_ruin == b.probability_of_ruin


def test_percentiles_are_ordered():
    r = risk_of_ruin(0.55, 1.5, 0.01, trades=300)
    assert r.p05_final_equity <= r.median_final_equity <= r.p95_final_equity


# --- leverage -------------------------------------------------------------


def test_liquidation_distance_is_inverse_of_leverage():
    # 10x with 0.5% maintenance: 1/10 - 0.005 = 9.5%
    assert abs(liquidation_distance_pct(10, 0.005) - 0.095) < 1e-12


def test_hundred_x_liquidates_on_a_half_percent_move():
    assert abs(liquidation_distance_pct(100, 0.005) - 0.005) < 1e-12


def test_two_hundred_x_has_no_buffer_at_all():
    """Maintenance margin alone consumes the entire liquidation distance."""
    assert liquidation_distance_pct(200, 0.005) == 0.0
    assert survival_probability(200, volatility_pct=0.004) == 0.0


def test_survival_falls_as_leverage_rises():
    vol = 0.006  # ~0.6%, typical BTC 15m ATR
    assert (
        survival_probability(3, vol)
        > survival_probability(20, vol)
        > survival_probability(100, vol)
    )


def test_low_leverage_survives_ordinary_noise():
    assert survival_probability(3, volatility_pct=0.006) > 0.99


def test_max_safe_leverage_round_trips():
    vol = 0.006
    lev = max_safe_leverage(vol, survival_target=0.99)
    assert survival_probability(lev, vol) >= 0.985
    assert lev < 50


def test_higher_volatility_forces_lower_leverage():
    assert max_safe_leverage(0.02) < max_safe_leverage(0.004)


# --- sample size ----------------------------------------------------------


def test_small_edges_need_large_samples():
    assert trades_needed_for_significance(0.1) > 300


def test_large_edges_need_fewer_trades():
    assert trades_needed_for_significance(0.5) < trades_needed_for_significance(0.1)


def test_no_edge_is_never_significant():
    assert trades_needed_for_significance(0.0) == -1


if __name__ == "__main__":
    import traceback

    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception:  # noqa: BLE001 - test harness
            failed += 1
            print(f"  FAIL  {name}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
