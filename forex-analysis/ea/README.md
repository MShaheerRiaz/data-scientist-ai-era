# GbpJpyMondayEA — custom MT5 Expert Advisor

Implements the one edge from [`../REPORT.md`](../REPORT.md) that survived every test:
**long GBP/JPY through Monday**, from the week's first bar to Monday's last hour.
Built as a private, single-user EA for use on FTMO accounts.

## The rules it trades

**Module 1 — Monday long** (the primary edge) and **Module 2 — Friday short**
(`InpFridayShort`, on by default): sell GBPJPY at Friday 00:00 server, ATR stop above,
close at 22:00 Friday (buffer before the weekend). Friday-short backtest, exact rules,
net of 3 pips: **+12.5 pips/trade 2012–2022, positive 10 of 11 years**, ~+2–5 pips/trade
in recent years, ~4% stopped out. Thinner than Monday — treat it as a satellite.
Thursday-short was tested the same way and **rejected** (+1 pip 2017–22, negative
2020–22 — its reputation comes from overnight gaps a day-bot can't capture).

### Monday long in detail

1. Monday, first server-time bar (00:00 on FTMO's EET-style server clock = the week open): **buy** GBPJPY.
2. Stop-loss: `ATR(14, D1) × 1.5` below entry (or a fixed pip stop via input). Position sized so the stop costs `RiskPercent` of balance (default **0.5%**).
3. Exit: close at the 23:00 server bar on Monday (never holds overnight into Tuesday, never over a weekend).
4. One trade per week. That's the whole system.

## Backtested on 2012–2022 hourly data, net of 3 pips cost (`backtest_ea.py`)

| Window | Trades | Mean/trade | Win rate | Stopped out |
|---|---|---|---|---|
| 2015–2022 | 371 | **+9.9 pips** | 55.8% | 4% |
| 2017–2022 | 268 | **+8.8 pips** | 57.1% | 4% |
| 2020–2022 | 113 | **+16.3 pips** | 61.1% | 5% |

Yearly means positive every year 2015–2022; 2013–2014 were flat/negative — this edge
was weak before the current yen regime and can weaken again. The 2021–2026 daily study
(61.5% of Mondays up, positive all six years) suggests it strengthened after the
hourly data ends, but that part is unverified intraday. **Forward-test on a demo or
FTMO Free Trial for a few weeks before the real Challenge.**

## FTMO compliance (why this EA is allowed)

- FTMO permits EAs on Challenge and funded accounts; the risk they flag is
  *commercial third-party* EAs (many users, identical trades → capital-allocation
  denials). This EA is your own private strategy — the allowed category.
- No banned behavior by construction: one market order per week, no tick scalping,
  no latency/feed arbitrage, no HFT bursts, negligible server requests.
- No weekend holding → works on regular (non-Swing) accounts.
- Risk guards sit **inside** FTMO's limits: trading halts for the day at −3% equity
  from the day's start (FTMO limit 5%) and the EA freezes entirely at −8% from its
  attach-time baseline (FTMO limit 10%).
- News filter: entries are blocked within ±3 minutes of high-impact GBP/JPY/USD
  calendar events (FTMO's Challenge/Verification news rule is ±2 minutes). Since the
  entry is 00:00 server, collisions are rare anyway.
- The FTMO rulebook changes — re-check ftmo.com FAQ before each Challenge.

## Install & verify

1. Open MetaEditor from MT5 (F4) → File → Open → `GbpJpyMondayEA.mq5` → **Compile** (F7, expect 0 errors).
2. In MT5: View → Strategy Tester → Expert: GbpJpyMondayEA, Symbol: GBPJPY, Period: H1,
   model "Every tick based on real ticks", date range ≥ 2 years → run and compare with the table above.
3. Attach to a GBPJPY chart on demo. Allow Algo Trading. Leave inputs at defaults
   (0.5% risk) for the Challenge; the guards do the rest.
4. It trades once a week — Sunday night/Monday. Don't panic when it does nothing on Wednesday.

Inputs you might actually change: `InpRiskPercent` (0.5 → 0.25 for extra safety),
`InpExitHour`, `InpMaxSpreadPips` (skip thin/wild opens), `InpNewsBlockMinutes`.

## Journal

Same design as `binance-claude-trader/journal.py`: an **append-only JSONL file**
where every decision is recorded — including the entries that were *skipped* and
why (spread too wide, news blackout, guard tripped). Skips and guard events are
the most useful records: they tell you whether the filters are protecting you or
muzzling the strategy.

- File: `GbpJpyMondayEA_journal.jsonl` in the terminal's **Common** data folder
  (MT5 → File → Open Data Folder → up one level → `Common\Files\`).
- Events: `attach`, `entry` (price, lots, SL, spread, risk%), `exit` (reason,
  pips, profit, hours held), `skip_entry` (reason), `guard_daily_loss`,
  `guard_total_drawdown`, `error`, `detach`. Every line carries timestamp,
  equity and balance.
- Review loop: this EA is deterministic, so unlike the crypto bot there is no
  in-loop LLM reviewing each decision. Instead, paste the journal file into a
  Claude session periodically — the same process-vs-outcome review applies (a
  losing Monday is not automatically a mistake; a winning one is not
  automatically correct). What you're auditing is execution quality (slippage,
  spread at entry, guard behaviour) and whether the edge is decaying.
- Turn off with `InpJournal = false` if ever needed.

## Keeping it running (you do NOT need your laptop on 24/7)

The EA only ever acts between Sunday ~23:00 and Tuesday 00:05 **server time**
(entry at the Monday 00:00 bar, exit at 23:00 Monday). Outside that window it
does nothing. Your options, best first:

1. **MT5 built-in VPS (recommended):** right-click the chart → "Add to Virtual
   Hosting" (~$10–15/month). Your EA + settings migrate to MetaQuotes' server,
   run 24/7 with ~1–5 ms latency to the broker, and your laptop can be off.
2. **Any Windows VPS** (Contabo/Kamatera/ForexVPS etc., ~$5–15/month): install
   MT5, log into the FTMO account, attach the EA once, leave it running.
3. **Laptop only:** fine for paper trading — it just has to be on, with MT5
   open and Algo Trading enabled, from Sunday night through Monday close
   (server time). If the machine sleeps mid-trade the stop-loss still sits on
   the broker's server (it's a real SL order, not a virtual one), so the
   position is protected; you'd only miss the timed 23:00 exit, and the EA
   closes the leftover position the moment it reconnects (any non-Monday bar
   triggers the safety exit).

For the paper phase: FTMO Free Trial or any MT5 demo account + your laptop is
plenty. Move to a VPS when real Challenge money is on the line.
