"""Append-only JSONL journal and persisted bot state.

Every decision is logged whether or not it was acted on, including the ones the
risk gate rejected. Rejections are the most useful record you have: they tell
you whether the model is generating sane ideas that the limits are filtering,
or nonsense that the limits are saving you from.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from risk import DayState, PaperAccount, Position


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Journal:
    def __init__(self, path: str):
        self.path = path

    def write(self, event: str, payload: dict[str, Any]) -> None:
        record = {"ts": _now(), "event": event, **payload}
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")

    def decision(
        self,
        decision: dict,
        verdict_reason: str,
        approved: bool,
        usage: dict,
        equity: float,
    ) -> None:
        self.write(
            "decision",
            {
                "approved": approved,
                "verdict": verdict_reason,
                "equity": round(equity, 2),
                "action": decision.get("action"),
                "symbol": decision.get("symbol"),
                "side": decision.get("side"),
                "entry": decision.get("entry"),
                "stop": decision.get("stop"),
                "target": decision.get("target"),
                "confidence": decision.get("confidence"),
                "reasoning": decision.get("reasoning"),
                "rejected": decision.get("rejected"),
                "usage": usage,
            },
        )

    def fill(self, side: str, symbol: str, order: dict, dry_run: bool) -> None:
        self.write("fill", {"side": side, "symbol": symbol, "dry_run": dry_run, "order": order})

    def error(self, where: str, message: str) -> None:
        self.write("error", {"where": where, "message": message})


class StateStore:
    """Persists open positions and the day's PnL across restarts.

    Without this, a restart forgets the daily loss cap and the kill switch
    resets itself — which is exactly when you least want it to.
    """

    def __init__(self, path: str):
        self.path = path

    def load(
        self, paper_default: PaperAccount | None = None
    ) -> tuple[dict[str, Position], DayState, PaperAccount]:
        paper_default = paper_default or PaperAccount()

        if not os.path.exists(self.path):
            return {}, DayState(), paper_default

        try:
            with open(self.path, encoding="utf-8") as fh:
                raw = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[state] could not read {self.path} ({exc}); starting clean")
            return {}, DayState(), paper_default

        positions = {
            sym: Position(**data) for sym, data in raw.get("positions", {}).items()
        }
        day = DayState(**raw.get("day", {}))
        day.roll_if_new_day()

        # Preserve accumulated paper PnL across restarts, but honour a changed
        # PAPER_EQUITY — otherwise raising the simulated balance in .env would
        # silently do nothing.
        stored = raw.get("paper")
        if stored:
            paper = PaperAccount(
                starting_equity=paper_default.starting_equity,
                realised_total=stored.get("realised_total", 0.0),
            )
        else:
            paper = paper_default

        return positions, day, paper

    def save(
        self,
        positions: dict[str, Position],
        day: DayState,
        paper: PaperAccount | None = None,
    ) -> None:
        payload = {
            "positions": {sym: asdict(pos) for sym, pos in positions.items()},
            "day": asdict(day),
            "paper": asdict(paper) if paper else None,
            "saved_at": _now(),
        }
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        os.replace(tmp, self.path)  # atomic — a crash mid-write cannot corrupt state
