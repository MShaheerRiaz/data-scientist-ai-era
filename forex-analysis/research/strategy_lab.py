"""Strategy lab: systematic intraday strategy tests on GBPJPY (GJ) and AUDJPY (AJ).

Data: Dukascopy m15/h1/d1 2012-2022, MT-server time (London = server - 2h).
Discipline: in-sample 2012-2018, out-of-sample 2019-2022, costs included
(3 pips GJ, 2 pips AJ round trip). A strategy survives only if expectancy > 0
in BOTH splits. R = profit as a multiple of the amount risked on the trade.

Run from forex-analysis/:  python research/strategy_lab.py
"""

import numpy as np
import pandas as pd

BASE = "/tmp/claude-0/-home-user-data-scientist-ai-era/eef445db-5aaa-5bd9-84d0-49793a7be370/scratchpad/ejtrader-data"
PIP = 100
COST = {"GBPJPY": 3, "AUDJPY": 2}
OOS_YEAR = 2019


def load(pair):
    m = pd.read_csv(f"{BASE}/{pair}/{pair}m15.csv", parse_dates=["Date"])
    d = pd.read_csv(f"{BASE}/{pair}/{pair}d1.csv", parse_dates=["Date"])
    for df in (m, d):
        for c in ("open", "high", "low", "close"):
            df[c] /= 1000
    m = m[m.Date.dt.dayofweek < 5].copy()
    m["date"] = m.Date.dt.date
    m["hh"] = m.Date.dt.hour + m.Date.dt.minute / 60
    tr = np.maximum(d.high - d.low, np.maximum((d.high - d.close.shift()).abs(),
                    (d.low - d.close.shift()).abs()))
    d["atr"] = tr.rolling(14).mean().shift(1)
    d["date"] = d.Date.dt.date
    return m, d


def resolve(bars, side, entry, sl, tp):
    """Walk bars; return R outcome (+2 TP, -1 SL, else mark-to-market at end)."""
    risk = abs(entry - sl)
    for _, c in bars.iterrows():
        if side == 1:
            if c.low <= sl:
                return -1.0
            if c.high >= tp:
                return (tp - entry) / risk
        else:
            if c.high >= sl:
                return -1.0
            if c.low <= tp:
                return (entry - tp) / risk
    if len(bars):
        return side * (bars.iloc[-1].close - entry) / risk
    return 0.0


def run_daily(m, fn):
    """fn(day_df, dow, ctx) -> (side, entry_bar_time, entry, sl, tp) or None."""
    out = []
    for day, g in m.groupby("date"):
        g = g.sort_values("Date")
        r = fn(g, pd.Timestamp(day).dayofweek)
        if r is None:
            continue
        side, t0, entry, sl, tp = r
        after = g[(g.Date > t0) & (g.hh <= 21)]
        out.append((pd.Timestamp(day), resolve(after, side, entry, sl, tp),
                    abs(entry - sl) * PIP))
    return out


def report(name, rows, cost):
    if not rows:
        print(f"{name:34s}  no trades")
        return None
    t = pd.DataFrame(rows, columns=["d", "R", "risk_pips"]).set_index("d")
    t["Rnet"] = t.R - cost / t.risk_pips
    ins, oos = t[t.index.year < OOS_YEAR], t[t.index.year >= OOS_YEAR]
    line = f"{name:34s}"
    verdict = []
    for lbl, s in (("IS", ins), ("OOS", oos)):
        if len(s) < 30:
            line += f"  {lbl}: n<30"
            verdict.append(False)
            continue
        line += (f"  {lbl}: n={len(s):4d} {s.Rnet.mean():+.3f}R "
                 f"w={100 * (s.Rnet > 0).mean():.0f}%")
        verdict.append(s.Rnet.mean() > 0)
    surv = all(verdict) and len(verdict) == 2
    print(line + ("   << SURVIVES" if surv else ""))
    return t if surv else None


# ---------------- strategy definitions (all London-session, server time) ----
def asian_range(g):
    a = g[(g.hh >= 2) & (g.hh < 10)]
    if len(a) < 20:
        return None
    return a.high.max(), a.low.min()


def s_gapfill(g, dow, d1_close_prev):
    """Monday weekend-gap fill: fade the gap toward Friday's close."""
    if dow != 0 or d1_close_prev is None:
        return None
    o = g.iloc[0]
    gap = (o.open - d1_close_prev) * PIP
    if abs(gap) < 15 or abs(gap) > 120:
        return None
    side = -1 if gap > 0 else 1
    entry = o.open
    tp = d1_close_prev
    sl = entry - side * abs(entry - tp)  # 1:1 on the gap size
    return side, o.Date, entry, sl, tp


def s_first_hour_momo(g, dow):
    """Direction of first London hour (10:00-11:00) -> follow, 30/60."""
    fh = g[(g.hh >= 10) & (g.hh < 11)]
    if len(fh) < 3:
        return None
    mv = (fh.iloc[-1].close - fh.iloc[0].open) * PIP
    if abs(mv) < 15:
        return None
    side = 1 if mv > 0 else -1
    e = fh.iloc[-1].close
    return side, fh.iloc[-1].Date, e, e - side * 30 / PIP, e + side * 60 / PIP


