"""Order placement and position management.

Two responsibilities: turn an approved decision into a spot order, and watch
open positions so stops and targets are honoured.

Stops are enforced *by this process*, not resting on the exchange. That is a
deliberate tradeoff: a resting OCO order survives the bot dying, but Binance
spot OCO interacts awkwardly with the quoteOrderQty entry sizing used here.
The consequence is real and you should know it — if this process is not
running, your stops are not active. Do not leave positions open with the bot
stopped.
"""

from __future__ import annotations

from datetime import datetime, timezone

from binance_client import BinanceError, BinanceSpot
from journal import Journal
from risk import Position, Verdict


class Executor:
    def __init__(self, client: BinanceSpot, journal: Journal, dry_run: bool):
        self.client = client
        self.journal = journal
        self.dry_run = dry_run

    def open_long(self, decision: dict, verdict: Verdict) -> Position | None:
        symbol = decision["symbol"].upper()
        quote_amount = verdict.quote_amount

        # Entry drift guard. The model priced this decision off the last closed
        # candle; by the time we act, the market may have moved. Two failure
        # modes are caught here:
        #   1. Price already at/through the stop or target — the trade is
        #      instantly dead or already done; buying now is pure slippage.
        #   2. Price drifted far from the intended entry — position size was
        #      computed against the decision's stop distance, so a large drift
        #      silently changes the risk actually taken.
        entry = float(decision["entry"])
        stop = float(decision["stop"])
        target = float(decision["target"])
        try:
            price = self.client.price(symbol)
        except BinanceError as exc:
            self.journal.error("open_long", f"no price for {symbol}: {exc}")
            return None

        if price <= stop or price >= target:
            self.journal.write(
                "skip",
                {"symbol": symbol, "reason": "price_beyond_levels",
                 "price": price, "entry": entry, "stop": stop, "target": target},
            )
            print(f"[executor] skip {symbol}: price {price} already beyond stop/target")
            return None

        stop_distance = entry - stop
        if abs(price - entry) > 0.5 * stop_distance:
            self.journal.write(
                "skip",
                {"symbol": symbol, "reason": "entry_drift",
                 "price": price, "entry": entry,
                 "drift_pct": round(abs(price - entry) / entry * 100, 3)},
            )
            print(
                f"[executor] skip {symbol}: price {price} drifted more than half "
                f"the stop distance from intended entry {entry}"
            )
            return None

        if self.dry_run:
            qty = quote_amount / price
            self.journal.fill(
                "buy",
                symbol,
                {"simulated": True, "quote_amount": quote_amount, "price": price, "qty": qty},
                dry_run=True,
            )
            print(f"[dry-run] BUY {symbol} {quote_amount:.2f} quote @ ~{price}")
            return Position(
                symbol=symbol,
                quantity=qty,
                entry=price,
                stop=float(decision["stop"]),
                target=float(decision["target"]),
                opened_at=datetime.now(timezone.utc).isoformat(),
            )

        try:
            order = self.client.market_buy(symbol, quote_amount)
        except BinanceError as exc:
            self.journal.error("open_long", str(exc))
            print(f"[executor] buy rejected: {exc}")
            return None

        filled_qty = float(order.get("executedQty", 0))
        if filled_qty <= 0:
            self.journal.error("open_long", f"zero fill on {symbol}")
            return None

        # Use the actual weighted fill price, not the model's intended entry —
        # slippage on a market order can be material on thinner pairs, and the
        # stop must be measured from where we actually got in.
        spent = float(order.get("cummulativeQuoteQty", 0))
        avg_price = spent / filled_qty if filled_qty else 0.0

        self.journal.fill("buy", symbol, order, dry_run=False)
        print(f"[executor] BUY {symbol} qty={filled_qty} avg={avg_price}")

        return Position(
            symbol=symbol,
            quantity=filled_qty,
            entry=avg_price,
            stop=float(decision["stop"]),
            target=float(decision["target"]),
            opened_at=datetime.now(timezone.utc).isoformat(),
        )

    def close(self, position: Position, reason: str) -> float:
        """Flatten a position at market. Returns realised PnL in quote currency."""
        price = self.client.price(position.symbol)
        pnl = position.unrealised(price)

        if self.dry_run:
            self.journal.fill(
                "sell",
                position.symbol,
                {"simulated": True, "qty": position.quantity, "price": price,
                 "pnl": pnl, "reason": reason},
                dry_run=True,
            )
            print(f"[dry-run] SELL {position.symbol} ({reason}) pnl={pnl:.2f}")
            return pnl

        try:
            # Sell the free balance rather than the recorded quantity — fees are
            # taken in the base asset on some pairs, so the recorded quantity can
            # exceed what is actually sellable and the order would bounce.
            filters = self.client.filters_for(position.symbol)
            free = self.client.free_balance(filters.base_asset)
            qty = min(position.quantity, free)
            order = self.client.market_sell(position.symbol, qty)
        except BinanceError as exc:
            self.journal.error("close", str(exc))
            print(f"[executor] sell rejected: {exc}")
            raise

        received = float(order.get("cummulativeQuoteQty", 0))
        sold_qty = float(order.get("executedQty", 0))
        pnl = received - (position.entry * sold_qty)

        self.journal.fill(
            "sell", position.symbol, {**order, "pnl": pnl, "reason": reason}, dry_run=False
        )
        print(f"[executor] SELL {position.symbol} ({reason}) pnl={pnl:.2f}")
        return pnl

    def check_exits(self, positions: dict[str, Position]) -> list[tuple[Position, str, float]]:
        """Close any position that has reached its stop or target.

        Returns the closures as (position, reason, pnl) so the caller can update
        the daily PnL and persist state.
        """
        closed: list[tuple[Position, str, float]] = []

        for symbol, position in list(positions.items()):
            try:
                price = self.client.price(symbol)
            except BinanceError as exc:
                self.journal.error("check_exits", f"{symbol}: {exc}")
                continue

            reason = ""
            if price <= position.stop:
                reason = "stop"
            elif price >= position.target:
                reason = "target"

            if not reason:
                continue

            try:
                pnl = self.close(position, reason)
            except BinanceError:
                # Leave the position in state so the next cycle retries the exit
                # rather than losing track of an open holding.
                continue

            closed.append((position, reason, pnl))
            positions.pop(symbol, None)

        return closed
