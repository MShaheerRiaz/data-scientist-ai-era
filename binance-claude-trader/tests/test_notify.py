"""Notifier tests: fire-and-forget must mean exactly that.

A Telegram outage, a bad token, or a raised exception inside send() must
never propagate into the trading loop — the notification is a nice-to-have,
the position management is not.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Config  # noqa: E402
from notify import TelegramNotifier, notifier_from_config  # noqa: E402


class _Response:
    def __init__(self, status_code=200, text="ok"):
        self.status_code = status_code
        self.text = text


def test_send_posts_token_chat_id_and_text():
    calls = []

    def fake_post(url, json=None, timeout=None):
        calls.append((url, json, timeout))
        return _Response()

    n = TelegramNotifier("TOKEN123", "42", post_fn=fake_post)
    assert n.send("hello") is True

    url, body, timeout = calls[0]
    assert "botTOKEN123/sendMessage" in url
    assert body == {"chat_id": "42", "text": "hello"}
    assert timeout == 10


def test_send_swallows_exceptions():
    def exploding_post(url, json=None, timeout=None):
        raise ConnectionError("telegram is down")

    n = TelegramNotifier("t", "c", post_fn=exploding_post)
    assert n.send("hello") is False  # no exception escapes


def test_send_reports_http_errors_as_false():
    n = TelegramNotifier("t", "c", post_fn=lambda *a, **k: _Response(401, "unauthorized"))
    assert n.send("hello") is False


def _cfg(**kw) -> Config:
    base = dict(binance_key="", binance_secret="", testnet=False, anthropic_key="k")
    base.update(kw)
    return Config(**base)


def test_notifier_from_config_requires_both_settings():
    assert notifier_from_config(_cfg()) is None
    assert notifier_from_config(_cfg(telegram_token="t")) is None
    assert notifier_from_config(_cfg(telegram_chat_id="c")) is None

    n = notifier_from_config(_cfg(telegram_token="t", telegram_chat_id="c"))
    assert isinstance(n, TelegramNotifier)


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
