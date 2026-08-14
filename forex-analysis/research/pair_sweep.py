"""Full-universe intraday strategy sweep: every setup x every FTMO-tradable
instrument in the Dukascopy dataset (11 FX pairs + gold), 2012-2022.

Setups: Monday gap-fill, Tom Hougaard's School Run / 1st-bar trap / fishing
reversal, first-hour momentum, NY fade, Bollinger fade, prev-strong-day
continuation. Same discipline as strategy_lab.py: IS 2012-2018, OOS 2019-2022,
net of realistic round-trip cost, survives only if positive in BOTH splits.
Survivors then get a deployability check (equity max drawdown in R).

Run from forex-analysis/:  python research/pair_sweep.py
"""

import numpy as np
import pandas as pd

BASE = "/tmp/claude-0/-home-user-data-scientist-ai-era/eef445db-5aaa-5bd9-84d0-49793a7be370/scratchpad/ejtrader-data"
OOS_YEAR = 2019
LONDON_OPEN = 10.0
MORNING_END = 14.0

# pip size (price units), realistic round-trip cost in pips, and raw-price
# divisor (repo stores ints: JPY pairs x1000, 5-digit pairs x100000, gold x100)
SPEC = {
    "EURUSD": (0.0001, 1.2, 1e5), "GBPUSD": (0.0001, 1.8, 1e5),
    "AUDUSD": (0.0001, 1.2, 1e5), "USDCAD": (0.0001, 1.8, 1e5),
    "USDCHF": (0.0001, 1.8, 1e5), "EURGBP": (0.0001, 1.8, 1e5),
    "EURCHF": (0.0001, 2.0, 1e5), "USDJPY": (0.01, 1.2, 1e3),
    "EURJPY": (0.01, 2.0, 1e3), "GBPJPY": (0.01, 3.0, 1e3),
    "AUDJPY": (0.01, 2.0, 1e3), "XAUUSD": (0.1, 3.5, 1e2),
}


def load(pair, pip, div=1e3):
    m = pd.read_csv(f"{BASE}/{pair}/{pair}m15.csv", parse_dates=["Date"])
    h = pd.read_csv(f"{BASE}/{pair}/{pair}h1.csv", parse_dates=["Date"])
    d = pd.read_csv(f"{BASE}/{pair}/{pair}d1.csv", parse_dates=["Date"])
    for df in (m, h, d):
        for c in ("open", "high", "low", "close"):
            df[c] /= div
    for df in (m, h):
        df.drop(df[df.Date.dt.dayofweek >= 5].index, inplace=True)
        df["date"] = df.Date.dt.date
        df["hh"] = df.Date.dt.hour + df.Date.dt.minute / 60
    d["date"] = d.Date.dt.date
    return m, h, d


def resolve(bars, side, entry, sl, tp=None):
    risk = abs(entry - sl)
    for _, c in bars.iterrows():
        if side == 1:
            if c.low <= sl:
                return -1.0
            if tp is not None and c.high >= tp:
                return (tp - entry) / risk
        else:
            if c.high >= sl:
                return -1.0
            if tp is not None and c.low <= tp:
                return (entry - tp) / risk
    if len(bars):
        return side * (bars.iloc[-1].close - entry) / risk
    return 0.0


def run_daily(m, fn, pip, cutoff=21):
    out = []
    for day, g in m.groupby("date"):
        g = g.sort_values("Date")
        r = fn(g, pd.Timestamp(day).dayofweek)
        if r is None:
            continue
        side, t0, entry, sl, tp = r[:5]
        stop_entry = len(r) > 5 and r[5]
        after = g[(g.Date > t0) & (g.hh <= cutoff)]
        if stop_entry:
            # entry filled by a stop order inside bar t0: worst case, if that
            # bar's range also covers the SL, count the trade as stopped
            b0 = g[g.Date == t0]
            if len(b0):
                b0 = b0.iloc[0]
                if (side == 1 and b0.low <= sl) or (side == -1 and b0.high >= sl):
                    out.append((pd.Timestamp(day), -1.0, abs(entry - sl) / pip))
                    continue
        out.append((pd.Timestamp(day), resolve(after, side, entry, sl, tp),
                    abs(entry - sl) / pip))
    return out


