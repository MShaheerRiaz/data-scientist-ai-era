# Crypto Bot — Project Memory

Everything that matters about the Claude-powered Binance spot trading bot, in
one place. Written so a fresh session (or a future me) can pick this up cold
without re-deriving the reasoning.

**Repo:** `MShaheerRiaz/data-scientist-ai-era`
**Code:** `binance-claude-trader/`
**Branch:** `claude/gbpjpy-chart-analysis-1qnrqd`
**Status:** code-complete, 137 tests passing, never yet run against a live API key.

---

## 1. The hard constraints (these drove the whole design)

- **Spot only. No futures, no leverage, no shorting. Non-negotiable.**
  The owner lives in the **UK** but the Binance account is registered on
  **Pakistani details**. Two independent reasons: the FCA bans retail crypto
  derivatives for UK residents, and a residency/KYC mismatch carries real
  account-freeze risk — which would be catastrophic with leveraged positions
  open. Spot means the worst case is a frozen account holding coins, not a
  liquidation you cannot reach.
- **Claude picks the coin.** The owner explicitly refused to restrict it to one
  crypto: *"the decision will be entirely of Claude."* Hence the universe scan.
- **Paper trade on live markets first.** Real order book, simulated fills, no
  Binance keys required.
- **The bot must learn from its own mistakes** and watch news + volume
  ("as seen in Waqar Zaka's videos"). Hence `lessons.py` and `catalyst.py`.

---

## 2. The core architecture idea

> **Claude decides *what and whether*. Deterministic code decides *how much*.
> Those two responsibilities never mix.**

Claude chooses the symbol, the direction, the entry/stop/target, or returns
`none`. Everything about size, exposure, and shutdown is enforced in plain
Python that no prompt can talk its way past.

`confidence` filters trades (below 0.6 is rejected) but **never scales size** —
otherwise the model would have an incentive to inflate it.

### One cycle

```
exits → universe scan → snapshots → Claude decides → risk gate → execute
```

### Two clocks (important)

| Clock | Period | What runs |
|---|---|---|
| Decision | one closed candle (default 1h) | full cycle above, one Claude call |
| Protection | `POLL_SECONDS` (30s) | `manage_exits()` — stops and targets |

This decoupling is what makes a 1h decision interval safe. Without it, a stop
hit one minute into an hourly bar would sit unactioned for 59 minutes.
Pinned by `test_exits_are_enforced_between_candles`.

---

## 3. File map

| File | Role |
|---|---|
| `config.py` | settings + risk limits; `.env` loader; coherence warnings at startup |
| `main.py` | the loop, the two clocks, `run_cycle`, `manage_exits` |
| `risk.py` | **the gate** — deterministic, not promptable. `Position`, `PaperAccount`, `DayState`, `RiskGate` |
| `decision.py` | system prompt (byte-stable, cacheable) + strict JSON schema + payload builder |
| `executor.py` | order placement, entry drift guard, `check_exits` |
| `binance_client.py` | hand-rolled signed REST client, auditable, no SDK |
| `indicators.py` | EMA/RSI/ATR/swings/levels — pure Python, no numpy |
| `universe.py` | liquidity-filtered candidate selection |
| `catalyst.py` | volume anomaly detection + web-search news brief |
| `lessons.py` | post-trade review + deduplicated lesson book |
| `journal.py` | append-only JSONL journal + crash-safe state |
| `notify.py` | Telegram alerts + command polling |
| `telegram_control.py` | read-only command handler (`/status`, `/why`, …) |
| `quant.py` | expectancy, Kelly, risk of ruin, leverage maths |
| `analyze.py` | applies `quant.py` to the journal; reports real API cost |
| `llm/base.py` | provider interface — swapping providers is one file |
| `llm/anthropic_provider.py` | Claude, with caching/refusal/truncation handling |

---

## 4. Risk defaults and *why they are coupled*

