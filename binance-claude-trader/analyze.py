"""Read journal.jsonl and report what the numbers actually say.

Run this after a paper-trading period. It answers the questions that decide
whether a strategy is worth real money, in the order they matter:

    1. Is there an edge at all?          (expectancy)
    2. Is the sample large enough to believe it?  (significance)
    3. If so, how much should be risked? (Kelly)
    4. What does that survive?           (risk of ruin)

Question 2 is the one people skip, and it is why most strategies are adopted
on evidence that cannot support the conclusion.

    python analyze.py [journal.jsonl]
"""

from __future__ import annotations

import json
import sys
from collections import Counter

from quant import (
    breakeven_win_rate,
    expectancy_r,
    kelly_fraction,
    kelly_fraction_fractional,
    risk_of_ruin,
    trades_needed_for_significance,
)


def load(path: str) -> list[dict]:
    records = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue  # skip a torn final line from a hard kill
    except FileNotFoundError:
        print(f"No journal at {path}. Run the bot first.")
        sys.exit(1)
    return records


def money(multiple: float) -> str:
    """Compact equity multiples. Kelly-scale compounding produces numbers with
    no intuitive meaning at full precision, and the point is the order of
    magnitude, not the digits."""
    if multiple >= 1e9:
        return f"{multiple:.1e}x"
    if multiple >= 1000:
        return f"{multiple:,.0f}x"
    return f"{multiple:.2f}x"


