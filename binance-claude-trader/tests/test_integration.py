"""End-to-end wiring test for the main loop.

Every module has unit tests, but run_cycle — the code that actually strings
them together — had never been executed before this file existed. These tests
drive the real run_cycle with a stubbed exchange and a stubbed model, through
every path a live session takes: no-trade, open, stop exit, review, lesson
recording, model-instructed close, kill switch, entry-drift skip, and restart
persistence.

No network. The stub exchange raises if paper mode ever touches the real
account balance, pinning the paper-equity fix permanently.
"""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import main  # noqa: E402
from binance_client import Candle, SymbolFilters  # noqa: E402
from config import Config, RiskLimits  # noqa: E402
from executor import Executor  # noqa: E402
from journal import Journal, StateStore  # noqa: E402
from lessons import LessonBook  # noqa: E402
from risk import DayState, PaperAccount, RiskGate  # noqa: E402


# --- stubs ----------------------------------------------------------------


def _filters(symbol: str) -> SymbolFilters:
    return SymbolFilters(
        symbol=symbol,
        tick_size=Decimal("0.01"),
        step_size=Decimal("0.0001"),
        min_qty=Decimal("0.0001"),
        min_notional=Decimal("5"),
        base_asset=symbol.removesuffix("USDT"),
        quote_asset="USDT",
    )


class StubBinance:
    """The subset of BinanceSpot the paper loop touches. No network."""

    def __init__(self, symbols=("BTCUSDT", "ETHUSDT")):
        self.current_price = {s: 100.0 for s in symbols}
        self._symbols = symbols
        self._filters = {s: _filters(s) for s in symbols}

    def ping(self):
        pass

    def load_filters(self):
        return self._filters

    def tradable(self):
        return set(self._filters)

    def ticker_24h(self):
        return [
            {"symbol": s, "quoteVolume": "50000000", "priceChangePercent": "2.5"}
            for s in self._symbols
        ]

    def klines(self, symbol, interval, limit=120):
        # Oscillating series with enough history for every indicator, ending
        # exactly at the stub's current price so decisions line up with fills.
        p = self.current_price[symbol]
        candles = []
        for i in range(130):
            base = p * (1 + 0.002 * math.sin(i / 5))
            candles.append(Candle(i, base, base * 1.002, base * 0.998, base, 100.0, i))
        candles[-1] = Candle(129, p, p * 1.002, p * 0.998, p, 100.0, 129)
        return candles

    def price(self, symbol):
        return self.current_price[symbol]

    def equity_in_quote(self, quote_asset="USDT"):
        raise AssertionError(
            "paper mode queried the real account balance — the silent-zero-equity "
            "bug is back"
        )


class StubProvider:
    """Scripted decisions and reviews; records everything it was asked."""

    def __init__(self):
        self.decisions: list[dict] = []
        self.decide_calls = 0
        self.review_payloads: list[dict] = []
        self.next_review: dict | None = None
        self.last_payload: dict | None = None

    def decide(self, system_prompt, payload, schema):
        assert system_prompt, "system prompt must not be empty"
        self.decide_calls += 1
        self.last_payload = payload
        usage = {"input_tokens": 100, "output_tokens": 50,
                 "cache_read_input_tokens": 2000, "cache_creation_input_tokens": 0}
        return self.decisions.pop(0), usage

    def review(self, system_prompt, payload, schema):
        self.review_payloads.append(payload)
        review = self.next_review or {
            "process_quality": "sound", "outcome": payload["outcome"],
            "should_record": False, "lesson": "", "tags": [], "analysis": "fine",
        }
        self.next_review = None
        return review, {"input_tokens": 50, "output_tokens": 30}


def none_decision() -> dict:
    return {"action": "none", "symbol": "", "side": "none", "entry": 0, "stop": 0,
            "target": 0, "confidence": 0.0, "reasoning": "nothing here",
            "rejected": ["BTCUSDT", "ETHUSDT"]}