```
RISK_PER_TRADE=0.005          # 0.5% of equity per trade
MAX_POSITION_PCT=0.30         # notional ceiling per position
MAX_DAILY_LOSS_PCT=0.03       # kill switch
MAX_CONCURRENT_POSITIONS=3
MIN_REWARD_RISK=1.2
MAX_STOP_DISTANCE_PCT=0.08
MIN_CONFIDENCE=0.6
```

**The coupling that bit us once and must not be forgotten:**

```
notional = risk_per_trade / stop_distance
```

At 1% risk against a 2% ATR stop, one position demands **50% of equity**, and
three of those exceed the account. At 0.5% the same stop needs 25%, which fits a
full book. The notional cap binds whenever `stop_distance < risk / max_position_pct`
— at the defaults that is any stop tighter than 3.3%, which normal ATR stops
clear. Set `MAX_POSITION_PCT` too low and it silently overrides `RISK_PER_TRADE`
on every trade, making that setting meaningless.

Keep `max_position_pct × max_concurrent_positions ≤ 1.0` — spot cannot borrow.
`config.py` prints a warning at startup if either invariant breaks.

### Every trade has a stop and a target — enforced at three layers

1. **Schema** — `entry`, `stop`, `target` are required; strict, `additionalProperties: false`. Claude cannot return a trade without them.
2. **Risk gate** (`risk.py`) — rejects if any is ≤ 0, if stop ≥ entry, if target ≤ entry, if stop > 8% away, if stop < 0.15% away (inside spread+fees), or if R:R < 1.2.
3. **`Position`** — cannot be constructed without stop and target.

**Caveat:** stops are enforced by the **running process**, not resting on the
exchange. A dead VPS means unprotected positions. The bot Telegrams you on
shutdown-with-positions for exactly this reason. Exchange-resting OCO orders are
the fix — designed, discussed, **not built** (live-mode only; see §11).

---

## 5. Why 5% risk per trade was rejected

The owner initially proposed 5% or less. The rebuttal was mathematical, not
stylistic, and `quant.py` exists to make it checkable:

- 5% per trade is roughly **full Kelly** for a decent edge. Full Kelly is
  growth-optimal *and* brutal — it spends most of its life in deep drawdown.
- **2× Kelly has a median outcome below break-even even with a genuinely
  positive edge.** There is a test asserting exactly this.
- Quarter Kelly gives ~half the growth for a quarter of the variance.
- The principle adopted: **earn the size.** Grow into bigger risk through
  demonstrated performance in the journal, never through optimism.

Also settled here: **"0.5R"** means half of what you risked on that trade. If
you risk £50 and make £25, that's +0.5R. R normalises results so a 2% stop and
a 6% stop are comparable.

**"385 trades"** is the sample size needed to be ~95% confident a +0.1R edge is
real and not luck. `analyze.py` computes this from your own measured edge.

---

## 6. The strategy — a blend, split by layer

| Layer | What it does | Where |
|---|---|---|
| **Technical** | market structure, EMAs, RSI, ATR, swing points, equal levels. Stops behind structure, not arbitrary percentages | `indicators.py` → Claude |
| **Volume** | each coin vs **its own** baseline. `volume_ratio ≥ 2.0` **and** `range_expansion ≥ 1.3` → anomalous | `catalyst.py` |
| **Fundamental** | Claude web-searches a market brief, focused on whatever volume flagged | `catalyst.py` |
| **Mathematical** | sizing, R:R floor, kill switch, Kelly/expectancy/ruin | `risk.py`, `quant.py` |

**Ordering principle: volume leads, news explains.** The anomaly is the signal;
the headline is the reason. News is context, never a trade trigger by itself.

Honest one-line description: *a discretionary technical trader with a volume
scanner, a news desk, and an uncompromising risk manager it does not control.*

---

## 7. The learning system

After every closed trade, Claude critiques it — **judging process, not outcome**:

| | Win | Loss |
|---|---|---|
| **Sound process** | no lesson | usually no lesson (good trades lose) |
| **Poor process** | **flagged** (lucky, dangerous) | lesson recorded |

- `entry_snapshot` and `reasoning` are captured **at entry** so the reviewer
  judges what was knowable then — otherwise it produces hindsight, not lessons.