def stats(rows, cost):
    """Return (is_mean, oos_mean, n_is, n_oos, survives, maxdd_R) net of cost."""
    if not rows:
        return None
    t = pd.DataFrame(rows, columns=["d", "R", "risk"]).set_index("d").sort_index()
    t["Rnet"] = t.R - cost / t.risk
    ins = t[t.index.year < OOS_YEAR]
    oos = t[t.index.year >= OOS_YEAR]
    if len(ins) < 30 or len(oos) < 30:
        return None
    eq = t.Rnet.cumsum()
    dd = (eq - eq.cummax()).min()
    surv = ins.Rnet.mean() > 0 and oos.Rnet.mean() > 0
    return ins.Rnet.mean(), oos.Rnet.mean(), len(ins), len(oos), surv, dd


# ------------------------------ setups --------------------------------------
def make_gapfill(d1, pip):
    cl = dict(zip(d1.date, d1.close))
    dates = sorted(cl)
    idx = {dt: i for i, dt in enumerate(dates)}

    def f(g, dow):
        if dow != 0:
            return None
        day = g.iloc[0].date
        i = idx.get(day)
        if not i:
            return None
        prev = cl[dates[i - 1]]
        o = g.iloc[0]
        gap = (o.open - prev) / pip
        if abs(gap) < 15 or abs(gap) > 120:
            return None
        side = -1 if gap > 0 else 1
        entry = o.open
        sl = entry - side * abs(entry - prev)
        return side, o.Date, entry, sl, prev
    return f


def make_school_run(pip):
    def f(g, dow):
        ref = g[(g.hh >= LONDON_OPEN + 0.25) & (g.hh < LONDON_OPEN + 0.5)]
        if ref.empty:
            return None
        hi, lo = ref.high.max(), ref.low.min()
        buf = 3 * pip
        post = g[(g.hh >= LONDON_OPEN + 0.5) & (g.hh <= MORNING_END)]
        for _, b in post.iterrows():
            if b.high >= hi + buf:
                return 1, b.Date, hi + buf, lo - buf, None, True
            if b.low <= lo - buf:
                return -1, b.Date, lo - buf, hi + buf, None, True
        return None
    return f


def make_first_bar_trap(pip):
    def f(g, dow):
        ref = g[(g.hh >= LONDON_OPEN) & (g.hh < LONDON_OPEN + 0.25)]
        if ref.empty:
            return None
        b0 = ref.iloc[0]
        buf = 3 * pip
        post = g[(g.hh >= LONDON_OPEN + 0.25) & (g.hh <= MORNING_END)]
        for _, b in post.iterrows():
            if b.low <= b0.low - buf:
                e = b0.low - buf
                if b0.close > b0.open:
                    return -1, b.Date, e, b0.high + buf, None, True
                return 1, b.Date, e, e - 15 * pip, None, True
        return None
    return f


def make_first_hour_momo(pip):
    def f(g, dow):
        fh = g[(g.hh >= LONDON_OPEN) & (g.hh < LONDON_OPEN + 1)]
        if len(fh) < 3:
            return None
        mv = (fh.iloc[-1].close - fh.iloc[0].open) / pip
        if abs(mv) < 15:
            return None
        side = 1 if mv > 0 else -1
        e = fh.iloc[-1].close
        return side, fh.iloc[-1].Date, e, e - side * 30 * pip, e + side * 60 * pip
    return f


def make_ny_fade(pip):
    def f(g, dow):
        ld = g[(g.hh >= LONDON_OPEN) & (g.hh < 15)]
        if len(ld) < 10:
            return None
        mv = (ld.iloc[-1].close - ld.iloc[0].open) / pip
        if abs(mv) < 70:
            return None
        side = -1 if mv > 0 else 1
        e = ld.iloc[-1].close
        ext = ld.high.max() if mv > 0 else ld.low.min()
        sl = ext + 10 * pip * (1 if mv > 0 else -1)
        tp = e + side * abs(mv) * 0.5 * pip
        return side, ld.iloc[-1].Date, e, sl, tp
    return f


