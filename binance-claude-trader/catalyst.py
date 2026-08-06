"""Catalyst detection: what the market is actually reacting to right now.

Two independent signals, deliberately kept separate:

1. **Volume and volatility anomalies**, computed from Binance data alone. This
   is the objective half — no external service, no API key, no opinion. When a
   pair's volume jumps against its own recent baseline, something is happening
   in it, whether or not anyone has written about it yet.

2. **A news brief**, gathered by Claude with web search on a slow cadence. This
   is the subjective half and it is *context*, never a trade trigger on its own.

The ordering matters. Volume moves before headlines, and by the time a story is
widely reported the move it describes has usually already happened. So the
anomaly scan leads and the news brief explains — not the reverse.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import anthropic

from binance_client import Candle

# The news brief is deliberately free text rather than a strict schema. Nothing
# numeric depends on it — it is injected as background for the decision model,
# not parsed into prices or sizes — and mixing server-side tools with strict
# structured output adds a failure mode for no benefit here. If the brief comes
# back malformed the worst case is slightly noisy context, not a bad order.
NEWS_SYSTEM_PROMPT = """\
You are a crypto market analyst producing a short situational brief for an \
automated spot trading system. Search for what is actually moving markets right \
now.

Cover, briefly:
- Overall market posture (risk-on / risk-off / chop) and what is driving it
- Any macro events landing in the next 24h that historically move crypto \
(central bank decisions, CPI prints, large token unlocks, major listings, \
regulatory rulings)
- Specific assets with genuine catalysts right now, and what the catalyst is
- Anything that argues for standing aside entirely (an imminent high-impact \
event, extreme funding, a market-wide liquidation cascade in progress)

Rules:
- Report what has happened or is scheduled. Do not predict prices and do not \
give trade recommendations — a separate system makes those decisions.
- Distinguish confirmed news from rumour and speculation, and say which is which.
- If a story is already widely reported, say so. A catalyst everyone has traded \
is not an edge, and treating stale news as fresh is a common way to buy a top.
- Note when nothing significant is happening. "Quiet, no major catalysts" is a \
useful and frequently correct brief.
- Be concise. Under 250 words.\
"""


def volume_profile(candles: list[Candle], recent: int = 8, baseline: int = 60) -> dict:
    """Measure current activity against the pair's own recent baseline.

    Ratios rather than absolute volume, because absolute volume only tells you
    that BTC is bigger than a small-cap. What matters for a catalyst is a pair
    being unusually active *for itself*.
    """
    if len(candles) < baseline + recent:
        return {"volume_ratio": 1.0, "range_expansion": 1.0, "is_anomalous": False}

    recent_bars = candles[-recent:]
    baseline_bars = candles[-(baseline + recent) : -recent]

    recent_vol = sum(c.volume for c in recent_bars) / recent
    baseline_vol = sum(c.volume for c in baseline_bars) / baseline
    volume_ratio = recent_vol / baseline_vol if baseline_vol > 0 else 1.0

    recent_range = sum(c.high - c.low for c in recent_bars) / recent
    baseline_range = sum(c.high - c.low for c in baseline_bars) / baseline
    range_expansion = recent_range / baseline_range if baseline_range > 0 else 1.0

    return {
        "volume_ratio": round(volume_ratio, 2),
        "range_expansion": round(range_expansion, 2),
        # Volume alone can spike on a single print. Requiring range expansion
        # too filters out one-off blocks that move no price.
        "is_anomalous": volume_ratio >= 2.0 and range_expansion >= 1.3,
    }


@dataclass
class MarketContext:
    """A cached news brief. Refreshed on a slow cadence, reused between."""

    brief: str = ""
    fetched_at: float = 0.0
    error: str = ""

    def is_stale(self, max_age_seconds: int) -> bool:
        return (time.time() - self.fetched_at) > max_age_seconds

    def age_minutes(self) -> float:
        return (time.time() - self.fetched_at) / 60 if self.fetched_at else 0.0


class CatalystScanner:
    """Fetches the news brief via Claude with web search.

    Runs far less often than the trading loop. A 15m decision cadence does not
    need 15m news — the brief is background, and refetching it every bar would
    multiply cost for information that changes on the scale of hours.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-opus-5",
        refresh_seconds: int = 3600,
        max_searches: int = 6,
    ):
        # Same timeout rationale as the decision provider: a hung news fetch
        # must not consume the trading window. News is optional context.
        self._client = anthropic.Anthropic(api_key=api_key, timeout=300.0)
        self._model = model
        self.refresh_seconds = refresh_seconds
        self._max_searches = max_searches
        self.context = MarketContext()

    def refresh_if_stale(self, focus_symbols: list[str] | None = None) -> MarketContext:
        if not self.context.is_stale(self.refresh_seconds):
            return self.context

        focus = ""
        if focus_symbols:
            focus = (
                "\n\nPay particular attention to these, which are showing "
                f"unusual volume right now: {', '.join(focus_symbols)}. "
                "If you can find a specific reason for the activity, say what it "
                "is. If you cannot find one, say so explicitly — unexplained "
                "volume is itself worth flagging."
            )

        try:
            conversation: list[dict] = [
                {
                    "role": "user",
                    "content": (
                        "Give me the current crypto market brief for "
                        "automated spot trading." + focus
                    ),
                }
            ]

            # Web search runs a server-side loop that can stop with
            # stop_reason == "pause_turn" mid-way. Re-sending the conversation
            # with the assistant turn appended resumes it; without this loop a
            # paused turn would silently return a half-finished brief.
            response = None
            for _ in range(4):
                response = self._client.messages.create(
                    model=self._model,
                    # Thinking is on by default on Claude Opus 5 and shares
                    # max_tokens with the searches' synthesis; 8000 gives a
                    # sub-250-word brief plenty of headroom.
                    max_tokens=8000,
                    system=NEWS_SYSTEM_PROMPT,
                    tools=[
                        {
                            "type": "web_search_20260209",
                            "name": "web_search",
                            "max_uses": self._max_searches,
                        }
                    ],
                    messages=conversation,
                )
                if response.stop_reason != "pause_turn":
                    break
                conversation = conversation + [
                    {"role": "assistant", "content": response.content}
                ]

            if response is None or response.stop_reason == "refusal":
                self.context = MarketContext(
                    brief="", fetched_at=time.time(), error="model declined"
                )
                return self.context

            text = "\n".join(b.text for b in response.content if b.type == "text").strip()
            self.context = MarketContext(brief=text, fetched_at=time.time())
            print(f"[catalyst] refreshed news brief ({len(text)} chars)")

        except Exception as exc:  # noqa: BLE001 - news is optional context
            # A failed news fetch must never stop trading. The bot falls back to
            # pure price action, which is what it would do without this module.
            print(f"[catalyst] news fetch failed, continuing without it: {exc}")
            self.context = MarketContext(
                brief=self.context.brief,  # keep the previous brief if we had one
                fetched_at=time.time(),
                error=str(exc),
            )

        return self.context


def anomalous_symbols(snapshots: list[dict], limit: int = 5) -> list[str]:
    """Symbols worth asking the news layer about, most unusual first."""
    flagged = [
        (s["symbol"], s.get("volume_ratio", 1.0))
        for s in snapshots
        if s.get("is_anomalous")
    ]
    flagged.sort(key=lambda item: item[1], reverse=True)
    return [symbol for symbol, _ in flagged[:limit]]
