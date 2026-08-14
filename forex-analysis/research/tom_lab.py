"""Tom Hougaard (TraderTom) setups translated to GBPJPY/AUDJPY and tested.

Source rules: his published manuals + channel-wide extraction of his strategy
videos (School Run breakout, FTSE 1st-bar trap, Fishing reversal, and his
"average price forward" pyramiding). His markets are DAX/Dow/FTSE with an
opening auction; forex has no auction, so "the open" is mapped to the London
open (08:00 UK = 10:00 server on this MT-style data, London = server - 2h).

Discipline identical to strategy_lab.py: in-sample 2012-2018, out-of-sample
2019-2022, costs included (3 pips GJ, 2 pips AJ per round trip, per tranche).
A setup survives only if net expectancy > 0 in BOTH splits.

Run from forex-analysis/:  python research/tom_lab.py
"""

import numpy as np
import pandas as pd

BASE = "/tmp/claude-0/-home-user-data-scientist-ai-era/eef445db-5aaa-5bd9-84d0-49793a7be370/scratchpad/ejtrader-data"
PIP = 100
COST = {"GBPJPY": 3, "AUDJPY": 2}
OOS_YEAR = 2019
LONDON_OPEN = 10.0          # server time
MORNING_END = 14.0          # 12:00 UK, Tom's morning window ends


def load(pair):
    m = pd.read_csv(f"{BASE}/{pair}/{pair}m15.csv", parse_dates=["Date"])
    h = pd.read_csv(f"{BASE}/{pair}/{pair}h1.csv", parse_dates=["Date"])
    d = pd.read_csv(f"{BASE}/{pair}/{pair}d1.csv", parse_dates=["Date"])
    for df in (m, h, d):
        for c in ("open", "high", "low", "close"):
            df[c] /= 1000
    for df in (m, h):
        df.drop(df[df.Date.dt.dayofweek >= 5].index, inplace=True)
        df["date"] = df.Date.dt.date
        df["hh"] = df.Date.dt.hour + df.Date.dt.minute / 60
    tr = np.maximum(d.high - d.low, np.maximum((d.high - d.close.shift()).abs(),
                    (d.low - d.close.shift()).abs()))
    d["atr"] = tr.rolling(14).mean().shift(1)
    d["date"] = d.Date.dt.date
    return m, h, d


def resolve(bars, side, entry, sl, tp=None):
    """Walk bars; -1R at stop, +R at tp if set, else mark-to-market at end."""
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


def report(name, rows, cost):
    if not rows:
        print(f"{name:38s}  no trades")
        return
    t = pd.DataFrame(rows, columns=["d", "R", "risk_pips"]).set_index("d")
    t["Rnet"] = t.R - cost / t.risk_pips
    line = f"{name:38s}"
    verdict = []
    for lbl, s in (("IS", t[t.index.year < OOS_YEAR]),
                   ("OOS", t[t.index.year >= OOS_YEAR])):
        if len(s) < 30:
            line += f"  {lbl}: n<30"
            verdict.append(False)
            continue
        line += (f"  {lbl}: n={len(s):4d} {s.Rnet.mean():+.3f}R "
                 f"w={100 * (s.Rnet > 0).mean():.0f}%")
        verdict.append(s.Rnet.mean() > 0)
    print(line + ("   << SURVIVES" if all(verdict) and len(verdict) == 2 else ""))


# ---- 1. School Run analog: bracket the 2nd 15m bar after London open -------
# (his 4th 5-min bar = minutes 15-20 after the open; the 2nd m15 bar
#  10:15-10:30 server is the closest object our data can build)
def s_school_run(g, dow):
    ref = g[(g.hh >= LONDON_OPEN + 0.25) & (g.hh < LONDON_OPEN + 0.5)]
    if ref.empty:
        return None
    hi, lo = ref.high.max(), ref.low.min()
    buf = 3 / PIP
    post = g[(g.hh >= LONDON_OPEN + 0.5) & (g.hh <= MORNING_END)]
    for _, b in post.iterrows():
        if b.high >= hi + buf:
            e = hi + buf
            return 1, b.Date, e, lo - buf, None
        if b.low <= lo - buf:
            e = lo - buf
            return -1, b.Date, e, hi + buf, None
    return None


# ---- 2. FTSE 1st-bar trap analog: first 15m bar of London ------------------
def s_first_bar_trap(g, dow):
    ref = g[(g.hh >= LONDON_OPEN) & (g.hh < LONDON_OPEN + 0.25)]
    if ref.empty:
        return None
    b0 = ref.iloc[0]
    buf = 3 / PIP
    post = g[(g.hh >= LONDON_OPEN + 0.25) & (g.hh <= MORNING_END)]
    for _, b in post.iterrows():
        if b.low <= b0.low - buf:
            e = b0.low - buf
            if b0.close > b0.open:       # positive 1st bar -> reversal short
                return -1, b.Date, e, b0.high + buf, None
            return 1, b.Date, e, e - 15 / PIP, None   # negative bar -> trap long
    return None


