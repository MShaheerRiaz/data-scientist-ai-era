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


# Telegram rejects messages over 4096 characters outright, so long replies
# (the journal tail, the lesson book) are cut rather than silently dropped.
MAX_MESSAGE = 4000

# How many "a stranger messaged your bot" warnings to send per process run.
# Enough to tell you it is happening, few enough that it cannot become the
# spam channel it is warning you about.
MAX_REFUSAL_ALERTS = 3


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, post_fn=None, get_fn=None):
        self.token = token
        self.chat_id = chat_id
        # Injectable so tests exercise send()/poll() without the network.
        self._post = post_fn or requests.post
        self._get = get_fn or requests.get
        # Telegram's cursor: acknowledging update N stops it being redelivered.
        # Starts as None so the first poll takes whatever is pending.
        self._offset: int | None = None
        # Chat ids that have messaged the bot and been refused. Kept so you are
        # told once that someone found it, and capped so a stranger cycling
        # accounts cannot turn your alerts into a spam channel.
        self._refused_chats: set[str] = set()
        self._refusal_alerts = 0

    def send(self, text: str) -> bool:
        """Send one message. Returns False on any failure, never raises."""
        if len(text) > MAX_MESSAGE:
            text = text[:MAX_MESSAGE] + "\n… (truncated)"
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

    def poll_commands(self) -> list[str]:
        """Return new message texts sent to the bot by the configured chat.

        Short-polls: timeout=0 so this returns immediately and never stalls the
        trading loop. Anyone who discovers the bot's username can message it,
        so messages from any chat other than the configured one are discarded —
        this is the only thing standing between a stranger and /pause.

        Returns an empty list on any failure. Never raises.
        """
        try:
            params = {"timeout": 0}
            if self._offset is not None:
                params["offset"] = self._offset
            resp = self._get(
                f"https://api.telegram.org/bot{self.token}/getUpdates",
                params=params,
                timeout=15,
            )
            if resp.status_code != 200:
                print(f"[notify] getUpdates HTTP {resp.status_code}")
                return []
            updates = resp.json().get("result", [])
        except Exception as exc:  # noqa: BLE001 - polling must never break trading
            print(f"[notify] telegram poll failed: {exc}")
            return []

        texts: list[str] = []
        for update in updates:
            # Acknowledge every update, including ones we ignore — otherwise a
            # message from a stranger would be redelivered forever.
            update_id = update.get("update_id")
            if isinstance(update_id, int):
                self._offset = update_id + 1

            message = update.get("message") or {}
            chat_id = str((message.get("chat") or {}).get("id", ""))
            text = (message.get("text") or "").strip()
            if not text:
                continue
            if chat_id != str(self.chat_id):
                self._refuse(chat_id)
                continue
            texts.append(text)

        return texts

    def _refuse(self, chat_id: str) -> None:
        """Drop a message from an unauthorised chat, telling you the first few
        times it happens.

        The stranger gets no reply at all — not even an error — so the bot
        gives away nothing, not even that it is running.
        """
        print(f"[notify] refused message from unauthorised chat {chat_id}")
        if chat_id in self._refused_chats or self._refusal_alerts >= MAX_REFUSAL_ALERTS:
            return
        self._refused_chats.add(chat_id)
        self._refusal_alerts += 1
        self.send(
            f"🔒 Someone else messaged this bot (chat id {chat_id}). "
            f"They were ignored and got no reply. Nothing was exposed.\n"
            f"If this keeps happening, revoke the token with @BotFather "
            f"and put the new one in .env."
        )


def notifier_from_config(cfg) -> TelegramNotifier | None:
    """Build a notifier if both Telegram settings are present, else None.

    Callers treat None as "notifications off" — every send site is guarded,
    so an unconfigured bot runs exactly as before.
    """
    if cfg.telegram_token and cfg.telegram_chat_id:
        return TelegramNotifier(cfg.telegram_token, cfg.telegram_chat_id)
    return None
