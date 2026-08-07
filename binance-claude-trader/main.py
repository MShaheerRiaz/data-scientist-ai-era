"""Main loop.

One cycle per closed candle:

    exits -> universe -> snapshots -> Claude decides -> risk gate -> execute

The model chooses the symbol, the direction and whether to act at all. The risk
gate decides whether that choice is permitted and how large it may be. Those
two responsibilities never mix.
"""

from __future__ import annotations

import signal
import sys
import time
from datetime import datetime, timezone

from binance_client import BinanceError, BinanceSpot
from catalyst import CatalystScanner, anomalous_symbols
from config import Config
from decision import DECISION_SCHEMA, SYSTEM_PROMPT, build_payload
from executor import Executor
from journal import Journal, StateStore
from llm.anthropic_provider import AnthropicProvider
from lessons import REVIEW_SCHEMA, REVIEW_SYSTEM_PROMPT, LessonBook, build_review_payload
from llm.base import ProviderRefusal
from notify import notifier_from_config
from telegram_control import CommandHandler, Controls
from risk import PaperAccount, RiskGate
from universe import build_snapshots, select_universe

# Seconds a 15m/1h/etc. bar lasts, used to sleep until just after the next close.
_INTERVAL_SECONDS = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400, "1d": 86400,
}

_running = True


def _handle_signal(signum, _frame):
    global _running
    print(f"\n[main] signal {signum} received — finishing cycle and shutting down.")
    _running = False


def seconds_to_next_close(interval: str, buffer: int = 5) -> float:
    """Sleep until just after the next bar closes, so klines returns a fresh bar."""
    period = _INTERVAL_SECONDS.get(interval, 900)
    now = time.time()
    return (period - (now % period)) + buffer


def current_equity(
    cfg: Config,
    client: BinanceSpot,
    positions: dict,
    paper: PaperAccount,
) -> float:
    """Account equity in the quote asset, real or simulated.

    Paper mode must not read the real balance. A fresh or empty account reports
    near zero, every position sizes to zero, and the bot runs cleanly while
    never taking a trade — a silent no-op that looks like "no setups found".
    """
    if not cfg.dry_run:
        return client.equity_in_quote(cfg.quote_asset)

    prices: dict[str, float] = {}
    for symbol in positions:
        try:
            prices[symbol] = client.price(symbol)
        except BinanceError:
            # Fall back to entry, so a quote failure understates rather than
            # inflates equity.
            prices[symbol] = positions[symbol].entry
    return paper.equity(positions, prices)


def review_closed_trade(
    cfg: Config,
    provider: AnthropicProvider,
    book: LessonBook,
    journal: Journal,
    position,
    exit_reason: str,
    pnl: float,
    exit_price: float,
) -> None:
    """Critique one closed trade and keep the lesson, if there is one.

    Failures here are swallowed: a review that errors must never affect
    trading. The lesson is a nice-to-have, the position management is not.
    """
    if not cfg.enable_review:
        return

    payload = build_review_payload(
        position_symbol=position.symbol,
        entry=position.entry,
        stop=position.stop,
        target=position.target,
        exit_price=exit_price,
        exit_reason=exit_reason,
        pnl=pnl,
        opened_at=position.opened_at,
        original_reasoning=position.reasoning,
        entry_snapshot=position.entry_snapshot,
    )

    try:
        review, usage = provider.review(REVIEW_SYSTEM_PROMPT, payload, REVIEW_SCHEMA)
    except Exception as exc:  # noqa: BLE001 - review must never break trading
        journal.error("review", str(exc))
        print(f"[review] failed, continuing: {exc}")
        return

    journal.write(
        "review",
        {
            "symbol": position.symbol,
            "process_quality": review.get("process_quality"),
            "outcome": review.get("outcome"),
            "should_record": review.get("should_record"),
            "lesson": review.get("lesson"),
            "analysis": review.get("analysis"),
            "usage": usage,
        },
    )

    quality = review.get("process_quality")
    print(f"[review] {position.symbol}: process={quality} outcome={review.get('outcome')}")
    if review.get("analysis"):
        print(f"         {review['analysis']}")

    if review.get("should_record") and review.get("lesson"):
        is_new = book.record(
            text=review["lesson"],
            tags=review.get("tags", []),
            example=f"{position.symbol} {exit_reason} pnl={pnl:.2f}",
        )
        verb = "new lesson" if is_new else "reinforced lesson"
        print(f"         {verb}: {review['lesson']}")


