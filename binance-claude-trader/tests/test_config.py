"""Config tests.

These exist because of a bug that the risk tests could not see: the risk limit
defaults were declared twice — once on the dataclass, once as literals inside
`Config.from_env()`. The tests constructed `RiskLimits()` directly and passed,
while the running bot loaded the other set of numbers. Tests that only exercise
the dataclass cannot catch that, so these go through `from_env` instead.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Config, RiskLimits  # noqa: E402

REQUIRED_ENV = {
    "BINANCE_API_KEY": "test-key",
    "BINANCE_API_SECRET": "test-secret",
    "ANTHROPIC_API_KEY": "test-anthropic",
}

RISK_ENV_VARS = [
    "RISK_PER_TRADE",
    "MAX_POSITION_PCT",
    "MAX_DAILY_LOSS_PCT",
    "MAX_CONCURRENT_POSITIONS",
    "MIN_REWARD_RISK",
    "MAX_STOP_DISTANCE_PCT",
    "MIN_CONFIDENCE",
]


def load(**extra_env) -> Config:
    """Load config with a clean environment plus any overrides."""
    saved = dict(os.environ)
    try:
        for var in RISK_ENV_VARS + ["BINANCE_TESTNET", "DRY_RUN"]:
            os.environ.pop(var, None)
        os.environ.update(REQUIRED_ENV)
        os.environ.update({k: str(v) for k, v in extra_env.items()})
        return Config.from_env()
    finally:
        os.environ.clear()
        os.environ.update(saved)


def test_runtime_defaults_match_dataclass_defaults():
    """The bug this file exists for: one source of truth for every default."""
    runtime = load().risk
    declared = RiskLimits()
    for field in RISK_ENV_VARS:
        attr = field.lower()
        assert getattr(runtime, attr) == getattr(declared, attr), (
            f"{attr}: from_env gave {getattr(runtime, attr)}, "
            f"dataclass declares {getattr(declared, attr)} — defaults have drifted apart"
        )


def test_env_overrides_are_applied_with_correct_types():
    cfg = load(RISK_PER_TRADE=0.008, MAX_CONCURRENT_POSITIONS=6)
    assert cfg.risk.risk_per_trade == 0.008
    assert cfg.risk.max_concurrent_positions == 6
    # `from __future__ import annotations` makes dataclass field types strings,
    # which previously coerced every int field to float.
    assert isinstance(cfg.risk.max_concurrent_positions, int)
    assert isinstance(cfg.risk.risk_per_trade, float)


def test_unset_env_vars_do_not_override():
    cfg = load(RISK_PER_TRADE=0.008)
    assert cfg.risk.risk_per_trade == 0.008
    assert cfg.risk.max_position_pct == RiskLimits().max_position_pct


def test_sizing_settings_are_coherent_by_default():
    """Notional cap must not bind on ordinary ATR stops (2-4%)."""
    r = load().risk
    binds_below = r.risk_per_trade / r.max_position_pct
    assert binds_below <= 0.02, (
        f"cap binds on stops tighter than {binds_below:.1%}, inside the normal "
        f"ATR range — risk_per_trade would stop being the active constraint"
    )


def test_full_book_fits_in_equity_by_default():
    r = load().risk
    assert r.max_position_pct * r.max_concurrent_positions <= 1.0


def test_safe_defaults_when_nothing_is_configured():
    """Absent explicit opt-out, the bot must not touch real money."""
    cfg = load()
    assert cfg.testnet is True
    assert cfg.dry_run is True
    assert "testnet" in cfg.base_url


def test_live_host_selected_only_when_explicitly_disabled():
    cfg = load(BINANCE_TESTNET="false")
    assert cfg.testnet is False
    assert cfg.base_url == "https://api.binance.com"
    # DRY_RUN is independent — live host alone must not arm orders.
    assert cfg.dry_run is True


def test_missing_credentials_raise():
    saved = dict(os.environ)
    try:
        for var in REQUIRED_ENV:
            os.environ.pop(var, None)
        try:
            Config.from_env()
        except RuntimeError as exc:
            assert "BINANCE_API_KEY" in str(exc)
        else:
            raise AssertionError("missing credentials must raise")
    finally:
        os.environ.clear()
        os.environ.update(saved)


def test_stablecoin_pairs_are_denylisted():
    cfg = load()
    for pair in ("USDCUSDT", "FDUSDUSDT", "TUSDUSDT"):
        assert pair in cfg.symbol_denylist


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
