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
