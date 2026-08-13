# GJ Bossman — GBP/JPY Trading Memory File

> **What this is:** The persistent memory of the "GBP/JPY Bossman" project. Give this file
> to any Claude session (or read it yourself) to restore full context on the GBP/JPY
> trading study, the FTMO EA, and how we work together. Last updated: **2026-08-07**.

## 1. The mission

Shaheer trades **GBP/JPY** ("GJ"), aiming to pass an **FTMO Challenge** on **MT5**.
Claude's role: data analysis, trade review copilot, and EA development. Claude never
executes trades — Shaheer is always the executor (prop-firm compliant).

## 2. The edge (from the 5-year study, Aug 2021 – Aug 2026)

The one finding that survived every test — **Monday-long bias on GBP/JPY**:

- **61.5% of Mondays closed up**, mean **+0.115%/Monday**, t-stat 3.0, positive in
  **all six calendar years** 2021–2026.
- Independently confirmed on separate Dukascopy data 2017–2022 (59.7% up, t = 2.5).
- Monday is also the **calmest** day: 122 pips avg range vs 137 on Thursday; smallest tails.
- **Thursday** is the only reliably negative day (~45% up, biggest ranges/tails).
- **Friday** drifted negative in *every* intraday session across 10 years (weekend fade).
- Hours (London time): busiest 08:00–16:00, peaks 08–09 (~35 pips/h) and 14–16
  (~40 pips at 15:00). Dead zone 03:00–06:00 (~15 pips/h). Shaheer trades London hours.
- Critical detail: the Monday edge is earned **from the week open (00:00 server)** —
  entering at London open captures roughly zero of it.

**Caveats that must travel with the edge:** 2021–26 was one long yen-weakening regime
(part of the tilt IS the trend; can flip if BoJ regime turns — see Aug 2024); many
patterns were tested so smaller effects may be luck; session drifts of 3–7 pips don't
survive 2–4 pip spreads; intraday OHLC data ends Mar 2022. This is a probability tilt,
not a system.

## 3. The EA (built, pushed, awaiting paper test)

`forex-analysis/ea/GbpJpyMondayEA.mq5` — custom **MQL5 / MT5** expert advisor:

- Buys GBPJPY on Monday's first bar (00:00 server = week open on FTMO's EET clock),
  SL = ATR(14, D1) × 1.5, sized to risk **0.5%**/trade, exits 23:00 Monday.
  One trade/week, never holds a weekend (works on regular non-Swing FTMO accounts).
- Guards inside FTMO limits: daily halt at −3% (FTMO: 5%), full freeze at −8% (FTMO: 10%),
  max-spread skip, ±3-min high-impact news filter.
- **Backtest net of 3-pip cost** (`ea/backtest_ea.py`): 2015–22 **+9.9 pips/trade, 55.8% win**;
  2017–22 +8.8 pips, 57.1%; 2020–22 **+16.3 pips, 61.1%**; only ~4% of trades stopped out;
  positive every year 2015–2022 (flat/negative 2013–14 — pre-regime).
- **Journal:** append-only JSONL at MT5 `Common\Files\GbpJpyMondayEA_journal.jsonl` —
  logs entries, exits (pips/profit/hours held), *skipped entries with reasons*, guard
  trips, errors. Design ported from `binance-claude-trader/journal.py`.
- Review loop: periodically paste the journal into a Claude session for a
  **process-vs-outcome** review (a losing Monday ≠ mistake; a winning one ≠ correct).

**FTMO ruling (verified Aug 2026): EAs are ALLOWED** on Challenge and funded accounts —
no pre-approval. Banned: tick scalping, latency/feed arbitrage, HFT bursts, >2,000 server
req/day. Risk zone is *commercial third-party* EAs (identical trades across users →
capital-allocation denials); this private custom EA is the allowed category. News rule:
no opens within 2 min of high-impact news during Challenge/Verification. Re-check the
FTMO FAQ before each Challenge — rules change.

## 3b. Module 2: Friday short (added Aug 2026, bot-only mode)

