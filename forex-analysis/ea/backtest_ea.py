"""Backtest of GbpJpyMondayEA rules on the Dukascopy hourly data (2012-2022).

Replicates the EA exactly: buy Monday 00:00 server open, ATR(14,D1)x1.5 stop,
exit at the 23:00 bar close unless stopped intraday. Run from forex-analysis/:
    python ea/backtest_ea.py
"""

import numpy as np
import pandas as pd

PIP = 100
ATR_PERIOD, ATR_MULT = 14, 1.5
SPREAD_PIPS = 3  # typical FTMO GBPJPY cost per round trip

d1 = pd.read_csv("data/ejtrader_gbpjpy_d1.csv", parse_dates=["Date"])
h1 = pd.read_csv("data/ejtrader_gbpjpy_h1.csv", parse_dates=["Date"])
for df in (d1, h1):
    for c in ("open", "high", "low", "close"):
        df[c] /= 1000

# daily ATR, shifted so Monday uses data through the prior Friday
tr = np.maximum(d1.high - d1.low,
                np.maximum((d1.high - d1.close.shift()).abs(),
                           (d1.low - d1.close.shift()).abs()))
d1["atr"] = tr.rolling(ATR_PERIOD).mean().shift(1)
atr_by_date = dict(zip(d1.Date.dt.date, d1.atr))

h1["date"] = h1.Date.dt.date
trades = []
for day, g in h1[h1.Date.dt.dayofweek == 0].groupby("date"):
    g = g.sort_values("Date")
    first, last = g.iloc[0], g[g.Date.dt.hour <= 23].iloc[-1]
    if first.Date.hour != 0:
        continue
    atr = atr_by_date.get(day, np.nan)
    if not np.isfinite(atr):
        continue
    entry = first.open
    sl = entry - atr * ATR_MULT
    stopped = g[g.low <= sl]
    exit_px = sl if len(stopped) else last.close
    trades.append({"date": pd.Timestamp(day),
                   "pips": (exit_px - entry) * PIP - SPREAD_PIPS,
                   "stopped": bool(len(stopped))})

t = pd.DataFrame(trades).set_index("date")

def report(label, s):
    if not len(s):
        return
    print(f"{label:18s} n={len(s):4d}  mean={s.pips.mean():+6.1f} pips  "
          f"win={100 * (s.pips > 0).mean():4.1f}%  total={s.pips.sum():+8.0f}  "
          f"stopped={100 * s.stopped.mean():.0f}%  worst={s.pips.min():+.0f}")

print(f"Monday-long EA rules, {SPREAD_PIPS}-pip cost, ATR({ATR_PERIOD})x{ATR_MULT} stop")
report("full 2012-2022", t)
report("2015-2022", t[t.index.year >= 2015])
report("2017-2022", t[t.index.year >= 2017])
report("2020-2022", t[t.index.year >= 2020])
print("\nyearly mean pips:")
print(t.groupby(t.index.year).pips.mean().round(1).to_string())