def make_bb_fade(pip):
    def f(g, dow):
        g = g.copy()
        g["ma"] = g.close.rolling(20).mean()
        g["sd"] = g.close.rolling(20).std()
        ldn = g[(g.hh >= LONDON_OPEN) & (g.hh <= 18)]
        for _, b in ldn.iterrows():
            if np.isnan(b.ma):
                continue
            up, dn = b.ma + 2 * b.sd, b.ma - 2 * b.sd
            if b.close > up:
                return -1, b.Date, b.close, b.close + 25 * pip, b.ma
            if b.close < dn:
                return 1, b.Date, b.close, b.close - 25 * pip, b.ma
        return None
    return f


def make_prevday(d1, pip):
    cl = dict(zip(d1.date, d1.close))
    op = dict(zip(d1.date, d1.open))
    dates = sorted(cl)
    prev = {dates[i]: dates[i - 1] for i in range(1, len(dates))}

    def f(g, dow):
        p = prev.get(g.iloc[0].date)
        if p is None:
            return None
        mv = (cl[p] - op[p]) / pip
        if abs(mv) < 60:
            return None
        side = 1 if mv > 0 else -1
        o = g.iloc[0]
        return side, o.Date, o.open, o.open - side * 40 * pip, o.open + side * 80 * pip
    return f


def make_fishing(h1, pip):
    h1 = h1.reset_index(drop=True)
    by_date = {}
    for i, r in h1.iterrows():
        by_date.setdefault(r.date, []).append(i)

    def f(g, dow):
        idxs = by_date.get(g.iloc[0].date)
        if not idxs:
            return None
        for i in idxs:
            b = h1.iloc[i]
            if not (LONDON_OPEN <= b.hh <= 18):
                continue
            w = h1.iloc[max(0, i - 12):i]
            if len(w) < 12:
                continue
            rng = (w.high.max() - w.low.min())
            trend = w.iloc[-1].close - w.iloc[0].close
            if trend < -0.5 * rng:
                lowest = w.loc[w.low.idxmin()]
                if b.close > lowest.high:
                    return 1, b.Date, b.close, lowest.low - 3 * pip, None
            elif trend > 0.5 * rng:
                highest = w.loc[w.high.idxmax()]
                if b.close < highest.low:
                    return -1, b.Date, b.close, highest.high + 3 * pip, None
        return None
    return f


def main():
    results = []
    for pair, (pip, cost, div) in SPEC.items():
        try:
            m, h, d1 = load(pair, pip, div)
        except FileNotFoundError:
            print(f"{pair}: no data, skipped")
            continue
        setups = {
            "gap-fill Mon": make_gapfill(d1, pip),
            "school-run": make_school_run(pip),
            "1st-bar trap": make_first_bar_trap(pip),
            "1h momentum": make_first_hour_momo(pip),
            "NY fade": make_ny_fade(pip),
            "BB fade": make_bb_fade(pip),
            "prev-day cont": make_prevday(d1, pip),
            "fishing rev": make_fishing(h, pip),
        }
        for name, fn in setups.items():
            src = h if name == "fishing rev" else m
            try:
                s = stats(run_daily(src, fn, pip), cost)
            except Exception as e:
                print(f"{pair} {name}: ERROR {e}")
                continue
            if s is None:
                continue
            is_m, oos_m, n_is, n_oos, surv, dd = s
            results.append((pair, name, is_m, oos_m, n_is + n_oos, surv, dd))
            flag = "  << SURVIVES" if surv else ""
            print(f"{pair:7s} {name:14s} IS {is_m:+.3f}R  OOS {oos_m:+.3f}R  "
                  f"n={n_is + n_oos:5d}  maxDD {dd:6.1f}R{flag}", flush=True)
    print("\n=== SURVIVORS (positive IS and OOS) ===")
    for pair, name, is_m, oos_m, n, surv, dd in results:
        if surv:
            print(f"{pair:7s} {name:14s} IS {is_m:+.3f}R OOS {oos_m:+.3f}R "
                  f"n={n} maxDD {dd:.1f}R")


if __name__ == "__main__":
    main()