def open_decision(symbol="BTCUSDT", entry=100.0, stop=96.0, target=110.0) -> dict:
    return {"action": "open", "symbol": symbol, "side": "long", "entry": entry,
            "stop": stop, "target": target, "confidence": 0.8,
            "reasoning": "test setup", "rejected": []}


class RecordingNotifier:
    """Stands in for TelegramNotifier; keeps every message it was asked to send."""

    def __init__(self):
        self.messages: list[str] = []

    def send(self, text: str) -> bool:
        self.messages.append(text)
        return True


class Harness:
    """A fully wired paper-trading session against the stubs."""

    def __init__(self, tmp: str, **overrides):
        self.cfg = Config(
            binance_key="", binance_secret="", testnet=False,
            anthropic_key="k", dry_run=True, paper_equity=10_000.0,
            journal_path=os.path.join(tmp, "journal.jsonl"),
            state_path=os.path.join(tmp, "state.json"),
            lessons_path=os.path.join(tmp, "lessons.json"),
            enable_news=False,
            min_quote_volume=1_000_000.0,
            **overrides,
        )
        self.client = StubBinance()
        self.provider = StubProvider()
        self.journal = Journal(self.cfg.journal_path)
        self.store = StateStore(self.cfg.state_path)
        self.gate = RiskGate(self.cfg.risk)
        self.executor = Executor(self.client, self.journal, dry_run=True)
        self.book = LessonBook(self.cfg.lessons_path, self.cfg.max_lessons)
        self.positions: dict = {}
        self.day = DayState()
        self.paper = PaperAccount(starting_equity=self.cfg.paper_equity)
        self.notifier = RecordingNotifier()

    def cycle(self):
        main.run_cycle(
            self.cfg, self.client, self.provider, self.gate, self.executor,
            self.journal, self.store, self.positions, self.day, self.paper,
            self.book, None, notifier=self.notifier,
        )

    def journal_events(self) -> list[dict]:
        with open(self.cfg.journal_path, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]


# --- tests ----------------------------------------------------------------


def test_no_trade_cycle_runs_clean():
    with tempfile.TemporaryDirectory() as tmp:
        h = Harness(tmp)
        h.provider.decisions = [none_decision()]
        h.cycle()
        assert h.positions == {}
        assert h.provider.decide_calls == 1
        events = h.journal_events()
        assert any(e["event"] == "decision" and e["action"] == "none" for e in events)
        # The model saw real candidates and account context.
        payload = h.provider.last_payload
        assert payload["account_equity_quote"] == 10_000.0
        assert {c["symbol"] for c in payload["candidates"]} == {"BTCUSDT", "ETHUSDT"}


def test_open_position_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        h = Harness(tmp)
        h.provider.decisions = [open_decision()]
        h.cycle()

        assert "BTCUSDT" in h.positions
        pos = h.positions["BTCUSDT"]
        # 0.5% of 10k = 50 risk against a 4% stop -> 1250 notional -> 12.5 units.
        assert round(pos.quantity, 4) == 12.5
        assert pos.entry == 100.0 and pos.stop == 96.0 and pos.target == 110.0
        # Entry evidence captured for the later review.
        assert pos.reasoning == "test setup"
        assert pos.entry_snapshot.get("symbol") == "BTCUSDT"
        # Fill journaled, state persisted.
        assert any(e["event"] == "fill" and e["side"] == "buy" for e in h.journal_events())
        stored, _, _ = h.store.load()
        assert "BTCUSDT" in stored


def test_stop_exit_updates_pnl_and_triggers_review():
    with tempfile.TemporaryDirectory() as tmp:
        h = Harness(tmp)
        h.provider.decisions = [open_decision(), none_decision()]
        h.cycle()

        h.client.current_price["BTCUSDT"] = 95.0  # through the 96 stop
        h.cycle()

        assert "BTCUSDT" not in h.positions
        # 12.5 units, entry 100, marked at 95 -> -62.5 realised.
        assert round(h.day.realised_pnl, 2) == -62.50
        assert round(h.paper.realised_total, 2) == -62.50
        # The reviewer saw entry-time evidence, not just the exit.
        assert len(h.provider.review_payloads) == 1
        review_payload = h.provider.review_payloads[0]
        assert review_payload["exit_reason"] == "stop"
        assert review_payload["original_reasoning"] == "test setup"
        assert review_payload["market_state_at_entry"].get("symbol") == "BTCUSDT"
        # The next decision was made against the reduced equity.
        assert h.provider.last_payload["account_equity_quote"] == 9_937.5


