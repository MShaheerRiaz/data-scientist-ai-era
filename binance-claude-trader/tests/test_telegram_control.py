"""Tests for the two-way Telegram interface.

Two things matter most here and both are pinned below:

  1. Only the configured chat can command the bot. Anyone who finds the bot's
     username can message it, so an unauthorised /pause must be discarded —
     while still being acknowledged, or Telegram redelivers it forever.
  2. No command can raise. The handler runs inside the trading loop; an
     exception formatting a reply must never become an exception that stops
     managing a live position.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Config  # noqa: E402
from lessons import LessonBook  # noqa: E402
from notify import TelegramNotifier  # noqa: E402
from risk import DayState, PaperAccount, Position  # noqa: E402
from telegram_control import CommandHandler, Controls, _tail_events  # noqa: E402


class _Response:
    def __init__(self, payload=None, status_code=200):
        self.status_code = status_code
        self._payload = payload or {"result": []}
        self.text = "ok"

    def json(self):
        return self._payload


def _update(update_id: int, text: str, chat_id: str = "42") -> dict:
    return {
        "update_id": update_id,
        "message": {"chat": {"id": int(chat_id)}, "text": text},
    }


# --- polling and authorisation ---------------------------------------------


def test_poll_returns_messages_from_the_configured_chat():
    n = TelegramNotifier(
        "t", "42",
        get_fn=lambda *a, **k: _Response({"result": [_update(1, "/status")]}),
    )
    assert n.poll_commands() == ["/status"]


def test_poll_ignores_messages_from_other_chats_but_still_acks_them():
    """An unauthorised message must be dropped AND acknowledged — otherwise
    Telegram redelivers it on every poll for as long as the bot runs."""
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(params)
        if len(calls) == 1:
            return _Response({"result": [_update(7, "/pause", chat_id="999")]})
        return _Response({"result": []})

    n = TelegramNotifier("t", "42", get_fn=fake_get)
    assert n.poll_commands() == []
    n.poll_commands()
    # Second poll advanced past the stranger's update.
    assert calls[1]["offset"] == 8


def test_poll_advances_offset_so_commands_are_not_repeated():
    n = TelegramNotifier(
        "t", "42",
        get_fn=lambda *a, **k: _Response({"result": [_update(3, "/status")]}),
    )
    n.poll_commands()
    assert n._offset == 4


def test_poll_swallows_network_errors():
    def exploding_get(*a, **k):
        raise ConnectionError("no network")

    n = TelegramNotifier("t", "42", get_fn=exploding_get)
    assert n.poll_commands() == []


def test_long_replies_are_truncated_not_dropped():
    sent = {}

    def fake_post(url, json=None, timeout=None):
        sent.update(json)
        return _Response()

    n = TelegramNotifier("t", "42", post_fn=fake_post)
    n.send("x" * 9000)
    assert len(sent["text"]) < 4200
    assert sent["text"].endswith("(truncated)")


# --- command replies --------------------------------------------------------


def _handler(tmp: str, **cfg_kw):
    cfg = Config(
        binance_key="", binance_secret="", testnet=False, anthropic_key="k",
        dry_run=True, paper_equity=10_000.0,
        journal_path=os.path.join(tmp, "journal.jsonl"),
        lessons_path=os.path.join(tmp, "lessons.json"),
        **cfg_kw,
    )
    positions: dict = {}
    day = DayState()
    paper = PaperAccount(starting_equity=10_000.0)
    book = LessonBook(cfg.lessons_path, 25)
    return CommandHandler(
        cfg, positions, day, paper, book, Controls(),
        equity_fn=lambda: 10_000.0,
        price_fn=lambda symbol: 105.0,
    )


def _write_journal(path: str, records: list[dict]) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record) + "\n")


def test_status_reports_live_state():
    with tempfile.TemporaryDirectory() as tmp:
        h = _handler(tmp)
        h.day.realised_pnl = -25.0
        reply = h.handle("/status")
        assert "PAPER" in reply
        assert "-25.00" in reply
        assert "0/3" in reply


def test_status_reflects_pause_and_halt():
    with tempfile.TemporaryDirectory() as tmp:
        h = _handler(tmp)
        h.controls.paused = True
        assert "PAUSED" in h.handle("/status")

        h.day.halted = True
        h.day.halt_reason = "daily loss breached"
        # A halt is more serious than a pause and must be what you see.
        assert "HALTED" in h.handle("/status")


def test_positions_report_shows_r_multiple():
    with tempfile.TemporaryDirectory() as tmp:
        h = _handler(tmp)
        assert "No open positions" in h.handle("/positions")

        h.positions["BTCUSDT"] = Position(
            symbol="BTCUSDT", entry=100.0, stop=96.0, target=110.0,
            quantity=12.5, opened_at="2026-08-07T10:00:00+00:00",
        )
        reply = h.handle("/positions")
        # Price 105 vs entry 100 on 12.5 units = +62.50, and 5/4 = +1.25R.
        assert "+62.50" in reply
        assert "+1.25R" in reply


def test_why_reports_the_last_decision_and_its_reasoning():
    with tempfile.TemporaryDirectory() as tmp:
        h = _handler(tmp)
        assert "No decisions" in h.handle("/why")

        _write_journal(h.cfg.journal_path, [
            {"ts": "2026-08-07T10:00:00+00:00", "event": "decision", "action": "none",
             "symbol": "", "approved": False, "verdict": "model chose no trade",
             "confidence": 0.0, "reasoning": "old one"},
            {"ts": "2026-08-07T11:00:00+00:00", "event": "decision", "action": "open",
             "symbol": "ETHUSDT", "approved": True, "verdict": "ok", "entry": 3000,
             "stop": 2900, "target": 3300, "confidence": 0.75,
             "reasoning": "reclaimed the range high on expanding volume",
             "rejected": ["BTCUSDT"]},
        ])
        reply = h.handle("/why")
        assert "ETHUSDT" in reply
        assert "reclaimed the range high" in reply
        assert "APPROVED" in reply
        assert "BTCUSDT" in reply  # what it looked at and passed on
        assert "old one" not in reply


def test_rejected_lists_only_blocked_entries():
    with tempfile.TemporaryDirectory() as tmp:
        h = _handler(tmp)
        _write_journal(h.cfg.journal_path, [
            {"ts": "2026-08-07T10:00:00+00:00", "event": "decision", "action": "open",
             "symbol": "BTCUSDT", "approved": True, "verdict": "ok"},
            {"ts": "2026-08-07T11:00:00+00:00", "event": "decision", "action": "open",
             "symbol": "SOLUSDT", "approved": False, "verdict": "reward:risk 0.8 below 1.2"},
        ])
        reply = h.handle("/rejected")
        assert "SOLUSDT" in reply and "reward:risk" in reply
        assert "BTCUSDT" not in reply


def test_pnl_warns_when_the_sample_is_too_small():
    with tempfile.TemporaryDirectory() as tmp:
        h = _handler(tmp)
        assert "No closed trades" in h.handle("/pnl")

        _write_journal(h.cfg.journal_path, [
            {"ts": "2026-08-07T10:00:00+00:00", "event": "fill", "side": "sell",
             "symbol": "BTCUSDT", "order": {"pnl": 60.0}},
            {"ts": "2026-08-07T11:00:00+00:00", "event": "fill", "side": "sell",
             "symbol": "ETHUSDT", "order": {"pnl": -20.0}},
        ])
        reply = h.handle("/pnl")
        assert "Closed trades 2" in reply
        assert "50%" in reply
        assert "+40.00" in reply
        # Two trades must not be presented as evidence of an edge.
        assert "too few" in reply


def test_journal_tail_renders_mixed_event_types():
    with tempfile.TemporaryDirectory() as tmp:
        h = _handler(tmp)
        _write_journal(h.cfg.journal_path, [
            {"ts": "2026-08-07T10:00:00+00:00", "event": "decision", "action": "open",
             "symbol": "BTCUSDT", "approved": True, "verdict": "ok"},
            {"ts": "2026-08-07T10:05:00+00:00", "event": "skip", "symbol": "BTCUSDT",
             "reason": "entry_drift"},
            {"ts": "2026-08-07T11:00:00+00:00", "event": "error", "where": "decide",
             "message": "timeout"},
        ])
        reply = h.handle("/journal")
        assert "open BTCUSDT" in reply
        assert "entry_drift" in reply
        assert "ERROR in decide" in reply


def test_pause_and_resume_toggle_controls():
    with tempfile.TemporaryDirectory() as tmp:
        h = _handler(tmp)
        first = h.handle("/pause")
        assert "Paused" in first
        assert h.controls.paused is True
        # The reply must say open risk is still supervised — pausing is easy to
        # mistake for "the bot has stopped looking after my positions".
        assert "stops and targets" in first
        assert "Already paused" in h.handle("/pause")

        assert "Resumed" in h.handle("/resume")
        assert h.controls.paused is False
        assert "Not paused" in h.handle("/resume")


def test_unknown_command_returns_help_not_an_error():
    with tempfile.TemporaryDirectory() as tmp:
        reply = _handler(tmp).handle("/nonsense")
        assert "Unknown command" in reply
        assert "/status" in reply


def test_group_style_command_suffix_is_stripped():
    with tempfile.TemporaryDirectory() as tmp:
        assert "PAPER" in _handler(tmp).handle("/status@my_trading_bot")


def test_handler_never_raises_even_when_state_is_broken():
    """The handler runs inside the trading loop. A formatting failure must
    come back as text, not as an exception that stops managing positions."""
    with tempfile.TemporaryDirectory() as tmp:
        h = _handler(tmp)

        def exploding_equity():
            raise RuntimeError("exchange unreachable")

        h._equity = exploding_equity
        reply = h.handle("/status")
        assert "Could not read equity" in reply

        # A position whose price lookup fails still renders the rest.
        h.positions["BTCUSDT"] = Position(
            symbol="BTCUSDT", entry=100.0, stop=96.0, target=110.0,
            quantity=1.0, opened_at="2026-08-07T10:00:00+00:00",
        )
        h._price = lambda s: (_ for _ in ()).throw(RuntimeError("no price"))
        assert "price unavailable" in h.handle("/positions")


def test_poll_and_reply_answers_each_command():
    with tempfile.TemporaryDirectory() as tmp:
        h = _handler(tmp)
        sent = []

        class FakeNotifier:
            def poll_commands(self):
                return ["/status", "/lessons"]

            def send(self, text):
                sent.append(text)
                return True

        assert h.poll_and_reply(FakeNotifier()) == 2
        assert len(sent) == 2
        assert "No lessons recorded yet" in sent[1]


def test_tail_reads_only_the_end_of_a_large_journal():
    """The journal grows forever; answering /status must not get slower every
    day the bot runs."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "big.jsonl")
        _write_journal(path, [
            {"ts": f"2026-08-07T10:00:{i % 60:02d}+00:00", "event": "decision",
             "action": "none", "symbol": "X" * 200, "approved": False, "verdict": "no"}
            for i in range(4000)
        ])
        assert os.path.getsize(path) > 256_000
        events = _tail_events(path, 5)
        assert len(events) == 5
        assert all(e["event"] == "decision" for e in events)


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
