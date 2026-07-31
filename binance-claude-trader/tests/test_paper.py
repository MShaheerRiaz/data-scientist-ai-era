"""Paper-trading equity tests.

Paper mode was silently broken: equity came from the real Binance account, so
running against a fresh or empty account gave ~0 equity, every position sized
to 0, and the bot ran cleanly while never taking a trade. It looked like "no
setups found" rather than a bug, which is the worst way for this to fail.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import main  # noqa: E402
from binance_client import BinanceError  # noqa: E402
from config import Config, RiskLimits  # noqa: E402
from journal import StateStore  # noqa: E402
from risk import DayState, PaperAccount, Position, RiskGate  # noqa: E402


class StubClient:
    """Stands in for BinanceSpot. Records whether the signed account endpoint
    was hit, since paper mode must never call it."""

    def __init__(self, prices=None, real_equity=0.0, fail_prices=False):
        self.prices = prices or {}
        self.real_equity = real_equity
        self.fail_prices = fail_prices
        self.account_called = False

    def price(self, symbol):
        if self.fail_prices:
            raise BinanceError(500, {"msg": "quote unavailable"})
        return self.prices[symbol]

    def equity_in_quote(self, _quote="USDT"):
        self.account_called = True
        return self.real_equity


def make_cfg(**over) -> Config:
    base = dict(
        binance_key="", binance_secret="", testnet=False,
        anthropic_key="k", dry_run=True, paper_equity=10_000.0,
    )
    base.update(over)
    return Config(**base)


def test_paper_equity_ignores_the_real_account():
    """The core bug: an empty real account must not zero out paper equity."""
    client = StubClient(real_equity=0.0)
    equity = main.current_equity(make_cfg(), client, {}, PaperAccount(10_000.0))
    assert equity == 10_000.0
    assert not client.account_called, "paper mode must not query the real balance"


def test_live_mode_reads_the_real_account():
    client = StubClient(real_equity=4_200.0)
    equity = main.current_equity(make_cfg(dry_run=False), client, {}, PaperAccount())
    assert equity == 4_200.0
    assert client.account_called


def test_paper_equity_includes_realised_pnl():
    paper = PaperAccount(starting_equity=10_000.0, realised_total=350.0)
    assert main.current_equity(make_cfg(), StubClient(), {}, paper) == 10_350.0


def test_paper_equity_includes_unrealised_on_open_positions():
    positions = {"BTCUSDT": Position("BTCUSDT", 2.0, 100.0, 96.0, 110.0, "now")}
    client = StubClient(prices={"BTCUSDT": 105.0})
    # 2 units up 5.0 each = +10 unrealised
    assert main.current_equity(make_cfg(), client, positions, PaperAccount(10_000.0)) == 10_010.0


def test_unrealised_loss_reduces_paper_equity():
    positions = {"BTCUSDT": Position("BTCUSDT", 2.0, 100.0, 96.0, 110.0, "now")}
    client = StubClient(prices={"BTCUSDT": 97.0})
    assert main.current_equity(make_cfg(), client, positions, PaperAccount(10_000.0)) == 9_994.0


def test_price_failure_falls_back_to_entry_not_inflation():
    """A failed quote must understate equity, never overstate it."""
    positions = {"BTCUSDT": Position("BTCUSDT", 2.0, 100.0, 96.0, 110.0, "now")}
    client = StubClient(fail_prices=True)
    equity = main.current_equity(make_cfg(), client, positions, PaperAccount(10_000.0))
    assert equity == 10_000.0  # entry price -> zero unrealised


def test_paper_equity_actually_sizes_a_position():
    """End to end: the bug's real symptom was every trade sizing to zero."""
    gate = RiskGate(RiskLimits())
    equity = main.current_equity(make_cfg(), StubClient(real_equity=0.0), {}, PaperAccount(10_000.0))
    verdict = gate.evaluate(
        decision={
            "action": "open", "symbol": "BTCUSDT", "side": "long",
            "entry": 100.0, "stop": 96.0, "target": 110.0,
            "confidence": 0.8, "reasoning": "t", "rejected": [],
        },
        equity=equity,
        positions={},
        day=DayState(),
        denylist=(),
        tradable_symbols={"BTCUSDT"},
    )
    assert verdict.approved
    assert verdict.quote_amount > 0, "the original bug: zero-sized position"
    assert round(verdict.quote_amount, 2) == 1250.00


def test_paper_pnl_survives_restart_and_honours_a_changed_balance():
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        store = StateStore(os.path.join(tmp, "state.json"))
        store.save({}, DayState(), PaperAccount(10_000.0, realised_total=250.0))

        # Same configured balance: realised PnL carries over.
        _, _, paper = store.load(PaperAccount(10_000.0))
        assert paper.realised_total == 250.0
        assert paper.starting_equity == 10_000.0

        # Raising PAPER_EQUITY in .env must take effect, not be ignored by
        # the persisted value.
        _, _, paper = store.load(PaperAccount(50_000.0))
        assert paper.starting_equity == 50_000.0
        assert paper.realised_total == 250.0


def test_missing_state_file_uses_the_configured_default():
    store = StateStore("/nonexistent/path/state.json")
    positions, day, paper = store.load(PaperAccount(7_500.0))
    assert positions == {} and day.realised_pnl == 0.0
    assert paper.starting_equity == 7_500.0


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