def s_london_fade(g, dow):
    """NY fade: if 10:00-15:00 moved >70 pips one way, fade at 15:00, tp 50% back."""
    ld = g[(g.hh >= 10) & (g.hh < 15)]
    if len(ld) < 10:
        return None
    mv = (ld.iloc[-1].close - ld.iloc[0].open) * PIP
    if abs(mv) < 70:
        return None
    side = -1 if mv > 0 else 1
    e = ld.iloc[-1].close
    ext = ld.high.max() if mv > 0 else ld.low.min()
    sl = ext + (10 / PIP) * (1 if mv > 0 else -1)
    tp = e + side * abs(mv) * 0.5 / PIP
    return side, ld.iloc[-1].Date, e, sl, tp


def s_bb_fade(g, dow):
    """m15 Bollinger(20,2) fade during London, tp = mid band."""
    g = g.copy()
    g["ma"] = g.close.rolling(20).mean()
    g["sd"] = g.close.rolling(20).std()
    ldn = g[(g.hh >= 10) & (g.hh <= 18)]
    for _, b in ldn.iterrows():
        if np.isnan(b.ma):
            continue
        up, dn = b.ma + 2 * b.sd, b.ma - 2 * b.sd
        if b.close > up:
            e = b.close
            return -1, b.Date, e, e + 25 / PIP, b.ma
        if b.close < dn:
            e = b.close
            return 1, b.Date, e, e - 25 / PIP, b.ma
    return None


def make_s_prevday_momo(d1):
    cl = dict(zip(d1.date, d1.close))
    op = dict(zip(d1.date, d1.open))
    dates = sorted(cl)
    prev = {dates[i]: dates[i - 1] for i in range(1, len(dates))}

    def f(g, dow):
        day = g.iloc[0].date
        p = prev.get(day)
        if p is None:
            return None
        mv = (cl[p] - op[p]) * PIP
        if abs(mv) < 60:            # only after a strong day
            return None
        side = 1 if mv > 0 else -1
        o = g.iloc[0]
        e = o.open
        return side, o.Date, e, e - side * 40 / PIP, e + side * 80 / PIP
    return f


def s_breakout_fvg(g, dow):
    """Asian breakout confirmed by an FVG in the same direction within 8 bars."""
    ar = asian_range(g)
    if ar is None:
        return None
    hi, lo = ar
    post = g[(g.hh >= 10) & (g.hh <= 18)].reset_index(drop=True)
    for i in range(2, len(post)):
        b = post.iloc[i]
        brk = 1 if b.close > hi else (-1 if b.close < lo else 0)
        if not brk:
            continue
        lo_i = max(0, i - 8)
        win = post.iloc[lo_i:i + 1]
        fvg = False
        for j in range(2, len(win)):
            if brk == 1 and win.iloc[j].low > win.iloc[j - 2].high:
                fvg = True
            if brk == -1 and win.iloc[j].high < win.iloc[j - 2].low:
                fvg = True
        if not fvg:
            return None
        e = b.close
        return brk, b.Date, e, e - brk * 30 / PIP, e + brk * 60 / PIP
    return None


def s_fib_pullback(g, dow):
    """Morning swing (10-14h); enter 61.8% retrace toward trend, tp = swing high/low."""
    am = g[(g.hh >= 10) & (g.hh < 14)]
    pm = g[(g.hh >= 14) & (g.hh <= 20)]
    if len(am) < 10 or len(pm) < 4:
        return None
    swing = (am.iloc[-1].close - am.iloc[0].open) * PIP
    if abs(swing) < 50:
        return None
    hi, lo = am.high.max(), am.low.min()
    if swing > 0:
        entry = hi - 0.618 * (hi - lo)
        touched = pm[pm.low <= entry]
        if touched.empty:
            return None
        t0 = touched.iloc[0].Date
        return 1, t0, entry, lo - 5 / PIP, hi
    entry = lo + 0.618 * (hi - lo)
    touched = pm[pm.high >= entry]
    if touched.empty:
        return None
    t0 = touched.iloc[0].Date
    return -1, t0, entry, hi + 5 / PIP, lo


def make_s_bias(fn):
    """Wrap any strategy: only take trades agreeing with day-of-week bias."""
    BIAS = {0: 1, 1: 1, 2: 1, 4: -1}

    def f(g, dow):
        r = fn(g, dow)
        if r is None or dow not in BIAS or r[0] != BIAS[dow]:
            return None
        return r
    return f


def main():
    for pair in ("GBPJPY", "AUDJPY"):
        m, d1 = load(pair)
        cost = COST[pair]
        print(f"\n================ {pair} (cost {cost} pips) ================")
        strats = [
            ("gap-fill Monday", lambda g, dw, _c=dict(zip(d1.date, d1.close)),
             _dates=sorted(d1.date): s_gapfill(g, dw, _c.get(
                 _dates[max(0, _dates.index(g.iloc[0].date) - 1)]
                 if g.iloc[0].date in _dates else None))),
            ("first-hour momentum 30/60", s_first_hour_momo),
            ("first-hour momo + day-bias", make_s_bias(s_first_hour_momo)),
            ("NY fade of London move", s_london_fade),
            ("Bollinger fade m15", s_bb_fade),
            ("prev-strong-day continuation", make_s_prevday_momo(d1)),
            ("Asian breakout + FVG confluence", s_breakout_fvg),
            ("breakout+FVG + day-bias", make_s_bias(s_breakout_fvg)),
            ("Fib 61.8 pullback", s_fib_pullback),
            ("Fib pullback + day-bias", make_s_bias(s_fib_pullback)),
        ]
        for name, fn in strats:
            try:
                rows = run_daily(m, fn)
                report(name, rows, cost)
            except Exception as e:
                print(f"{name:34s}  ERROR {e}")


if __name__ == "__main__":
    main()