# ---- 3. Fishing reversal on h1: close beyond the extreme bar of the swing --
def make_s_fishing(h1):
    h1 = h1.reset_index(drop=True)
    by_date = {}
    for i, r in h1.iterrows():
        by_date.setdefault(r.date, []).append(i)

    def f(g, dow):
        day = g.iloc[0].date
        idxs = by_date.get(day)
        if not idxs:
            return None
        for i in idxs:
            b = h1.iloc[i]
            if not (LONDON_OPEN <= b.hh <= 18):
                continue
            w = h1.iloc[max(0, i - 12):i]           # last 12 h1 bars
            if len(w) < 12:
                continue
            trend = w.iloc[-1].close - w.iloc[0].close
            if trend < -0.30 * abs(w.close).mean() / 100:   # downswing
                lowest = w.loc[w.low.idxmin()]
                if b.close > lowest.high:
                    e = b.close
                    return 1, b.Date, e, lowest.low - 3 / PIP, None
            elif trend > 0.30 * abs(w.close).mean() / 100:  # upswing
                highest = w.loc[w.high.idxmax()]
                if b.close < highest.low:
                    e = b.close
                    return -1, b.Date, e, highest.high + 3 / PIP, None
        return None
    return f


def run_daily(m, fn, cutoff=21):
    out = []
    for day, g in m.groupby("date"):
        g = g.sort_values("Date")
        r = fn(g, pd.Timestamp(day).dayofweek)
        if r is None:
            continue
        side, t0, entry, sl, tp = r
        after = g[(g.Date > t0) & (g.hh <= cutoff)]
        out.append((pd.Timestamp(day), resolve(after, side, entry, sl, tp),
                    abs(entry - sl) * PIP))
    return out


# ---- 4. Pyramiding the Monday long (his "average price forward") -----------
def monday_pyramid(h1, d1, cost, add_at_r):
    """Base: buy Mon 00:00, ATR*1.5 stop, exit 23:00.
    Pyramid: when h1 high reaches entry + add_at_r*risk, add 1x at that level,
    move tranche-1 stop to breakeven, tranche-2 stop also at original entry.
    Worst-case fill order assumed inside the trigger bar."""
    atr = dict(zip(d1.date, d1.atr))
    base_rows, pyr_rows = [], []
    for day, g in h1.groupby("date"):
        if pd.Timestamp(day).dayofweek != 0:
            continue
        g = g.sort_values("Date")
        first = g.iloc[0]
        if first.hh > 1:
            continue
        a = atr.get(day)
        if a is None or np.isnan(a):
            continue
        entry = first.open
        risk = a * 1.5
        sl = entry - risk
        add_lvl = entry + add_at_r * risk
        bars = g[g.hh <= 23]
        # base result
        r1 = resolve(bars, 1, entry, sl)
        base_rows.append((pd.Timestamp(day), r1, risk * PIP))
        # pyramid walk
        added = False
        out = None
        for _, b in bars.iterrows():
            if not added:
                if b.low <= sl:
                    out = -1.0                       # stopped before add
                    break
                if b.high >= add_lvl:
                    added = True
                    if b.low <= entry and b.close < add_lvl:
                        out = 0.0 - add_at_r         # worst case: add then BE-stop
                        break
            else:
                if b.low <= entry:                    # both stops at orig entry
                    out = 0.0 - add_at_r
                    break
        if out is None:
            last = bars.iloc[-1].close
            out = (last - entry) / risk + (added and (last - add_lvl) / risk or 0.0)
        n_tranches = 2 if added else 1
        pyr_rows.append((pd.Timestamp(day), out, risk * PIP, n_tranches))
    return base_rows, pyr_rows


def pyramid_report(pair, base_rows, pyr_rows, cost, add_at_r):
    b = pd.DataFrame(base_rows, columns=["d", "R", "risk"]).set_index("d")
    p = pd.DataFrame(pyr_rows, columns=["d", "R", "risk", "tr"]).set_index("d")
    b["Rnet"] = b.R - cost / b.risk
    p["Rnet"] = p.R - p.tr * cost / p.risk
    print(f"\n  {pair} Monday long, add at +{add_at_r}R "
          f"(adds fired on {100 * (p.tr == 2).mean():.0f}% of Mondays)")
    for lbl, yr0, yr1 in (("IS ", 0, OOS_YEAR), ("OOS", OOS_YEAR, 9999)):
        bs = b[(b.index.year >= yr0) & (b.index.year < yr1)]
        ps = p[(p.index.year >= yr0) & (p.index.year < yr1)]
        print(f"    {lbl}: base {bs.Rnet.mean():+.3f}R/trade   "
              f"pyramid {ps.Rnet.mean():+.3f}R/trade   "
              f"(n={len(bs)}, pyramid worst {ps.Rnet.min():+.2f}R)")


def main():
    for pair in ("GBPJPY", "AUDJPY"):
        m, h, d1 = load(pair)
        cost = COST[pair]
        print(f"\n================ {pair} (cost {cost} pips/tranche) ================")
        for name, fn in (
            ("School Run (2nd m15 bar bracket)", s_school_run),
            ("1st-bar trap (London open)", s_first_bar_trap),
            ("Fishing reversal (h1 swing)", make_s_fishing(h)),
        ):
            try:
                report(name, run_daily(m, fn), cost)
            except Exception as e:
                print(f"{name:38s}  ERROR {e}")
        for add_at in (0.25, 0.5):
            base_rows, pyr_rows = monday_pyramid(h, d1, cost, add_at)
            pyramid_report(pair, base_rows, pyr_rows, cost, add_at)


if __name__ == "__main__":
    main()
