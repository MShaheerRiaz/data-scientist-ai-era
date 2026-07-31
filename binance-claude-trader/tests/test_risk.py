"""Risk gate tests.

This is the file that matters. The gate is the only thing standing between a
bad model output and your balance, so its behaviour is pinned here rather than
trusted.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import RiskLimits  # noqa: E402
from risk import DayState, Position, RiskGate  # noqa: E402

LIMITS = RiskLimits()
TRADABLE = {"BTCUSDT", "ETHUSDT", "SOLUSDT"}
DENYLIST = ("USDCUSDT",)
EQUITY = 10_000.0


def gate() -> RiskGate:
    return RiskGate(LIMITS)


def good_decision(**overrides) -> dict:
    base = {
        "action": "open",
        "symbol": "BTCUSDT",
        "side": "long",
        "entry": 100.0,
        "stop": 96.0,     # 4% stop
        "target": 110.0,  # 2.5 R:R
        "confidence": 0.75,
        "reasoning": "test",
        "rejected": [],
    }
    base.update(overrides)
    return base


def evaluate(decision, positions=None, day=None, equity=EQUITY):
    return gate().evaluate(
        decision=decision,
        equity=equity,
        positions=positions or {},
        day=day or DayState(),
        denylist=DENYLIST,
        tradable_symbols=TRADABLE,
    )


def test_valid_decision_is_approved_and_sized():
    v = evaluate(good_decision())
    assert v.approved
    # 0.5% of 10k = 50 risk; 4% stop -> 1250 notional, under the 3000 cap.
    assert round(v.quote_amount, 2) == 1250.00
    assert round(v.risk_amount, 2) == 50.00
    assert round(v.reward_risk, 2) == 2.50


def test_notional_cap_binds_when_stop_is_tight():
    # 0.5% stop would imply 10000 notional on 50 risk — the whole account.
    v = evaluate(good_decision(stop=99.5, target=101.0))
    assert v.approved
    assert v.quote_amount == EQUITY * LIMITS.max_position_pct
    assert v.risk_amount < EQUITY * LIMITS.risk_per_trade


def test_notional_cap_does_not_bind_on_typical_atr_stops():
    """Guards the config interaction that broke this on first run.

    The cap must not silently override risk_per_trade on ordinary trades. If
    max_position_pct is set too low relative to risk_per_trade it binds on
    every realistic stop and the risk setting stops doing anything.
    """
    for stop_pct in (0.02, 0.03, 0.04, 0.05):
        entry = 100.0
        decision = good_decision(
            stop=entry * (1 - stop_pct),
            target=entry * (1 + stop_pct * 2),
        )
        v = evaluate(decision)
        assert v.approved, f"{stop_pct:.0%} stop should be tradable"
        assert round(v.risk_amount, 2) == round(EQUITY * LIMITS.risk_per_trade, 2), (
            f"cap bound at a {stop_pct:.0%} stop — max_position_pct is too low "
            f"relative to risk_per_trade"
        )


def test_full_book_cannot_exceed_equity():
    assert LIMITS.max_position_pct * LIMITS.max_concurrent_positions <= 1.0


def test_short_is_rejected_on_spot():
    v = evaluate(good_decision(side="none"))
    assert not v.approved
    assert "not tradable on spot" in v.reason


def test_inverted_stop_is_rejected():
    v = evaluate(good_decision(stop=105.0))
    assert not v.approved
    assert "must sit below entry" in v.reason


def test_target_below_entry_is_rejected():
    v = evaluate(good_decision(target=99.0))
    assert not v.approved
    assert "must sit above entry" in v.reason


def test_low_confidence_is_rejected():
    v = evaluate(good_decision(confidence=0.4))
    assert not v.approved
    assert "confidence" in v.reason


def test_poor_reward_risk_is_rejected():
    v = evaluate(good_decision(target=101.0))  # 0.25 R:R against a 4% stop
    assert not v.approved
    assert "reward:risk" in v.reason


def test_absurdly_wide_stop_is_rejected():
    v = evaluate(good_decision(stop=50.0, target=200.0))
    assert not v.approved
    assert "exceeds cap" in v.reason


def test_implausibly_tight_stop_is_rejected():
    v = evaluate(good_decision(stop=99.99, target=101.0))
    assert not v.approved
    assert "implausibly tight" in v.reason


def test_unknown_symbol_is_rejected():
    v = evaluate(good_decision(symbol="SCAMUSDT"))
    assert not v.approved
    assert "not a tradable spot symbol" in v.reason


def test_denylisted_symbol_is_rejected():
    v = evaluate(good_decision(symbol="USDCUSDT"))
    assert not v.approved
    assert "denylisted" in v.reason


def test_duplicate_position_is_rejected():
    held = {"BTCUSDT": Position("BTCUSDT", 1.0, 100.0, 96.0, 110.0, "now")}
    v = evaluate(good_decision(), positions=held)
    assert not v.approved
    assert "already holding" in v.reason


def test_max_concurrent_positions_is_enforced():
    held = {
        sym: Position(sym, 1.0, 100.0, 96.0, 110.0, "now")
        for sym in ("ETHUSDT", "SOLUSDT", "XRPUSDT")
    }
    v = evaluate(good_decision(), positions=held)
    assert not v.approved
    assert "max concurrent positions" in v.reason


def test_kill_switch_trips_on_daily_loss_and_blocks_new_trades():
    day = DayState(realised_pnl=-350.0)  # -3.5% of 10k, past the 3% cap
    v = evaluate(good_decision(), day=day)
    assert not v.approved
    assert "halted" in v.reason
    assert day.halted


def test_kill_switch_stays_tripped_once_set():
    day = DayState(realised_pnl=0.0, halted=True, halt_reason="manual")
    v = evaluate(good_decision(), day=day)
    assert not v.approved
    assert "halted" in v.reason


def test_new_utc_day_clears_the_halt():
    day = DayState(date="1999-01-01", realised_pnl=-500.0, halted=True, halt_reason="old")
    day.roll_if_new_day()
    assert not day.halted
    assert day.realised_pnl == 0.0


def test_confidence_does_not_affect_position_size():
    """Sizing must be indifferent to confidence, or the model has an incentive
    to inflate it."""
    low = evaluate(good_decision(confidence=0.61))
    high = evaluate(good_decision(confidence=0.99))
    assert low.approved and high.approved
    assert low.quote_amount == high.quote_amount


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
