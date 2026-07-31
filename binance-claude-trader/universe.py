"""Candidate selection.

The model picks what to trade, but only from pairs that are actually tradable:
liquid enough that a market order does not move the book, quoted in the right
asset, not denylisted, and not a leveraged token.
"""

from __future__ import annotations

from binance_client import BinanceSpot
from config import Config
from indicators import Snapshot, build_snapshot

# Binance leveraged tokens (BTCUP/BTCDOWN etc.) track a rebalancing index
# rather than spot and decay when held. Excluded regardless of volume.
_LEVERAGED_SUFFIXES = ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT")


def select_universe(client: BinanceSpot, cfg: Config) -> list[dict]:
    """Return the top candidates by 24h quote volume, after filters."""
    tickers = client.ticker_24h()
    tradable = client.load_filters()

    candidates = []
    for t in tickers:
        symbol = t["symbol"]
        if not symbol.endswith(cfg.quote_asset):
            continue
        if symbol in cfg.symbol_denylist:
            continue
        if symbol.endswith(_LEVERAGED_SUFFIXES):
            continue
        if symbol not in tradable:
            continue

        quote_volume = float(t.get("quoteVolume", 0))
        if quote_volume < cfg.min_quote_volume:
            continue

        candidates.append(
            {
                "symbol": symbol,
                "quote_volume": quote_volume,
                "change_pct": float(t.get("priceChangePercent", 0)),
            }
        )

    candidates.sort(key=lambda c: c["quote_volume"], reverse=True)
    return candidates[: cfg.universe_size]


def build_snapshots(
    client: BinanceSpot, cfg: Config, candidates: list[dict]
) -> list[Snapshot]:
    """Fetch candles and reduce each candidate to a Snapshot.

    A symbol that errors or has too little history is skipped rather than
    failing the whole cycle — one bad pair should not stop the loop.
    """
    snapshots: list[Snapshot] = []
    for c in candidates:
        try:
            candles = client.klines(c["symbol"], cfg.interval, cfg.candles_per_symbol)
        except Exception as exc:  # noqa: BLE001 - one bad symbol must not halt the cycle
            print(f"[universe] skipping {c['symbol']}: {exc}")
            continue

        snapshot = build_snapshot(
            symbol=c["symbol"],
            candles=candles,
            change_pct_24h=c["change_pct"],
            quote_volume_24h=c["quote_volume"],
        )
        if snapshot:
            snapshots.append(snapshot)

    return snapshots
