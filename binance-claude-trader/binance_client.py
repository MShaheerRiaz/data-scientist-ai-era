"""Minimal Binance **spot** REST client.

Hand-rolled rather than pulled from a library so every request that can move
money is readable in one file. Spot only — there is no code path here that can
open a futures position or touch leverage.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from typing import Any
from urllib.parse import urlencode

import requests


class BinanceError(RuntimeError):
    """Raised for any non-2xx response. Carries the parsed body when present."""

    def __init__(self, status: int, payload: Any):
        self.status = status
        self.payload = payload
        code = payload.get("code") if isinstance(payload, dict) else None
        msg = payload.get("msg") if isinstance(payload, dict) else payload
        super().__init__(f"binance http {status} code={code}: {msg}")


@dataclass(frozen=True)
class Candle:
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int

    @classmethod
    def from_row(cls, row: list) -> "Candle":
        return cls(
            open_time=int(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
            close_time=int(row[6]),
        )


@dataclass(frozen=True)
class SymbolFilters:
    """Exchange-imposed rounding rules. Orders that violate these are rejected."""

    symbol: str
    tick_size: Decimal      # price increment
    step_size: Decimal      # quantity increment
    min_qty: Decimal
    min_notional: Decimal
    base_asset: str
    quote_asset: str

    def round_price(self, price: float) -> Decimal:
        return (Decimal(str(price)) / self.tick_size).quantize(
            Decimal("1"), rounding=ROUND_DOWN
        ) * self.tick_size

    def round_qty(self, qty: float) -> Decimal:
        return (Decimal(str(qty)) / self.step_size).quantize(
            Decimal("1"), rounding=ROUND_DOWN
        ) * self.step_size


class BinanceSpot:
    def __init__(self, key: str, secret: str, base_url: str, timeout: int = 15):
        self.key = key
        self.secret = secret.encode()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"X-MBX-APIKEY": key})
        self._filters: dict[str, SymbolFilters] = {}

    # ---- transport -------------------------------------------------------

    def _request(
        self, method: str, path: str, params: dict | None = None, *, signed: bool = False
    ) -> Any:
        params = dict(params or {})
        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["recvWindow"] = 5000
            query = urlencode(params)
            params["signature"] = hmac.new(
                self.secret, query.encode(), hashlib.sha256
            ).hexdigest()

        response = self._session.request(
            method, f"{self.base_url}{path}", params=params, timeout=self.timeout
        )
        try:
            payload = response.json()
        except ValueError:
            payload = response.text

        if not response.ok:
            raise BinanceError(response.status_code, payload)
        return payload

    # ---- public data -----------------------------------------------------

    def ping(self) -> None:
        self._request("GET", "/api/v3/ping")

    def exchange_info(self) -> dict:
        return self._request("GET", "/api/v3/exchangeInfo")

    def ticker_24h(self) -> list[dict]:
        return self._request("GET", "/api/v3/ticker/24hr")

    def klines(self, symbol: str, interval: str, limit: int = 120) -> list[Candle]:
        rows = self._request(
            "GET",
            "/api/v3/klines",
            {"symbol": symbol, "interval": interval, "limit": limit},
        )
        # The final row is the still-forming candle. Drop it: acting on an
        # unclosed bar means reacting to a high/low that can still change.
        return [Candle.from_row(r) for r in rows[:-1]]

    def price(self, symbol: str) -> float:
        return float(self._request("GET", "/api/v3/ticker/price", {"symbol": symbol})["price"])

    # ---- filters ---------------------------------------------------------

    def load_filters(self) -> dict[str, SymbolFilters]:
        """Cache per-symbol tick/step/notional rules from exchangeInfo."""
        info = self.exchange_info()
        filters: dict[str, SymbolFilters] = {}

        for sym in info.get("symbols", []):
            if sym.get("status") != "TRADING" or not sym.get("isSpotTradingAllowed"):
                continue

            by_type = {f["filterType"]: f for f in sym.get("filters", [])}
            price_f = by_type.get("PRICE_FILTER")
            lot_f = by_type.get("LOT_SIZE")
            # Binance uses either NOTIONAL or the older MIN_NOTIONAL depending
            # on the symbol and on testnet vs production.
            notional_f = by_type.get("NOTIONAL") or by_type.get("MIN_NOTIONAL")
            if not price_f or not lot_f:
                continue

            min_notional = Decimal("0")
            if notional_f:
                min_notional = Decimal(
                    notional_f.get("minNotional") or notional_f.get("notional") or "0"
                )

            filters[sym["symbol"]] = SymbolFilters(
                symbol=sym["symbol"],
                tick_size=Decimal(price_f["tickSize"]),
                step_size=Decimal(lot_f["stepSize"]),
                min_qty=Decimal(lot_f["minQty"]),
                min_notional=min_notional,
                base_asset=sym["baseAsset"],
                quote_asset=sym["quoteAsset"],
            )

        self._filters = filters
        return filters

    def filters_for(self, symbol: str) -> SymbolFilters:
        if not self._filters:
            self.load_filters()
        if symbol not in self._filters:
            raise BinanceError(400, {"msg": f"{symbol} is not a tradable spot symbol"})
        return self._filters[symbol]

    # ---- account ---------------------------------------------------------

    def account(self) -> dict:
        return self._request("GET", "/api/v3/account", signed=True)

    def balances(self) -> dict[str, float]:
        """Non-zero balances as {asset: free + locked}."""
        out: dict[str, float] = {}
        for bal in self.account().get("balances", []):
            total = float(bal["free"]) + float(bal["locked"])
            if total > 0:
                out[bal["asset"]] = total
        return out

    def free_balance(self, asset: str) -> float:
        for bal in self.account().get("balances", []):
            if bal["asset"] == asset:
                return float(bal["free"])
        return 0.0

    def equity_in_quote(self, quote_asset: str = "USDT") -> float:
        """Total account value expressed in the quote asset.

        Prices every non-quote balance through its {asset}{quote} spot pair.
        Assets with no such pair are skipped rather than guessed at.
        """
        balances = self.balances()
        equity = balances.get(quote_asset, 0.0)
        if not self._filters:
            self.load_filters()

        for asset, amount in balances.items():
            if asset == quote_asset:
                continue
            pair = f"{asset}{quote_asset}"
            if pair not in self._filters:
                continue
            try:
                equity += amount * self.price(pair)
            except BinanceError:
                continue
        return equity

    # ---- orders ----------------------------------------------------------

    def market_buy(self, symbol: str, quote_amount: float) -> dict:
        """Spend a fixed amount of quote currency at market.

        quoteOrderQty lets Binance size the base quantity, which sidesteps
        step-size rounding on entry.
        """
        f = self.filters_for(symbol)
        if f.min_notional and Decimal(str(quote_amount)) < f.min_notional:
            raise BinanceError(
                400,
                {"msg": f"{quote_amount} {f.quote_asset} below minNotional {f.min_notional}"},
            )
        return self._request(
            "POST",
            "/api/v3/order",
            {
                "symbol": symbol,
                "side": "BUY",
                "type": "MARKET",
                "quoteOrderQty": f"{quote_amount:.8f}".rstrip("0").rstrip("."),
            },
            signed=True,
        )

    def market_sell(self, symbol: str, quantity: float) -> dict:
        f = self.filters_for(symbol)
        qty = f.round_qty(quantity)
        if qty < f.min_qty:
            raise BinanceError(400, {"msg": f"qty {qty} below minQty {f.min_qty}"})
        return self._request(
            "POST",
            "/api/v3/order",
            {"symbol": symbol, "side": "SELL", "type": "MARKET", "quantity": str(qty)},
            signed=True,
        )

    def open_orders(self, symbol: str | None = None) -> list[dict]:
        params = {"symbol": symbol} if symbol else {}
        return self._request("GET", "/api/v3/openOrders", params, signed=True)

    def cancel_all(self, symbol: str) -> Any:
        try:
            return self._request(
                "DELETE", "/api/v3/openOrders", {"symbol": symbol}, signed=True
            )
        except BinanceError as exc:
            # -2011 is "no orders to cancel" — not an error for our purposes.
            if isinstance(exc.payload, dict) and exc.payload.get("code") == -2011:
                return []
            raise