- Lessons dedupe by **Jaccard similarity ≥ 0.75** with occurrence counts.
  (0.6 overlap/min was tried and wrongly merged *opposite* lessons — "volume
  spike means enter" with "volume spike means wait".)
- Capped at 25, pruned by occurrences then recency.
- Lessons go in the **user payload**, never the cached system prompt.

---

## 8. Cost (measured, not guessed)

Measured sizes: **system prompt 1,331 tokens**, **171 tokens per coin snapshot**.
A 12-coin decision ≈ 4,300 tokens in, ~1,250 out (thinking is on by default and
shares the budget).

At `claude-opus-5` list price, **1h candles**:

| Component | Cadence | Monthly |
|---|---|---|
| Decisions | 720/mo | ~$38 |
| News briefs | 180/mo (4-hourly) | ~$9 + search fees |
| Reviews | per closed trade | ~$2 |
| **Total** | | **~$50** |

15m candles → decisions ×4 ≈ $150/mo. Sonnet ≈ 60% of these.

**Levers, biggest first:** `CANDLE_INTERVAL` → `NEWS_REFRESH_SECONDS` → `CLAUDE_EFFORT`.

**Never trust the estimate — run `python analyze.py`.** It prices the actual
journalled usage and projects a run rate. (Note: the API's `input_tokens` is the
*uncached remainder*; cache reads/writes are separate fields that must be added.)

### The counterintuitive caching rule

A 1h-TTL cache **write** bills at **2× base**. A breakpoint that is never read
therefore costs *more* than not caching at all. On 1h candles the entry expires
almost exactly when the next decision lands — so caching was silently costing 2×.
**Caching is now enabled only when the candle is shorter than the TTL.** Startup
prints `prompt-cache=on|off`.

---

## 9. Telegram — read-only by design

Commands: `/status` `/positions` `/why` `/rejected` `/journal` `/pnl` `/lessons` `/help`

- **Nothing sent over chat can act on the account.** No open, close, pause, or
  resize. `/pause` and `/resume` existed briefly and were deliberately removed.
  Reasoning: chat is the only part of the system reachable from the open
  internet, so the worst case for a leaked token is someone reading a P&L figure.
  A test asserts no acting method exists on the handler.
- Only the configured chat id gets **any** reply. Strangers get nothing — not
  even an error — so they cannot confirm the bot is running. The owner is warned
  the first time an unknown chat appears (capped, so it cannot become spam).
- Poll timeout is bounded (5s) because command polling shares the loop with the
  exit watcher — chat must never delay a stop.
- To halt trading: **stop the service on the VPS.** That is the only authority.

---

## 10. Bugs found and fixed (worth remembering — several are subtle)

1. **Risk-coupling incoherence** — 1% risk + 20% cap meant the notional cap bound on every realistic stop, making `RISK_PER_TRADE` meaningless.
2. **Duplicated defaults** — literals in `from_env()` diverged from the dataclass, so tests validated one set and the bot ran another. Fixed with a sparse override dict.
3. **`from __future__ import annotations`** made `field.type` the *string* `"int"`, so every int config field silently became a float.
4. **Paper-mode silent no-op** — equity read from the real (empty) account → every position sized to zero → bot ran "fine" and never traded. The stub exchange now *raises* if paper mode touches a real balance.
5. **Lesson dedup merged opposite lessons** (see §7).
6. **"Reckless" 25% risk was exactly full Kelly** — the test assertion failed and taught the real lesson; tests rewritten around 2× Kelly.
7. **`.env` was never loaded** — the documented setup flow silently did nothing.
8. **No entry drift guard** — a decision could fill far from its intended entry, wrecking the R:R it was approved on.
9. **Catalyst `pause_turn`** returned half-written news briefs.
10. **Truncation risk** — 8000/4000 max_tokens with thinking on → silently cut JSON. Now 16000 + explicit error.
11. **10-minute default SDK timeout** — most of a 15m bar. Now 300s.
12. **Exits only ran at cycle boundaries** — the whole reason the second clock exists.
13. **Telegram poll timeout (15s)** could postpone the next stop check. Now 5s.
14. **Prompt caching cost 2× at the 1h default** (see §8).
15. **News briefs ran hourly**, costing as much as the entire decision loop.

Also: invalid `CANDLE_INTERVAL`/`CLAUDE_EFFORT` failed silently; `endswith("USDT")`
mismatched real quote assets; `exchangeInfo` was fetched twice per cycle.

---

## 11. Decisions made, and what was deliberately *not* built

**Settled:**
- 1h candles over 15m (4× cheaper, less noise; protection unaffected).
- Scan the market while paper trading, don't pin to BTC. Alts correlate, so 10
  coins ≠ 10 independent edges — the scan's value is *selection*, not
  diversification. `SYMBOL_ALLOWLIST=BTCUSDT` pins it later if the data says so;
  `analyze.py` has an **EDGE BY SYMBOL** table to settle it empirically.
  Check trade *count* per symbol, not just profit — 3 lucky trades is noise.
- Official Anthropic SDK, not OpenRouter (needs `cache_control` TTLs,
  `output_config.format`, and reliable cache-hit usage fields).
- Telegram read-only.

**Offered and not built (say the word):**
- **Exchange-resting OCO stops** — the one real gap in "every trade is protected".
  Live-mode only, so it can wait until real money is close.
- Futures with 3× cap and shorting — blocked by §1, would need the constraint to change.
- Multi-timeframe (1h analysis + 15m entry).
- Wiring AI-capex / Nvidia-earnings regime awareness into `catalyst.py` (from
  the situational-awareness research — see `research/situational-awareness-notes.md`).

---

## 12. Going live — the checklist

**Do not skip the gate: ~50+ closed paper trades with positive expectancy first.**
Then start with **£500–£1,000**.

- Floor is ~£400–500: below that, Binance minimum order sizes and rounding
  distort position sizes and live results stop resembling paper results.
- The first months live are a *second test* — that live fills match paper fills.
  You are paying for information; pay as little as possible for it.
- Must be money that can be lost entirely.

**Binance API key setup (only when `DRY_RUN=false`):**
1. Binance → profile → **API Management** → Create API
2. ✅ Enable **Spot & Margin Trading**
3. ❌ **Withdrawals OFF** — non-negotiable
4. ❌ **Futures OFF**
5. **Restrict to the VPS IP**
6. Paste into `.env`, set `BINANCE_TESTNET=false` and `DRY_RUN=false`
7. Restart — it prints `LIVE TRADING ARMED`

**Three modes:**

| TESTNET | DRY_RUN | Meaning |
|---|---|---|
| true | true | fake book, simulated fills (plumbing check) |
| **false** | **true** | **real book, simulated fills ← paper trading** |
| false | false | real book, real money |

---

## 13. Still pending

- [ ] **Anthropic API key** (owner's task)
- [ ] **VPS setup** — step-by-step walkthrough requested but not yet given.
      Needs: systemd service, auto-restart, `.env` placement, log rotation.
      ~£5/month box; can host other things alongside it.
- [ ] First paper run — nothing has ever executed against a live API key.
- [ ] Telegram BotFather setup (2 min, when wanted)

---

## 14. Conventions

- Commit trailers: `Co-Authored-By: Claude <noreply@anthropic.com>` +
  `Claude-Session: <url>`
- Push: `git push -u origin claude/gbpjpy-chart-analysis-1qnrqd`
- Tests are plain Python, no pytest dependency: `python3 tests/test_x.py`
- Run all: `for f in tests/test_*.py; do python3 "$f"; done`
- **137 tests across 8 files.** Every bug in §10 has a test pinning the fix.
  If you change behaviour and a test fails, read *why* it exists before editing it.

---

## 15. Not in this repo

The **GBPJPY / forex analysis** was conversational only and was never written to
a file. It is not recoverable here — a forex session starts fresh. That is fine;
chart reads go stale anyway.