def section(title: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "journal.jsonl"
    records = load(path)

    decisions = [r for r in records if r.get("event") == "decision"]
    fills = [r for r in records if r.get("event") == "fill"]
    reviews = [r for r in records if r.get("event") == "review"]
    closes = [f for f in fills if f.get("side") == "sell" and "pnl" in f.get("order", {})]

    # --- activity ---------------------------------------------------------

    section("ACTIVITY")
    print(f"decisions      {len(decisions)}")
    approved = sum(1 for d in decisions if d.get("approved"))
    no_trade = sum(1 for d in decisions if d.get("action") == "none")
    print(f"  no-trade     {no_trade} ({no_trade / len(decisions):.0%})" if decisions else "")
    print(f"  approved     {approved}")
    print(f"  rejected     {len(decisions) - approved - no_trade}")
    print(f"closed trades  {len(closes)}")

    if decisions:
        rejections = Counter(
            d["verdict"].split(" (")[0]
            for d in decisions
            if not d.get("approved") and d.get("action") == "open"
        )
        if rejections:
            section("WHY THE RISK GATE REJECTED TRADES")
            for reason, count in rejections.most_common(8):
                print(f"  {count:>4}  {reason}")

    # --- token spend ------------------------------------------------------

    usages = [d["usage"] for d in decisions if d.get("usage")]
    if usages:
        section("API USAGE")
        total_in = sum(u.get("input_tokens", 0) for u in usages)
        total_cached = sum(u.get("cache_read_input_tokens", 0) for u in usages)
        total_out = sum(u.get("output_tokens", 0) for u in usages)
        print(f"input tokens   {total_in:,}")
        print(f"cache reads    {total_cached:,}")
        print(f"output tokens  {total_out:,}")
        if total_in + total_cached:
            hit_rate = total_cached / (total_in + total_cached)
            print(f"cache hit rate {hit_rate:.0%}")
            if hit_rate < 0.3 and len(usages) > 5:
                print("  WARNING: low cache hit rate. Something volatile is")
                print("  probably being interpolated into the system prompt.")

    if not closes:
        section("EDGE")
        print("No closed trades yet — nothing to measure.")
        print("Let it run. Edge cannot be assessed from open positions.")
        return 0

    # --- edge -------------------------------------------------------------

    pnls = [float(f["order"]["pnl"]) for f in closes]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    win_rate = len(wins) / len(pnls)
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0.0
    reward_risk = (avg_win / avg_loss) if avg_loss > 0 else 0.0

    section("EDGE")
    print(f"trades         {len(pnls)}")
    print(f"win rate       {win_rate:.1%}  ({len(wins)}W / {len(losses)}L)")
    print(f"avg win        {avg_win:+.2f}")
    print(f"avg loss       {-avg_loss:+.2f}")
    print(f"reward:risk    {reward_risk:.2f}")
    print(f"total pnl      {sum(pnls):+.2f}")

    by_symbol: dict[str, list[float]] = {}
    for f in closes:
        by_symbol.setdefault(f.get("symbol", "?"), []).append(float(f["order"]["pnl"]))
    if len(by_symbol) > 1:
        section("EDGE BY SYMBOL")
        print(f"{'symbol':<12} {'trades':>6} {'win rate':>9} {'total pnl':>11}")
        for sym, ps in sorted(by_symbol.items(), key=lambda kv: -sum(kv[1])):
            wins_s = sum(1 for p in ps if p > 0)
            print(f"{sym:<12} {len(ps):>6} {wins_s / len(ps):>8.0%} {sum(ps):>+11.2f}")
        print("\nThis answers the single-coin question empirically: if one symbol")
        print("carries the edge, pin SYMBOL_ALLOWLIST to it and rerun.")

    if reward_risk <= 0:
        print("\nNot enough of both outcomes yet to compute an edge.")
        return 0

    breakeven = breakeven_win_rate(reward_risk)
    edge = expectancy_r(win_rate, reward_risk)

    print(f"\nbreakeven win rate at this R:R   {breakeven:.1%}")
    print(f"actual win rate                  {win_rate:.1%}")
    print(f"expectancy                       {edge:+.3f}R per trade")

    if edge <= 0:
        print("\nNEGATIVE EDGE. Do not trade this with real money.")
        print("The correct position size for a losing strategy is zero.")
        return 0

    # --- is the sample big enough? ---------------------------------------

    section("IS THIS REAL, OR LUCK?")
    needed = trades_needed_for_significance(edge)
    print(f"trades so far                    {len(pnls)}")
    print(f"needed for 95% confidence        {needed}")

    print("\n(Uses your *measured* edge, so a lucky sample understates the")
    print("requirement. Treat it as a floor, not a target.)")

    if len(pnls) < needed:
        shortfall = needed - len(pnls)
        print(f"\nNOT YET SIGNIFICANT — {shortfall} more trades required.")
        print("A positive result on this sample is consistent with luck.")
        print("Everything below is provisional and should not size real money.")
    else:
        print("\nSample is large enough to distinguish this edge from noise.")

    # --- sizing -----------------------------------------------------------

    section("POSITION SIZING (from your measured edge)")
    full = kelly_fraction(win_rate, reward_risk)
    quarter = kelly_fraction_fractional(win_rate, reward_risk, 0.25)
    print(f"full Kelly                       {full:.1%} of equity per trade")
    print(f"quarter Kelly (recommended)      {quarter:.1%}")
    print("\nFull Kelly maximises growth and is nearly unusable in practice:")
    print("it spends most of its time in deep drawdown. Quarter Kelly gives")
    print("roughly half the growth for a quarter of the variance.")

    # --- survival ---------------------------------------------------------

    section("SURVIVAL OVER THE NEXT 500 TRADES")
    print(f"{'risk/trade':>12} {'P(lose 50%)':>12} {'median result':>14} {'median maxDD':>13}")
    for label, size in (
        ("current 0.5%", 0.005),
        ("quarter Kelly", quarter),
        ("half Kelly", full * 0.5),
        ("full Kelly", full),
    ):
        if size <= 0 or size >= 1:
            continue
        r = risk_of_ruin(win_rate, reward_risk, size, trades=500, simulations=3000)
        print(
            f"{label:>12} {r.probability_of_ruin:>11.1%} "
            f"{money(r.median_final_equity):>14} {r.median_max_drawdown:>12.1%}"
        )

    # --- process quality --------------------------------------------------

    if reviews:
        section("PROCESS QUALITY (from self-reviews)")
        matrix = Counter(
            (r.get("process_quality"), r.get("outcome")) for r in reviews
        )
        for (quality, outcome), count in sorted(matrix.items(), key=lambda x: -x[1]):
            note = ""
            if quality == "sound" and outcome == "loss":
                note = "  <- normal variance, not a problem"
            elif quality == "poor" and outcome == "win":
                note = "  <- got lucky; this is what builds bad habits"
            print(f"  {count:>4}  {quality} process / {outcome}{note}")

        poor = sum(c for (q, _), c in matrix.items() if q == "poor")
        if poor:
            print(f"\n{poor} of {len(reviews)} trades had poor process.")
            print("Read lessons.json — those are the recurring errors.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
