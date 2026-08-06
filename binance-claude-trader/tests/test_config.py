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


def _load_without(*missing: str, **extra_env) -> Config:
    """Load config with specific env vars removed."""
    saved = dict(os.environ)
    try:
        for var in RISK_ENV_VARS + ["BINANCE_TESTNET", "DRY_RUN"]:
            os.environ.pop(var, None)
        os.environ.update(REQUIRED_ENV)
        os.environ.update({k: str(v) for k, v in extra_env.items()})
        for var in missing:
            os.environ.pop(var, None)
        return Config.from_env()
    finally:
        os.environ.clear()
        os.environ.update(saved)


def test_anthropic_key_is_always_required():
    """No decision model means no bot, in any mode."""
    try:
        _load_without("ANTHROPIC_API_KEY")
    except RuntimeError as exc:
        assert "ANTHROPIC_API_KEY" in str(exc)
    else:
        raise AssertionError("missing Anthropic key must raise")


def test_binance_keys_are_required_only_for_live_trading():
    """Paper mode uses public endpoints only, so it needs no account."""
    cfg = _load_without("BINANCE_API_KEY", "BINANCE_API_SECRET", DRY_RUN="true")
    assert cfg.binance_key == ""
    assert cfg.dry_run is True

    try:
        _load_without("BINANCE_API_KEY", "BINANCE_API_SECRET", DRY_RUN="false")
    except RuntimeError as exc:
        assert "BINANCE_API_KEY" in str(exc)
    else:
        raise AssertionError("arming orders without Binance keys must raise")


def test_paper_equity_defaults_and_overrides():
    assert _load_without().paper_equity == 10_000.0
    assert _load_without(PAPER_EQUITY=25_000).paper_equity == 25_000.0


def test_dotenv_file_is_loaded():
    """The documented flow is `cp .env.example .env; python main.py` — this
    pins that the file is actually read, which it silently was not before."""
    import tempfile

    saved_cwd = os.getcwd()
    saved_env = dict(os.environ)
    with tempfile.TemporaryDirectory() as tmp:
        try:
            os.chdir(tmp)
            with open(".env", "w") as fh:
                fh.write("# comment line\n")
                fh.write("RISK_PER_TRADE=0.007\n")
                fh.write('CLAUDE_EFFORT="high"\n')
            for var in RISK_ENV_VARS + ["CLAUDE_EFFORT", "BINANCE_TESTNET", "DRY_RUN"]:
                os.environ.pop(var, None)
            os.environ.update(REQUIRED_ENV)
            cfg = Config.from_env()
            assert cfg.risk.risk_per_trade == 0.007
            assert cfg.effort == "high"  # quotes stripped
        finally:
            os.chdir(saved_cwd)
            os.environ.clear()
            os.environ.update(saved_env)


def test_dotenv_does_not_override_real_environment():
    import tempfile

    saved_cwd = os.getcwd()
    saved_env = dict(os.environ)
    with tempfile.TemporaryDirectory() as tmp:
        try:
            os.chdir(tmp)
            with open(".env", "w") as fh:
                fh.write("RISK_PER_TRADE=0.007\n")
            for var in RISK_ENV_VARS + ["BINANCE_TESTNET", "DRY_RUN"]:
                os.environ.pop(var, None)
            os.environ.update(REQUIRED_ENV)
            os.environ["RISK_PER_TRADE"] = "0.003"  # shell wins over file
            cfg = Config.from_env()
            assert cfg.risk.risk_per_trade == 0.003
        finally:
            os.chdir(saved_cwd)
            os.environ.clear()
            os.environ.update(saved_env)


def test_invalid_interval_falls_back_to_15m():
    """A bad interval would 400 on every klines call while the scheduler
    silently slept a default period — fail soft with a warning instead."""
    cfg = load(CANDLE_INTERVAL="45m")
    assert cfg.interval == "15m"


def test_invalid_effort_falls_back_to_medium():
    cfg = load(CLAUDE_EFFORT="turbo")
    assert cfg.effort == "medium"


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