def test_lesson_from_review_reaches_the_next_decision():
    with tempfile.TemporaryDirectory() as tmp:
        h = Harness(tmp)
        h.provider.decisions = [open_decision(), none_decision(), none_decision()]
        h.cycle()

        h.provider.next_review = {
            "process_quality": "poor", "outcome": "loss", "should_record": True,
            "lesson": "Avoid chasing entries far above the range midpoint",
            "tags": ["chasing"], "analysis": "entered late",
        }
        h.client.current_price["BTCUSDT"] = 95.0
        h.cycle()

        assert len(h.book.lessons) == 1
        # The recorded lesson is injected into the following cycle's payload.
        h.cycle()
        assert "chasing entries" in h.provider.last_payload.get("lessons", "")


def test_model_close_realises_pnl_and_reviews():
    with tempfile.TemporaryDirectory() as tmp:
        h = Harness(tmp)
        close = {"action": "close", "symbol": "BTCUSDT", "side": "none", "entry": 0,
                 "stop": 0, "target": 0, "confidence": 0.9,
                 "reasoning": "thesis invalidated", "rejected": []}
        h.provider.decisions = [open_decision(), close]
        h.cycle()

        h.client.current_price["BTCUSDT"] = 104.0  # inside stop/target, model exits
        h.cycle()

        assert "BTCUSDT" not in h.positions
        assert round(h.day.realised_pnl, 2) == 50.0  # 12.5 * +4
        assert h.provider.review_payloads[0]["exit_reason"] == "model_close"


def test_kill_switch_blocks_decisions_but_not_exit_management():
    with tempfile.TemporaryDirectory() as tmp:
        h = Harness(tmp)
        h.provider.decisions = [open_decision()]
        h.cycle()
        assert h.provider.decide_calls == 1

        # Breach the daily cap; the stop also gets hit this cycle.
        h.day.realised_pnl = -400.0  # > 3% of ~10k
        h.client.current_price["BTCUSDT"] = 95.0
        h.cycle()

        # Exits were still honoured while halted...
        assert "BTCUSDT" not in h.positions
        # ...but no new decision was requested from the model.
        assert h.provider.decide_calls == 1
        assert h.day.halted


def test_entry_drift_guard_skips_stale_decisions():
    with tempfile.TemporaryDirectory() as tmp:
        h = Harness(tmp)
        # Model wants entry 100 (stop 96), but the market has run to 103 —
        # drift of 3 exceeds half the 4-point stop distance.
        h.provider.decisions = [open_decision(entry=100.0, stop=96.0, target=110.0)]
        h.client.current_price["BTCUSDT"] = 103.0
        h.cycle()

        assert h.positions == {}
        events = h.journal_events()
        skip = next(e for e in events if e["event"] == "skip")
        assert skip["reason"] == "entry_drift"


def test_price_through_stop_at_execution_is_skipped():
    with tempfile.TemporaryDirectory() as tmp:
        h = Harness(tmp)
        h.provider.decisions = [open_decision(entry=100.0, stop=96.0, target=110.0)]
        h.client.current_price["BTCUSDT"] = 95.0  # already below the stop
        h.cycle()

        assert h.positions == {}
        skip = next(e for e in h.journal_events() if e["event"] == "skip")
        assert skip["reason"] == "price_beyond_levels"


