# GbpJpyMondayEA — custom MT5 Expert Advisor

Implements the one edge from [`../REPORT.md`](../REPORT.md) that survived every test:
**long GBP/JPY through Monday**, from the week's first bar to Monday's last hour.
Built as a private, single-user EA for use on FTMO accounts.

## The rule it trades

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