- Shaheer decided **bot-only trading** (no discretionary for now).
- **Friday-short module baked into the EA** (`InpFridayShort=true`): sell Fri 00:00
  server, ATR×1.5 stop above, exit 22:00 Fri. Exact-rules backtest net of 3 pips:
  **+12.5 pips/trade 2012–22, positive 10/11 years** (only 2019 negative);
  recent years ~+2–5 pips. Satellite edge — Monday-long remains primary.
- **Thursday-short tested and REJECTED**: +1 pip 2017–22, −4.6 in 2020–22 intraday.
  Its close-to-close negativity is overnight-gap driven — not capturable by a day bot.
  Do not re-add without new evidence.

## 3c. Second pair: AUDJPY Monday-long (validated Aug 2026, full GJ-standard checks)

- Multi-pair sweep of 12 pairs found Monday-long is market-wide; **AUDJPY strongest**.
- Checked to the identical standard as GBPJPY:
  1. Exact-EA-rules h1 backtest 2012-22 (net 2 pips): **+7.5 pips/Mon 2017-22, 58.2% win,
     +16.0 pips 2020-22**, positive every year 2015-2022, ~2% stopped.
  2. FRED cross + currency-api validation Aug 2021 - Aug 2026: **+0.102%/Mon, t=2.3,
     positive 6/6 calendar years including 2026.**
- Deploy: same EA file on an AUDJPY chart, `InpFridayShort=false` (AUDJPY Friday didn't
  validate), `InpRiskPercent=0.35` on BOTH charts when running both (GJ+AUDJPY Monday
  longs are the same short-yen macro bet - correlated).
- **AUDJPY Wednesday-long: REJECTED for the bot** - strong close-to-close (6/6 years)
  but only +1.7 pips intraday 2017-22 exact-rules; mostly overnight-gap, same trap as
  GJ Thursday. Watch in journal, don't trade.
- **EURCHF Monday: REJECTED** - highest historical t (5.3) but dead since 2021
  (t=0.5). Lesson: always validate on recent data before deploying.

## 4. The plan (agreed Aug 2026)

1. **Paper trade for 1 month**: MT5 demo / FTMO Free Trial, EA at defaults.
   Compile in MetaEditor (F7), validate in Strategy Tester vs the table above first.
2. **One Windows VPS runs both bots** (this EA + the Binance crypto bot), journals kept
   separate. Laptop not needed 24/7 — EA only acts Sunday night → Monday close (server
   time); SL is server-side so a dropped connection still protects the position.
3. **Budget**: VPS $10–20/mo; forex side $0 API. Crypto bot (Opus, 1h cycle + news scan)
   ≈ $40–70/mo. Total ≈ $50–90/mo. Decision made: keep the crypto bot on the model you
   intend to run live (don't paper-test on Haiku — results wouldn't transfer).
4. After a green month: FTMO Challenge, same EA, same settings, risk 0.5% (or 0.25%).

## 4b. Risk model & execution rules (agreed Aug 2026)

**Discretionary challenge/funded-account rules — the path that actually passes:**

- Base risk: **0.5% per trade**, RR minimum **1:2** (win +1.0%, loss −0.5%).
- Breakeven win rate 33.3%. Targets: 45% WR → ~57 trades to +10%; 50% → 40; 55% → ~31.
  At 2–3 setups/week ≈ 3–6 months for Phase 1; Phase 2 (+5%) about half.
- **Scaling rule:** risk may rise to 0.75–1.0% ONLY when account is ≥ +3% cumulative
  AND the setup is A-grade. If profit drops back below +3%, risk reverts to 0.5%.
  Never exceed 1.0% per trade. Never scale up after a loss (no revenge sizing).
- **Every entry goes in with SL and TP attached** (real server-side orders, placed at
  order entry, never mental stops, never added later).
