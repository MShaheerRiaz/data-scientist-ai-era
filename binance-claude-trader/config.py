"""Configuration loaded from environment. Fail loudly on anything unsafe."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(f"{name} is not set. Copy .env.example to .env and fill it in.")
    return value or ""


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return default if raw in (None, "") else float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return default if raw in (None, "") else int(raw)


def _env_overrides(cls, mapping: dict[str, str]) -> dict:
    """Collect only the fields whose env var is actually set.

    Returning a sparse dict lets the dataclass supply every unset default, so
    defaults live in exactly one place. Repeating them as literals here is how
    the tests and the running bot end up disagreeing about the risk limits.
    """
    # `from __future__ import annotations` makes f.type a *string* ("int"),
    # never the type object — so compare against both forms.
    fields = {f.name: f.type for f in cls.__dataclass_fields__.values()}
    out: dict = {}
    for field_name, env_name in mapping.items():
        raw = os.environ.get(env_name)
        if raw in (None, ""):
            continue
        declared = fields[field_name]
        is_int = declared is int or declared == "int"
        out[field_name] = int(raw) if is_int else float(raw)
    return out


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# Binance spot REST hosts. Testnet has a separate key pair from production —
# keys are not interchangeable and a production key sent to testnet just 401s.
BINANCE_HOSTS = {
    True: "https://testnet.binance.vision",
    False: "https://api.binance.com",
}


@dataclass(frozen=True)
class RiskLimits:
    """Hard caps enforced in code. The model cannot widen these."""

    # Fraction of account equity risked on a single position, assuming the
    # trade goes to its stop. 0.005 == 0.5%.
    #
    # Deliberately half the conventional 1%. These three settings are coupled:
    # notional = risk_per_trade / stop_distance, so a 1% risk against a 2% ATR
    # stop demands 50% of equity in one position, and three of those exceed the
    # account. At 0.5% the same stop needs 25%, which fits inside
    # max_position_pct with room for a full book. Raise this only if you also
    # raise max_position_pct and lower max_concurrent_positions to match.
    risk_per_trade: float = 0.005
    # Ceiling on notional per position as a fraction of equity, regardless of
    # how tight the stop is. This is a backstop against a pathologically tight
    # stop demanding an enormous position — not the routine constraint.
    #
    # It binds whenever stop_distance < risk_per_trade / max_position_pct.
    # At the defaults that is a stop tighter than 1/30 == 3.3%, which normal
    # ATR-based stops clear. Set it too low (e.g. 0.20, binding below 5%) and
    # it silently overrides risk_per_trade on nearly every trade, making that
    # setting meaningless. Keep max_position_pct * max_concurrent_positions
    # at or under 1.0 so a full book cannot exceed equity.
    max_position_pct: float = 0.30
    # Cumulative realised + unrealised loss for the day that triggers the kill
    # switch. Once tripped, the bot flattens and refuses to open anything new.
    max_daily_loss_pct: float = 0.03
    max_concurrent_positions: int = 3
    # Reject a decision whose stop implies worse than this reward:risk.
    min_reward_risk: float = 1.2
    # Reject a decision whose stop is further than this from entry — usually a
    # sign the model misread the price scale.
    max_stop_distance_pct: float = 0.08
    # Ignore anything the model is not reasonably sure about.
    min_confidence: float = 0.6


@dataclass(frozen=True)
class Config:
    binance_key: str
    binance_secret: str
    testnet: bool
    anthropic_key: str

    model: str = "claude-opus-5"
    effort: str = "medium"
    # 15m bars. The loop wakes shortly after each close.
    interval: str = "15m"
    candles_per_symbol: int = 120
    # How many of the highest-volume USDT pairs to hand the model.
    universe_size: int = 12
    # Liquidity floor, in 24h quote volume (USDT). Filters out pairs where a
    # market order would move the book.
    min_quote_volume: float = 20_000_000.0
    quote_asset: str = "USDT"
    # Pairs never to trade regardless of what the model says. Leveraged tokens
    # and stablecoin-to-stablecoin pairs belong here.
    symbol_denylist: tuple[str, ...] = (
        "USDCUSDT",
        "FDUSDUSDT",
        "TUSDUSDT",
        "BUSDUSDT",
        "EURUSDT",
        "GBPUSDT",
    )

    dry_run: bool = True
    poll_seconds: int = 30
    journal_path: str = "journal.jsonl"
    state_path: str = "state.json"

    risk: RiskLimits = field(default_factory=RiskLimits)

    @property
    def base_url(self) -> str:
        return BINANCE_HOSTS[self.testnet]

    @classmethod
    def from_env(cls) -> "Config":
        testnet = _env_bool("BINANCE_TESTNET", True)
        dry_run = _env_bool("DRY_RUN", True)

        cfg = cls(
            binance_key=_env("BINANCE_API_KEY", required=True),
            binance_secret=_env("BINANCE_API_SECRET", required=True),
            testnet=testnet,
            anthropic_key=_env("ANTHROPIC_API_KEY", required=True),
            model=_env("CLAUDE_MODEL", "claude-opus-5"),
            effort=_env("CLAUDE_EFFORT", "medium"),
            interval=_env("CANDLE_INTERVAL", "15m"),
            candles_per_symbol=_env_int("CANDLES_PER_SYMBOL", 120),
            universe_size=_env_int("UNIVERSE_SIZE", 12),
            min_quote_volume=_env_float("MIN_QUOTE_VOLUME", 20_000_000.0),
            dry_run=dry_run,
            poll_seconds=_env_int("POLL_SECONDS", 30),
            journal_path=_env("JOURNAL_PATH", "journal.jsonl"),
            state_path=_env("STATE_PATH", "state.json"),
            # Only env vars that are actually set are passed through; every
            # default comes from RiskLimits itself.
            risk=RiskLimits(
                **_env_overrides(
                    RiskLimits,
                    {
                        "risk_per_trade": "RISK_PER_TRADE",
                        "max_position_pct": "MAX_POSITION_PCT",
                        "max_daily_loss_pct": "MAX_DAILY_LOSS_PCT",
                        "max_concurrent_positions": "MAX_CONCURRENT_POSITIONS",
                        "min_reward_risk": "MIN_REWARD_RISK",
                        "max_stop_distance_pct": "MAX_STOP_DISTANCE_PCT",
                        "min_confidence": "MIN_CONFIDENCE",
                    },
                )
            ),
        )

        # The three sizing settings are coupled. Warn loudly rather than
        # discovering at 3am that the notional cap has been quietly overriding
        # the risk budget on every trade.
        binds_below = cfg.risk.risk_per_trade / cfg.risk.max_position_pct
        if binds_below > 0.03:
            print(
                f"[config] WARNING: notional cap binds on any stop tighter than "
                f"{binds_below:.1%}. Typical ATR stops are 2-4%, so risk_per_trade "
                f"({cfg.risk.risk_per_trade:.3%}) will rarely be the active "
                f"constraint. Lower RISK_PER_TRADE or raise MAX_POSITION_PCT."
            )
        book = cfg.risk.max_position_pct * cfg.risk.max_concurrent_positions
        if book > 1.0:
            print(
                f"[config] WARNING: a full book would need {book:.0%} of equity; "
                f"spot cannot borrow, so later entries will fail on insufficient funds."
            )

        if not cfg.testnet and cfg.dry_run:
            print("[config] live host selected but DRY_RUN=true — no orders will be sent.")
        if not cfg.testnet and not cfg.dry_run:
            print("[config] LIVE TRADING ARMED against api.binance.com with real funds.")

        return cfg