def manage_exits(
    cfg: Config,
    provider: AnthropicProvider,
    executor: Executor,
    journal: Journal,
    store: StateStore,
    positions: dict,
    day,
    paper,
    book: LessonBook,
    notifier=None,
) -> int:
    """Honour stops and targets on open positions. Returns how many closed.

    Called at the top of every decision cycle AND every POLL_SECONDS while the
    loop sleeps between candles. That second call site is the point: it
    decouples the *thinking* timeframe from the *protection* timeframe, so a
    stop is acted on within ~30 seconds of being hit even when decisions are
    made on 1h candles.
    """
    closed = executor.check_exits(positions)
    for position, reason, pnl in closed:
        day.realised_pnl += pnl
        paper.realised_total += pnl
        print(f"[main] closed {position.symbol} on {reason}, day pnl {day.realised_pnl:.2f}")
        if notifier:
            emoji = "✅" if pnl >= 0 else "❌"
            notifier.send(
                f"{emoji} Closed {position.symbol} on {reason}\n"
                f"P&L {pnl:+.2f} — day {day.realised_pnl:+.2f}"
            )
        exit_price = position.stop if reason == "stop" else position.target
        review_closed_trade(
            cfg, provider, book, journal, position, reason, pnl, exit_price
        )
    if closed:
        store.save(positions, day, paper)
    return len(closed)


