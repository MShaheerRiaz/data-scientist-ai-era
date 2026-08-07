"""Two-way Telegram: ask the running bot what it is doing.

The notifier pushes events at you. This pulls: you send a command from your
phone and the bot answers from its live state and its journal. That means you
can see the approach — what it decided and why, what it rejected, what it has
learned — without SSHing into the VPS.

Every command is read-only except /pause and /resume, and even those cannot
open a position or move money: pause only stops NEW entries. Open positions
keep their stops and targets while paused, because abandoning risk management
on a running position is never the safe interpretation of "pause".

Commands are only accepted from the configured chat id (enforced in
notify.poll_commands), and every reply is best-effort — a Telegram failure is
logged and ignored, never propagated into the trading loop.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

HELP = """Commands:
/status — mode, equity, open positions, paused?
/positions — open positions with live P&L
/why — the last decision and its reasoning
/rejected — recent ideas the risk gate blocked
/journal — the last few journal events
/pnl — realised P&L, trade count, win rate
/lessons — what the bot has learned so far
/pause — stop opening NEW positions (stops still enforced)
/resume — resume normal trading
/help — this message"""


@dataclass
class Controls:
    """Runtime switches a human can flip from Telegram.

    Deliberately tiny and separate from Config: Config is the immutable set of
    settings the process started with, this is the mutable set a human changes
    while it runs.
    """

    paused: bool = False


def _tail_events(path: str, limit: int, event: str | None = None) -> list[dict]:
    """Read the last `limit` journal records, optionally filtered by event type.

    Reads only the tail of the file. The journal is append-only and grows
    forever, so loading all of it to answer /status would get slower every day
    the bot runs.
    """
    if not os.path.exists(path):
        return []
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            window = min(size, 256_000)
            fh.seek(size - window)
            chunk = fh.read().decode("utf-8", errors="ignore")
    except OSError as exc:
        print(f"[control] could not read journal: {exc}")
        return []

    lines = chunk.splitlines()
    if window < size and lines:
        lines = lines[1:]  # first line is probably a partial record

    records = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event and record.get("event") != event:
            continue
        records.append(record)

    return records[-limit:]


def _short_time(ts: str) -> str:
    """2026-08-07T14:32:11+00:00 -> 08-07 14:32"""
    return ts[5:16].replace("T", " ") if len(ts) >= 16 else ts


class CommandHandler:
    """Turns a Telegram command into a reply, from live state and the journal.

    Holds references — not copies — of the loop's positions/day/paper objects,
    so every answer reflects the bot's state at the moment you ask.
    """

    def __init__(self, cfg, positions, day, paper, book, controls, equity_fn, price_fn):
        self.cfg = cfg
        self.positions = positions
        self.day = day
        self.paper = paper
        self.book = book
        self.controls = controls
        self._equity = equity_fn
        self._price = price_fn

    # --- individual commands ---------------------------------------------

    def status(self) -> str:
        mode = "PAPER" if self.cfg.dry_run else "LIVE"
        try:
            equity = self._equity()
        except Exception as exc:  # noqa: BLE001 - a status query must not crash
            return f"Could not read equity: {exc}"

        state = "PAUSED (no new entries)" if self.controls.paused else "running"
        if self.day.halted:
            state = f"HALTED — {self.day.halt_reason}"

        lines = [
            f"{mode} · {self.cfg.interval} candles · {state}",
            f"Equity {equity:,.2f} {self.cfg.quote_asset}",
            f"Day P&L {self.day.realised_pnl:+,.2f}",
            f"Open positions {len(self.positions)}/{self.cfg.risk.max_concurrent_positions}",
            f"Lessons learned {len(self.book.lessons)}",
        ]
        if self.cfg.symbol_allowlist:
            lines.append(f"Pinned to {', '.join(self.cfg.symbol_allowlist)}")
        if self.cfg.dry_run:
            lines.append(
                f"Paper: started {self.paper.starting_equity:,.0f}, "
                f"realised {self.paper.realised_total:+,.2f}"
            )
        return "\n".join(lines)

    def positions_report(self) -> str:
        if not self.positions:
            return "No open positions."

        blocks = []
        for pos in self.positions.values():
            try:
                price = self._price(pos.symbol)
                unrealised = (price - pos.entry) * pos.quantity
                # R measures progress in units of the risk taken: +1R means the
                # trade has made exactly what it was risking.
                risk_per_unit = pos.entry - pos.stop
                r = (price - pos.entry) / risk_per_unit if risk_per_unit else 0.0
                live = f"now {price:g}  {unrealised:+.2f} ({r:+.2f}R)"
            except Exception:  # noqa: BLE001 - a price failure must not break the reply
                live = "price unavailable"
            blocks.append(
                f"{pos.symbol}\n"
                f"  entry {pos.entry:g}  stop {pos.stop:g}  target {pos.target:g}\n"
                f"  qty {pos.quantity:g}  {live}"
            )
        return "\n".join(blocks)

    def why(self) -> str:
        """The last decision the model made, and its stated reasoning."""
        events = _tail_events(self.cfg.journal_path, 1, event="decision")
        if not events:
            return "No decisions journalled yet."

        d = events[-1]
        head = f"{_short_time(d.get('ts', ''))} · {d.get('action')} {d.get('symbol') or ''}".strip()
        lines = [head]
        if d.get("action") == "open":
            lines.append(
                f"entry {d.get('entry')}  stop {d.get('stop')}  target {d.get('target')}"
            )
        lines.append(f"confidence {d.get('confidence')}")
        lines.append(f"gate: {'APPROVED' if d.get('approved') else 'rejected'} — {d.get('verdict')}")
        if d.get("reasoning"):
            lines.append(f"\n{d['reasoning']}")
        if d.get("rejected"):
            lines.append(f"\nAlso looked at and passed on: {', '.join(d['rejected'])}")
        return "\n".join(lines)

    def rejected(self, limit: int = 8) -> str:
        """Ideas the risk gate blocked — the most informative record there is.

        It tells you whether the model is producing sane ideas the limits are
        trimming, or nonsense the limits are catching.
        """
        events = [
            e for e in _tail_events(self.cfg.journal_path, 200, event="decision")
            if not e.get("approved") and e.get("action") == "open"
        ]
        if not events:
            return "No rejected entries recently."
        lines = [
            f"{_short_time(e.get('ts', ''))} {e.get('symbol')}: {e.get('verdict')}"
            for e in events[-limit:]
        ]
        return "Recently blocked:\n" + "\n".join(lines)

    def journal_tail(self, limit: int = 12) -> str:
        events = _tail_events(self.cfg.journal_path, limit)
        if not events:
            return "Journal is empty."

        lines = []
        for e in events:
            ts, kind = _short_time(e.get("ts", "")), e.get("event")
            if kind == "decision":
                mark = "✓" if e.get("approved") else "✗"
                lines.append(
                    f"{ts} {mark} {e.get('action')} {e.get('symbol') or '-'} — {e.get('verdict')}"
                )
            elif kind == "fill":
                pnl = (e.get("order") or {}).get("pnl")
                tail = f" pnl {pnl:+.2f}" if isinstance(pnl, (int, float)) else ""
                lines.append(f"{ts} · fill {e.get('side')} {e.get('symbol')}{tail}")
            elif kind == "review":
                lines.append(
                    f"{ts} · review {e.get('symbol')}: process={e.get('process_quality')}"
                )
            elif kind == "skip":
                lines.append(f"{ts} · skipped {e.get('symbol')} — {e.get('reason')}")
            elif kind == "error":
                lines.append(f"{ts} · ERROR in {e.get('where')}: {e.get('message')}")
            else:
                lines.append(f"{ts} · {kind}")
        return "\n".join(lines)

    def pnl(self) -> str:
        fills = [
            e for e in _tail_events(self.cfg.journal_path, 1000, event="fill")
            if isinstance((e.get("order") or {}).get("pnl"), (int, float))
        ]
        if not fills:
            return (
                f"No closed trades yet.\n"
                f"Day P&L {self.day.realised_pnl:+,.2f}"
            )

        pnls = [e["order"]["pnl"] for e in fills]
        wins = [p for p in pnls if p > 0]
        total = sum(pnls)
        win_rate = len(wins) / len(pnls)

        lines = [
            f"Closed trades {len(pnls)}",
            f"Win rate {win_rate:.0%}",
            f"Total realised {total:+,.2f} {self.cfg.quote_asset}",
            f"Day P&L {self.day.realised_pnl:+,.2f}",
        ]
        # Below ~50 trades the numbers above are mostly noise; say so rather
        # than letting a 3-trade winning streak look like an edge.
        if len(pnls) < 50:
            lines.append(
                f"\n⚠️ {len(pnls)} trades is too few to mean anything — "
                f"treat this as a plumbing check, not a verdict on the edge."
            )
        return "\n".join(lines)

    def lessons(self) -> str:
        if not self.book.lessons:
            return "No lessons recorded yet."
        lines = []
        for lesson in self.book.lessons:
            seen = f" (×{lesson.occurrences})" if lesson.occurrences > 1 else ""
            lines.append(f"• {lesson.text}{seen}")
        return f"{len(self.book.lessons)} lesson(s):\n" + "\n".join(lines)

    def pause(self) -> str:
        if self.controls.paused:
            return "Already paused."
        self.controls.paused = True
        return (
            "⏸ Paused. No new positions will be opened.\n"
            "Open positions keep their stops and targets — pausing does not "
            "abandon risk management. /resume to restart."
        )

    def resume(self) -> str:
        if not self.controls.paused:
            return "Not paused."
        self.controls.paused = False
        return "▶️ Resumed. New entries allowed again."

    # --- dispatch ---------------------------------------------------------

    def handle(self, text: str) -> str:
        """Map one incoming message to a reply. Never raises."""
        # Telegram sends "/status@mybotname" in groups; strip the suffix.
        command = text.strip().split()[0].lower().split("@")[0]
        handlers = {
            "/status": self.status,
            "/positions": self.positions_report,
            "/why": self.why,
            "/rejected": self.rejected,
            "/journal": self.journal_tail,
            "/pnl": self.pnl,
            "/lessons": self.lessons,
            "/pause": self.pause,
            "/resume": self.resume,
            "/help": lambda: HELP,
            "/start": lambda: "Connected.\n\n" + HELP,
        }
        handler = handlers.get(command)
        if not handler:
            return f"Unknown command {command!r}.\n\n{HELP}"
        try:
            return handler()
        except Exception as exc:  # noqa: BLE001 - a bad reply must not kill the loop
            return f"Command failed: {exc}"

    def poll_and_reply(self, notifier) -> int:
        """Fetch pending commands and answer them. Returns how many handled."""
        handled = 0
        for text in notifier.poll_commands():
            print(f"[control] command: {text}")
            notifier.send(self.handle(text))
            handled += 1
        return handled
