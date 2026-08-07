"""Telegram notifications for the events worth a phone buzz.

Fire-and-forget by design: a notification that fails must never affect
trading, so send() swallows every error and just logs. The bot notifies on
position opens, closes (with P&L), the daily kill switch tripping, startup,
and shutdown with positions still open. Everything else stays in the journal.

Setup (one-time, ~2 minutes):
  1. In Telegram, message @BotFather, send /newbot, follow the prompts.
     It replies with a bot token like 123456:ABC-DEF...
  2. Open a chat with your new bot and send it any message (it cannot
     message you first).
  3. Visit https://api.telegram.org/bot<TOKEN>/getUpdates in a browser and
     read the number at "chat":{"id": ...} — that is your chat id.
  4. Put both in .env as TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.

Leave either value blank to disable notifications entirely.
"""

from __future__ import annotations

import requests


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, post_fn=None):
        self.token = token
        self.chat_id = chat_id
        # Injectable so tests exercise send() without the network.
        self._post = post_fn or requests.post

    def send(self, text: str) -> bool:
        """Send one message. Returns False on any failure, never raises."""
        try:
            resp = self._post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": self.chat_id, "text": text},
                timeout=10,
            )
            if resp.status_code != 200:
                print(f"[notify] telegram HTTP {resp.status_code}: {resp.text[:200]}")
                return False
            return True
        except Exception as exc:  # noqa: BLE001 - notifications must never break trading
            print(f"[notify] telegram send failed: {exc}")
            return False


def notifier_from_config(cfg) -> TelegramNotifier | None:
    """Build a notifier if both Telegram settings are present, else None.

    Callers treat None as "notifications off" — every send site is guarded,
    so an unconfigured bot runs exactly as before.
    """
    if cfg.telegram_token and cfg.telegram_chat_id:
        return TelegramNotifier(cfg.telegram_token, cfg.telegram_chat_id)
    return None
