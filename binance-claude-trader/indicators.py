"""Indicators and structure detection, in pure Python.

No pandas/numpy on purpose: every number the model sees should be traceable to
a few lines you can read, and this file has no version-drift surface.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from binance_client import Candle


def ema(values: list[float], period: int) -> list[float]:
    """Exponential moving average, seeded with an SMA of the first `period`."""
    if len(values) < period:
        return []
    k = 2.0 / (period + 1)
    seed = sum(values[:period]) / period
    out = [seed]
    for v in values[period:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def rsi(closes: list[float], period: int = 14) -> list[float]:
    """Wilder's RSI."""
    if len(closes) <= period:
        return []
    gains, losses = [], []
    for prev, cur in zip(closes, closes[1:]):
        delta = cur - prev
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    out = []
    for g, l in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period
        if avg_loss == 0:
            out.append(100.0)
        else:
            rs = avg_gain / avg_loss
            out.append(100.0 - 100.0 / (1 + rs))
    return out


def atr(candles: list[Candle], period: int = 14) -> list[float]:
    """Average true range, Wilder-smoothed. The volatility unit for stops."""
    if len(candles) <= period:
        return []
    trs = []
    for prev, cur in zip(candles, candles[1:]):
        trs.append(
            max(
                cur.high - cur.low,
                abs(cur.high - prev.close),
                abs(cur.low - prev.close),
            )
        )
    smoothed = sum(trs[:period]) / period
    out = [smoothed]
    for tr in trs[period:]:
        smoothed = (smoothed * (period - 1) + tr) / period
        out.append(smoothed)
    return out


def swing_points(
    candles: list[Candle], lookback: int = 3
) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Fractal swing highs and lows.

    A swing high is a bar whose high exceeds the `lookback` bars either side.
    Returns (highs, lows) as lists of (index, price).
    """
    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []
    for i in range(lookback, len(candles) - lookback):
        window = candles[i - lookback : i + lookback + 1]
        if candles[i].high == max(c.high for c in window):
            highs.append((i, candles[i].high))
        if candles[i].low == min(c.low for c in window):
            lows.append((i, candles[i].low))
    return highs, lows


def equal_levels(
    points: list[tuple[int, float]], tolerance_pct: float = 0.0015
) -> list[float]:
    """Cluster swing points that sit within `tolerance_pct` of each other.

    Two or more swings at the same price are where stop orders pile up — the
    liquidity pools that price tends to reach for.
    """
    if not points:
        return []
    prices = sorted(p for _, p in points)
    clusters: list[list[float]] = [[prices[0]]]
    for price in prices[1:]:
        if abs(price - clusters[-1][-1]) / clusters[-1][-1] <= tolerance_pct:
            clusters[-1].append(price)
        else:
            clusters.append([price])
    return [sum(c) / len(c) for c in clusters if len(c) >= 2]


def _slope_direction(points: list[tuple[int, float]], count: int = 3) -> str:
    """Classify the last `count` swings as rising / falling / mixed."""
    if len(points) < count:
        return "insufficient"
    recent = [p for _, p in points[-count:]]
    if all(b > a for a, b in zip(recent, recent[1:])):
        return "rising"
    if all(b < a for a, b in zip(recent, recent[1:])):
        return "falling"
    return "mixed"


@dataclass
class Snapshot:
    """Compact per-symbol market state. This is what the model actually reads.

    Deliberately small — a 120-candle OHLCV dump per symbol across a dozen
    symbols would be tens of thousands of tokens per decision and would bury
    the signal.
    """

    symbol: str
    last_price: float
    change_pct_24h: float
    quote_volume_24h: float

    ema_fast: float
    ema_slow: float
    ema_trend: str          # "bullish" | "bearish"
    rsi_14: float
    atr_14: float
    atr_pct: float          # ATR as % of price — the volatility unit

    range_high: float
    range_low: float
    position_in_range: float  # 0.0 at range low, 1.0 at range high

    # Activity relative to this pair's own baseline. Ratios, not absolutes:
    # what matters is a pair being unusually busy for itself, not that BTC
    # trades more than a small-cap.
    volume_ratio: float       # recent avg volume / baseline avg volume
    range_expansion: float    # recent avg bar range / baseline
    is_anomalous: bool        # both elevated together — a real activity spike

    swing_high_structure: str  # rising | falling | mixed
    swing_low_structure: str
    equal_highs: list[float]
    equal_lows: list[float]

    recent_closes: list[float]  # last 12 closes, for shape

    def to_dict(self) -> dict:
        return asdict(self)


def build_snapshot(
    symbol: str, candles: list[Candle], change_pct_24h: float, quote_volume_24h: float
) -> Snapshot | None:
    """Reduce a candle series to the fields above. None if there isn't enough data."""
    if len(candles) < 60:
        return None

    closes = [c.close for c in candles]
    last = closes[-1]

    ema_fast_series = ema(closes, 21)
    ema_slow_series = ema(closes, 55)
    rsi_series = rsi(closes, 14)
    atr_series = atr(candles, 14)
    if not (ema_fast_series and ema_slow_series and rsi_series and atr_series):
        return None

    ema_fast, ema_slow = ema_fast_series[-1], ema_slow_series[-1]
    atr_14 = atr_series[-1]

    window = candles[-60:]
    range_high = max(c.high for c in window)
    range_low = min(c.low for c in window)
    span = range_high - range_low
    position_in_range = (last - range_low) / span if span > 0 else 0.5

    highs, lows = swing_points(candles, lookback=3)

    # Imported here rather than at module scope: catalyst imports Candle from
    # binance_client, and a top-level import would make the dependency circular.
    from catalyst import volume_profile

    activity = volume_profile(candles)

    def _round(values: list[float]) -> list[float]:
        return [round(v, 8) for v in values[:4]]

    return Snapshot(
        symbol=symbol,
        last_price=last,
        change_pct_24h=round(change_pct_24h, 2),
        quote_volume_24h=round(quote_volume_24h, 0),
        ema_fast=round(ema_fast, 8),
        ema_slow=round(ema_slow, 8),
        ema_trend="bullish" if ema_fast > ema_slow else "bearish",
        rsi_14=round(rsi_series[-1], 1),
        atr_14=round(atr_14, 8),
        atr_pct=round(atr_14 / last * 100, 3) if last else 0.0,
        range_high=round(range_high, 8),
        range_low=round(range_low, 8),
        position_in_range=round(position_in_range, 3),
        volume_ratio=activity["volume_ratio"],
        range_expansion=activity["range_expansion"],
        is_anomalous=activity["is_anomalous"],
        swing_high_structure=_slope_direction(highs),
        swing_low_structure=_slope_direction(lows),
        equal_highs=_round(equal_levels(highs)),
        equal_lows=_round(equal_levels(lows)),
        recent_closes=[round(c, 8) for c in closes[-12:]],
    )