- **Stop size (from the 5y data):** 20–25 pips is too tight for GBPJPY — average
  *single-hour* range in London hours is 29–40 pips, so a 20-pip stop sits inside one
  candle's noise. Working band: **25–40 pips**, placed at structure (beyond the swing),
  not at a fixed number. With 1:2 that means 50–80 pip targets — vs ~122–137 pip average
  daily range, so targets are realistic on trending days only; skip setups whose 2R
  target exceeds ~60–70% of the day's expected range remaining.
- Spread counts: 2–4 pip spread on a 25-pip stop is ~10–15% hidden cost — measure RR
  from real fill prices.
- Guardrails: max **2 losses/day then stop** (−1% day, far from FTMO's −5%);
  max 1–2 concurrent GJ positions; no entries within ±3 min of high-impact news;
  flat over weekends on the challenge; London hours only (08:00–16:00 UK), avoid 03–06.
- Session seasonality filter (§2): prefer longs Mon–Wed, extra skepticism on
  Thu–Fri longs.
- FTMO fee only after the journal shows **≥45% WR over 30+ logged trades** at 1:2.
- Known holes (not foolproof, by design honest): actual WR at 1:2 is unproven until
  journaled; discipline on the 2-loss rule is on Shaheer; news gaps can slip past a SL
  (rare, sized survivable at 0.5%).

## 5. Live trade review workflow

When Shaheer shares a chart + idea, Claude gives: (1) technical read (structure, levels,
stop/target vs average ranges above), (2) fundamental/calendar check (UK/US/JP news,
BoE/BoJ, risk sentiment — GJ is a risk proxy), (3) seasonality overlay from §2,
(4) verdict as **probability + invalidation**, never a guarantee.

## 6. Where everything lives

- **Repo:** `MShaheerRiaz/data-scientist-ai-era`, branch **`claude/gbp-jpy-trading-analysis-82h34i`**
  - `forex-analysis/REPORT.md` — full study write-up
  - `forex-analysis/gbpjpy_analysis.ipynb` — executed notebook; `analysis.py`, `charts.py`
  - `forex-analysis/data/` — all datasets + provenance README (FRED cross to Dec 2025,
    currency-api 2026, Dukascopy OHLC/h1 2012–2022; cross-checked, corr 0.995)
  - `forex-analysis/ea/` — EA source, backtest, README
- **Interactive dashboard:** https://claude.ai/code/artifact/a2753630-ef81-46f8-aca8-d54b30f318a5
- **Origin session:** "GBP/JPY Bossman", `session_01WQAzYcRUgTuWjygXyKvDz9` (Aug 7, 2026)
- **Crypto bot** (sibling project): `binance-claude-trader/` on branch
  `claude/gbpjpy-chart-analysis-1qnrqd` (branch name is misleading — it's the crypto bot).

## 7. Routine history (investigated Aug 7, 2026)

- A **GBPJPY routine existed and was disabled on 2026-07-02** (session: "Disable GBPJPY
  and app idea scout routines"). It no longer appears in the account's routines list.
- **None of its collected data was ever committed to the repo** (all branches searched —
  zero GJ files). Its cloud run containers were ephemeral → that data is unrecoverable
  from the cloud side. If it saved files locally, they'd be on the laptop
  Desktop (local Cowork tasks don't appear in the cloud routines list) — check there.
- The routine still firing at 9 AM Pakistan time (04:00 UTC) is the **"Daily SaaS & App
  Idea Scout"** — unrelated to GJ.
- Either way, nothing of value was lost: the 5-year study in §2 supersedes any daily
  chart snapshots that routine collected.

## 8. Open items

- [ ] Compile EA in MetaEditor; run Strategy Tester vs README table
- [ ] Start 1-month paper test (demo/Free Trial), journal on
- [ ] Pick and set up the Windows VPS (both bots)
- [ ] After ~4 Mondays: bring `GbpJpyMondayEA_journal.jsonl` to a session for review
- [ ] Decide: recreate a (useful) GJ morning routine? If yes, make it commit its output
      to the repo so data is never lost again
- [ ] Repo hygiene: `Toft/era-data-ai-scientist-submountain.zip` on main looks like a
      Windows malware dropper — recommended delete (untouched so far)
