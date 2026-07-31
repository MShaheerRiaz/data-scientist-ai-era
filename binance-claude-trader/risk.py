"""The risk gate. Deterministic, code-enforced, not promptable.

Every decision from the model passes through `evaluate` before anything is
sent to the exchange. The model chooses what to trade; this file decides
whether that trade is allowed and how large it may be.

Nothing in the model's output can widen a limit here. `confidence` in
particular does not scale position size — otherwise the model would have an
incentive to inflate it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from config import RiskLimits


@dataclass
class Position:
    symbol: str
    quantity: float
    entry: float
    stop: float
    target: float
    opened_at: str

    def unrealised(self, price: float) -> float:
        return (price - self.entry) * self.quantity


@dataclass
class DayState:
    """Rolling per-UTC-day realised PnL and the kill-switch flag."""

    date: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    realised_pnl: float = 0.0
    halted: bool = False
    halt_reason: str = ""

    def roll_if_new_day(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self.date:
            self.date = today
            self.realised_pnl = 0.0
            self.halted = False
            self.halt_reason = ""


@dataclass
class Verdict:
    approved: bool
    reason: str
    quote_amount: float = 0.0
    risk_amount: float = 0.0
    reward_risk: float = 0.0


class RiskGate:
    def __init__(self, limits: RiskLimits):
        self.limits = limits

    def check_kill_switch(self, day: DayState, equity: float) -> Verdict:
        """Trip the halt if the day's realised loss breaches the cap.

        Checked before every decision, not just before opening — once tripped
        the bot stops opening anything until the UTC day rolls.
        """
        day.roll_if_new_day()
        if day.halted:
            return Verdict(False, f"halted: {day.halt_reason}")

        max_loss = equity * self.limits.max_daily_loss_pct
        if day.realised_pnl <= -max_loss:
            day.halted = True
            day.halt_reason = (
                f"daily loss {day.realised_pnl:.2f} breached cap {-max_loss:.2f}"
            )
            return Verdict(False, f"halted: {day.halt_reason}")

        return Verdict(True, "ok")

    def evaluate(
        self,
        decision: dict,
        equity: float,
        positions: dict[str, Position],
        day: DayState,
        denylist: tuple[str, ...],
        tradable_symbols: set[str],
    ) -> Verdict:
        """Approve or reject an 'open' decision, and size it if approved."""
        kill = self.check_kill_switch(day, equity)
        if not kill.approved:
            return kill

        symbol = (decision.get("symbol") or "").upper()
        side = decision.get("side")
        entry = float(decision.get("entry") or 0)
        stop = float(decision.get("stop") or 0)
        target = float(decision.get("target") or 0)
        confidence = float(decision.get("confidence") or 0)

        # --- eligibility -------------------------------------------------

        if side != "long":
            # Spot cannot short. The model is told this, but a schema-valid
            # "none" side reaching an open action still has to be caught.
            return Verdict(False, f"side {side!r} not tradable on spot")

        if symbol in denylist:
            return Verdict(False, f"{symbol} is denylisted")

        if symbol not in tradable_symbols:
            return Verdict(False, f"{symbol} is not a tradable spot symbol")

        if symbol in positions:
            return Verdict(False, f"already holding {symbol}")

        if len(positions) >= self.limits.max_concurrent_positions:
            return Verdict(
                False,
                f"at max concurrent positions ({self.limits.max_concurrent_positions})",
            )

        if confidence < self.limits.min_confidence:
            return Verdict(
                False, f"confidence {confidence:.2f} below {self.limits.min_confidence}"
            )

        # --- price sanity ------------------------------------------------

        if entry <= 0 or stop <= 0 or target <= 0:
            return Verdict(False, "entry, stop and target must all be positive")

        if stop >= entry:
            return Verdict(False, f"long stop {stop} must sit below entry {entry}")

        if target <= entry:
            return Verdict(False, f"long target {target} must sit above entry {entry}")

        stop_distance = entry - stop
        stop_pct = stop_distance / entry
        if stop_pct > self.limits.max_stop_distance_pct:
            return Verdict(
                False,
                f"stop {stop_pct:.1%} from entry exceeds cap "
                f"{self.limits.max_stop_distance_pct:.1%}",
            )
        if stop_pct < 0.0015:
            # Tighter than ~0.15% is inside the spread plus fees on most pairs.
            return Verdict(False, f"stop {stop_pct:.2%} from entry is implausibly tight")

        reward_risk = (target - entry) / stop_distance
        if reward_risk < self.limits.min_reward_risk:
            return Verdict(
                False,
                f"reward:risk {reward_risk:.2f} below {self.limits.min_reward_risk}",
            )

        # --- sizing ------------------------------------------------------

        # Risk a fixed fraction of equity assuming the trade reaches its stop.
        # Confidence deliberately plays no part here.
        risk_amount = equity * self.limits.risk_per_trade
        quote_amount = risk_amount / stop_pct

        # Independent notional ceiling. Without it, a very tight stop turns a
        # 1% risk budget into an oversized position.
        notional_cap = equity * self.limits.max_position_pct
        if quote_amount > notional_cap:
            quote_amount = notional_cap
            risk_amount = quote_amount * stop_pct

        if quote_amount <= 0:
            return Verdict(False, "computed position size is zero")

        return Verdict(
            approved=True,
            reason="approved",
            quote_amount=quote_amount,
            risk_amount=risk_amount,
            reward_risk=reward_risk,
        )