def test_exits_are_enforced_between_candles():
    """The intra-bar watcher: stops must fire from the sleep loop's
    manage_exits call, without waiting for the next decision cycle.

    This is what makes the 1h decision interval safe — protection runs on
    the POLL_SECONDS clock, not the candle clock.
    """
    with tempfile.TemporaryDirectory() as tmp:
        h = Harness(tmp)
        h.provider.decisions = [open_decision()]
        h.cycle()
        assert "BTCUSDT" in h.positions

        # Price hits the stop mid-bar. Call manage_exits exactly as the sleep
        # loop does — no decision cycle, no model call.
        h.client.current_price["BTCUSDT"] = 95.0
        closed = main.manage_exits(
            h.cfg, h.provider, h.executor, h.journal, h.store,
            h.positions, h.day, h.paper, h.book,
        )

        assert closed == 1
        assert "BTCUSDT" not in h.positions
        assert round(h.day.realised_pnl, 2) == -62.50
        # No decision was requested — only the exit was managed.
        assert h.provider.decide_calls == 1
        # And the close was persisted immediately, not left for the next cycle.
        stored, stored_day, _ = h.store.load()
        assert stored == {}
        assert round(stored_day.realised_pnl, 2) == -62.50


def test_notifications_fire_on_open_close_and_kill_switch():
    """Telegram messages go out for the events that matter, and only those."""
    with tempfile.TemporaryDirectory() as tmp:
        h = Harness(tmp)
        h.provider.decisions = [open_decision(), none_decision()]
        h.cycle()
        assert any("Opened BTCUSDT" in m for m in h.notifier.messages)

        # No-trade cycles stay silent — an alert per hour of nothing is noise.
        before = len(h.notifier.messages)
        h.day.realised_pnl = -400.0  # breach the daily cap
        h.client.current_price["BTCUSDT"] = 95.0
        h.cycle()

        closed = [m for m in h.notifier.messages if "Closed BTCUSDT on stop" in m]
        assert len(closed) == 1 and "-62.50" in closed[0]
        halts = [m for m in h.notifier.messages if "halted" in m]
        assert len(halts) == 1

        # Still halted next cycle: no repeat alert.
        h.cycle()
        assert len([m for m in h.notifier.messages if "halted" in m]) == 1
        assert len(h.notifier.messages) == before + 2


def test_symbol_allowlist_restricts_universe_and_gate():
    """Pinning SYMBOL_ALLOWLIST must hold at both layers: the model only sees
    allowlisted candidates, and even if it names something else anyway, the
    risk gate refuses it."""
    with tempfile.TemporaryDirectory() as tmp:
        h = Harness(tmp, symbol_allowlist=("ETHUSDT",))
        # The stub exchange lists BTCUSDT and ETHUSDT; the model disobeys the
        # candidate list and asks for BTCUSDT.
        h.provider.decisions = [open_decision(symbol="BTCUSDT")]
        h.cycle()

        # Layer 1: only the pinned symbol was offered as a candidate.
        payload = h.provider.last_payload
        assert {c["symbol"] for c in payload["candidates"]} == {"ETHUSDT"}

        # Layer 2: the off-list open was rejected, not filled.
        assert h.positions == {}
        decision_events = [e for e in h.journal_events() if e["event"] == "decision"]
        assert decision_events[-1]["approved"] is False
        assert "not a tradable" in decision_events[-1]["verdict"]


def test_full_session_survives_restart():
    with tempfile.TemporaryDirectory() as tmp:
        h = Harness(tmp)
        h.provider.decisions = [open_decision()]
        h.cycle()

        # A new harness over the same directory simulates a process restart.
        h2 = Harness(tmp)
        h2.positions, h2.day, h2.paper = h2.store.load(
            PaperAccount(starting_equity=h2.cfg.paper_equity)
        )
        assert "BTCUSDT" in h2.positions
        restored = h2.positions["BTCUSDT"]
        assert restored.stop == 96.0 and restored.target == 110.0
        assert restored.reasoning == "test setup"

        # And the restored session still manages the position: stop fires.
        h2.provider.decisions = [none_decision()]
        h2.client.current_price["BTCUSDT"] = 95.0
        h2.cycle()
        assert "BTCUSDT" not in h2.positions
        assert round(h2.day.realised_pnl, 2) == -62.50


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