def run_cycle(
    cfg: Config,
    client: BinanceSpot,
    provider: AnthropicProvider,
    gate: RiskGate,
    executor: Executor,
    journal: Journal,
    store: StateStore,
    positions: dict,
    day,
    paper,
    book: LessonBook,
    scanner,
    notifier=None,
    controls=None,
) -> None:
    # 1. Honour stops and targets before considering anything new.
    manage_exits(
        cfg, provider, executor, journal, store, positions, day, paper, book,
        notifier=notifier,
    )
    store.save(positions, day, paper)

    # 2. Equity drives both sizing and the kill switch. In paper mode this must
    #    come from the simulated balance — reading the real account would size
    #    every position against a balance the run is not actually trading.
    equity = current_equity(cfg, client, positions, paper)

    # Notify only on the transition into halted, not every cycle it stays so.
    was_halted = day.halted
    kill = gate.check_kill_switch(day, equity)
    if not kill.approved:
        print(f"[main] {kill.reason} — no new positions this cycle.")
        if notifier and not was_halted:
            notifier.send(f"⛔ {kill.reason}\nNo new positions until the UTC day rolls.")
        store.save(positions, day, paper)
        return

    # Paused from Telegram: exits were already managed above, so open risk is
    # still supervised — only new entries stop. Checked before the universe
    # scan so a paused bot costs nothing in API calls either.
    if controls is not None and controls.paused:
        print("[main] paused — no new positions this cycle.")
        return

    # 3. Candidate set. The model picks from these; it cannot invent a symbol
    #    outside the tradable set (the risk gate rejects anything unknown).
    candidates = select_universe(client, cfg)
    if not candidates:
        print("[main] no candidates passed the liquidity filter.")
        return

    snapshots = build_snapshots(client, cfg, candidates)
    if not snapshots:
        print("[main] no usable snapshots this cycle.")
        return

    # Volume anomalies point the news scan at what is actually moving, rather
    # than asking for generic headlines.
    snapshot_dicts = [s.to_dict() for s in snapshots]
    context_brief, context_age = "", 0.0
    if scanner is not None:
        ctx = scanner.refresh_if_stale(anomalous_symbols(snapshot_dicts))
        context_brief, context_age = ctx.brief, ctx.age_minutes()

    payload = build_payload(
        snapshots=snapshot_dicts,
        open_positions=[
            {
                "symbol": p.symbol,
                "entry": p.entry,
                "stop": p.stop,
                "target": p.target,
                "quantity": p.quantity,
            }
            for p in positions.values()
        ],
        account_equity_quote=equity,
        interval=cfg.interval,
        market_context=context_brief,
        context_age_minutes=context_age,
        lessons=book.as_prompt_block(),
    )

    # 4. Decide.
    try:
        decision, usage = provider.decide(SYSTEM_PROMPT, payload, DECISION_SCHEMA)
    except ProviderRefusal as exc:
        # A refusal is a no-trade, not a crash.
        journal.error("decide", str(exc))
        print(f"[main] model declined: {exc}")
        return
    except Exception as exc:  # noqa: BLE001 - network/API errors must not kill the loop
        journal.error("decide", str(exc))
        print(f"[main] decision failed: {exc}")
        return

    cached = usage.get("cache_read_input_tokens", 0)
    print(
        f"[main] decision={decision['action']} {decision.get('symbol') or '-'} "
        f"conf={decision.get('confidence')} "
        f"(in={usage.get('input_tokens')} cached={cached} out={usage.get('output_tokens')})"
    )
    if decision.get("reasoning"):
        print(f"       {decision['reasoning']}")

    action = decision.get("action")

    if action == "none":
        journal.decision(decision, "model chose no trade", False, usage, equity)
        return

    if action == "close":
        symbol = (decision.get("symbol") or "").upper()
        position = positions.get(symbol)
        if not position:
            journal.decision(decision, f"no open position in {symbol}", False, usage, equity)
            return
        try:
            pnl = executor.close(position, "model_close")
        except BinanceError:
            return
        day.realised_pnl += pnl
        paper.realised_total += pnl
        positions.pop(symbol, None)
        if notifier:
            emoji = "✅" if pnl >= 0 else "❌"
            notifier.send(
                f"{emoji} Closed {symbol} on model instruction\n"
                f"P&L {pnl:+.2f} — day {day.realised_pnl:+.2f}"
            )
        review_closed_trade(
            cfg, provider, book, journal, position, "model_close", pnl,
            client.price(symbol),
        )
        journal.decision(decision, "closed on model instruction", True, usage, equity)
        store.save(positions, day, paper)
        return

    # action == "open"
    # The allowlist is enforced here too, not just in candidate selection —
    # the model could name any symbol, and "only trade what I pinned" must
    # hold even against that.
    allowed = client.tradable()
    if cfg.symbol_allowlist:
        allowed &= set(cfg.symbol_allowlist)
    verdict = gate.evaluate(
        decision=decision,
        equity=equity,
        positions=positions,
        day=day,
        denylist=cfg.symbol_denylist,
        tradable_symbols=allowed,
    )
    journal.decision(decision, verdict.reason, verdict.approved, usage, equity)

    if not verdict.approved:
        print(f"[main] rejected by risk gate: {verdict.reason}")
        return

    print(
        f"[main] approved: {verdict.quote_amount:.2f} {cfg.quote_asset} "
        f"risking {verdict.risk_amount:.2f} at R:R {verdict.reward_risk:.2f}"
    )

    position = executor.open_long(decision, verdict)
    if position:
        if notifier:
            notifier.send(
                f"🟢 Opened {position.symbol} long\n"
                f"entry {position.entry:g}  stop {position.stop:g}  "
                f"target {position.target:g}\n"
                f"size {verdict.quote_amount:.2f} {cfg.quote_asset}, "
                f"risking {verdict.risk_amount:.2f}"
            )
        position.reasoning = decision.get("reasoning", "")
        position.entry_snapshot = next(
            (s for s in snapshot_dicts if s["symbol"] == position.symbol), {}
        )
        positions[position.symbol] = position
        store.save(positions, day, paper)


