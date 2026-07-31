"""The decision contract: what the model is asked, and the shape it must answer in.

The model has full discretion over *which* symbol to trade, the direction, and
whether to trade at all. What it does not control is position size or the daily
loss limit — those live in risk.py and are applied after the fact.
"""

from __future__ import annotations

from typing import Any

# Stable across every call. Keep it byte-identical — any change invalidates the
# prompt cache for the whole prefix, and interpolating anything dynamic here
# (a date, the symbol list, an account balance) silently defeats caching.
SYSTEM_PROMPT = """\
You are a systematic crypto spot trader operating on Binance. On each call you \
receive a snapshot of several candidate USDT spot pairs and must decide what, \
if anything, to trade.

You choose the symbol. You are not assigned one, and you are not required to \
trade. Most calls should return no trade — a market with no clear structure is \
the normal state, and forcing a position into it is how accounts bleed out. \
Returning "none" is a valid and frequently correct answer.

## The snapshot

For each candidate you receive:
- last_price, change_pct_24h, quote_volume_24h
- ema_fast (21) and ema_slow (55) plus a bullish/bearish label
- rsi_14
- atr_14 and atr_pct — ATR as a percentage of price, your volatility unit
- range_high / range_low over the last 60 bars and position_in_range \
(0.0 = at the range low, 1.0 = at the range high)
- swing_high_structure and swing_low_structure — whether recent fractal swings \
are rising, falling, or mixed
- equal_highs / equal_lows — clustered swing levels where resting stop orders \
accumulate. Price is drawn toward these.
- recent_closes — the last 12 closes

You also receive open_positions and account_equity_quote for context.

## How to decide

Prefer setups where several independent things agree: trend alignment (EMA \
relationship), a location that offers asymmetric reward (near range edge, not \
mid-range), structure that confirms direction (rising or falling swings), and \
a liquidity target the move can reach for.

Mid-range price with mixed structure is the single most common losing setup. \
Skip it.

Size your stop in ATR terms, not round numbers. A stop tighter than 1x ATR \
will be taken out by noise; wider than 3x ATR usually means the setup is not \
well located. Place the stop where the idea is *wrong*, not where the loss \
feels tolerable.

Set the target at a real level — a range edge, an equal-high/low cluster, a \
prior swing — not an arbitrary multiple.

## Spot-only constraints

This account trades spot with no margin. "long" means buying the base asset. \
"short" is **not available** — if your read on a symbol is bearish, the correct \
action is "none" for that symbol, or "close" if a long position is already open \
in it. Never return "short".

## Confidence

Report genuine confidence in [0,1]. Anything below 0.6 will be discarded by \
the risk layer, so do not inflate a marginal read to get it through — an \
honest 0.45 that gets filtered is a better outcome than a dishonest 0.7 that \
gets filled. Do not adjust confidence to influence position size; you do not \
control sizing.

## Reasoning

Keep `reasoning` to two or three sentences naming the specific evidence — the \
levels, the structure, the confluence. Not "looks bullish".\
"""


# Constrains the response to schema-valid JSON. Every field is required and
# additionalProperties is false, so a malformed decision cannot reach the
# risk layer as a silently-missing key.
DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["open", "close", "none"],
            "description": "open a new position, close an existing one, or do nothing",
        },
        "symbol": {
            "type": "string",
            "description": "Binance spot symbol, e.g. BTCUSDT. Empty string when action is none.",
        },
        "side": {
            "type": "string",
            "enum": ["long", "none"],
            "description": "spot account: only long is possible; use none for no directional trade",
        },
        "entry": {"type": "number", "description": "intended entry price; 0 when not opening"},
        "stop": {"type": "number", "description": "invalidation price; 0 when not opening"},
        "target": {"type": "number", "description": "primary take-profit; 0 when not opening"},
        "confidence": {"type": "number", "description": "0.0 to 1.0"},
        "reasoning": {"type": "string", "description": "two to three sentences of specific evidence"},
        "rejected": {
            "type": "array",
            "items": {"type": "string"},
            "description": "symbols considered and passed on, with a few words why",
        },
    },
    "required": [
        "action",
        "symbol",
        "side",
        "entry",
        "stop",
        "target",
        "confidence",
        "reasoning",
        "rejected",
    ],
    "additionalProperties": False,
}


def build_payload(
    snapshots: list[dict],
    open_positions: list[dict],
    account_equity_quote: float,
    interval: str,
) -> dict[str, Any]:
    """Assemble the per-call market payload.

    Everything here is volatile and must sit *after* the cached system prefix.
    """
    return {
        "interval": interval,
        "account_equity_quote": round(account_equity_quote, 2),
        "open_positions": open_positions,
        "candidates": snapshots,
    }