def main() -> int:
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    cfg = Config.from_env()
    client = BinanceSpot(cfg.binance_key, cfg.binance_secret, cfg.base_url)
    journal = Journal(cfg.journal_path)
    store = StateStore(cfg.state_path)
    provider = AnthropicProvider(cfg.anthropic_key, cfg.model, cfg.effort)
    gate = RiskGate(cfg.risk)
    executor = Executor(client, journal, cfg.dry_run)
    book = LessonBook(cfg.lessons_path, cfg.max_lessons)
    scanner = (
        CatalystScanner(cfg.anthropic_key, cfg.model, cfg.news_refresh_seconds)
        if cfg.enable_news
        else None
    )
    notifier = notifier_from_config(cfg)
    controls = Controls()

    try:
        client.ping()
        client.load_filters()
    except BinanceError as exc:
        print(f"[main] cannot reach Binance: {exc}")
        return 1

    positions, day, paper = store.load(PaperAccount(starting_equity=cfg.paper_equity))

    # Answers Telegram queries from live state. It holds references to the very
    # same positions/day/paper objects the loop mutates in place, so a /status
    # sent mid-cycle reports what is true right now, not a snapshot.
    commands = (
        CommandHandler(
            cfg,
            positions=positions,
            day=day,
            paper=paper,
            book=book,
            controls=controls,
            equity_fn=lambda: current_equity(cfg, client, positions, paper),
            price_fn=client.price,
        )
        if notifier
        else None
    )

    mode = "TESTNET" if cfg.testnet else "LIVE"
    order_mode = "DRY-RUN (no orders sent)" if cfg.dry_run else "ORDERS ARMED"
    print(f"[main] {mode} / {order_mode} / {cfg.model} / {cfg.interval}")
    print(f"[main] resumed with {len(positions)} open position(s), day pnl {day.realised_pnl:.2f}")
    if cfg.dry_run:
        print(
            f"[main] paper balance {paper.starting_equity + paper.realised_total:,.2f} "
            f"{cfg.quote_asset} (started {paper.starting_equity:,.2f}, "
            f"realised {paper.realised_total:+,.2f})"
        )

    if book.lessons:
        print(f"[main] carrying {len(book.lessons)} lesson(s) from past trades")
    print(
        f"[main] review={'on' if cfg.enable_review else 'off'} "
        f"news={'on' if cfg.enable_news else 'off'} "
        f"telegram={'on' if notifier else 'off'}"
    )
    if notifier:
        notifier.send(
            f"🤖 Bot started — {mode} / {order_mode}\n"
            f"{cfg.interval} candles, {len(positions)} open position(s)\n"
            f"Send /help to see what you can ask me."
        )

    journal.write("start", {"mode": mode, "dry_run": cfg.dry_run, "model": cfg.model})

    while _running:
        cycle_start = datetime.now(timezone.utc).isoformat()
        print(f"\n--- cycle {cycle_start} ---")
        try:
            run_cycle(
                cfg, client, provider, gate, executor, journal, store,
                positions, day, paper, book, scanner, notifier=notifier,
                controls=controls,
            )
        except Exception as exc:  # noqa: BLE001 - a bad cycle must not end the run
            journal.error("cycle", str(exc))
            print(f"[main] cycle error: {exc}")

        if not _running:
            break

        sleep_for = seconds_to_next_close(cfg.interval)
        print(f"[main] sleeping {sleep_for:.0f}s until next {cfg.interval} close")
        # Wake every POLL_SECONDS: to honour a shutdown signal promptly, and —
        # when positions are open — to enforce stops and targets between
        # candles. Without this, a stop hit one minute into an hourly bar
        # would not be acted on for another 59 minutes.
        slept = 0.0
        while slept < sleep_for and _running:
            chunk = min(cfg.poll_seconds, sleep_for - slept)
            time.sleep(chunk)
            slept += chunk
            if positions and _running:
                try:
                    manage_exits(
                        cfg, provider, executor, journal, store,
                        positions, day, paper, book, notifier=notifier,
                    )
                except Exception as exc:  # noqa: BLE001 - watcher must not kill the loop
                    journal.error("exit_watch", str(exc))
            # Telegram commands are answered on the same clock, so /status
            # replies within ~POLL_SECONDS even while waiting on an hourly bar.
            if commands and _running:
                try:
                    commands.poll_and_reply(notifier)
                except Exception as exc:  # noqa: BLE001 - chat must not kill the loop
                    journal.error("telegram_poll", str(exc))

    journal.write("stop", {"open_positions": len(positions)})
    store.save(positions, day, paper)

    if positions:
        print(
            f"[main] WARNING: exiting with {len(positions)} open position(s). "
            "Stops are enforced by this process — they are NOT resting on the "
            "exchange. Close them manually or restart the bot."
        )
        if notifier:
            notifier.send(
                f"⚠️ Bot stopped with {len(positions)} open position(s): "
                f"{', '.join(positions)}. Stops are NOT enforced while it is down "
                f"— restart it or close them manually."
            )
    print("[main] stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
