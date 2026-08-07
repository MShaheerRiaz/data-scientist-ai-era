"""GBP/JPY day-of-week & session analysis.

Data sources (see data/README.md for provenance):
- data/ejtrader_gbpjpy_d1.csv / _h1.csv : Dukascopy-derived OHLC, 2012-11 .. 2022-03,
  prices scaled x1000, timestamps in MT-server time (EET, UTC+2 winter / UTC+3 summer).
- data/fred_gbp_usd.csv (DEXUSUK), data/fred_jpy_usd.csv (DEXJPUS): Fed H.10 noon-NY
  rates, through 2025-12-31. GBPJPY cross = DEXUSUK * DEXJPUS.
- data/capi_gbpjpy_2026.csv : fawazahmed0/currency-api daily ~00:00 UTC snapshots for
  2026. A snapshot dated D is the price at the very start of D, i.e. the close of
  trading day D-1, so dates are shifted back one day to label trading days.

Outputs: charts/*.png, results.json (feeds dashboard + report).
"""

import json

import numpy as np
import pandas as pd

DOW = ["Mon", "Tue", "Wed", "Thu", "Fri"]
PIP = 100  # GBPJPY: 1 pip = 0.01 JPY
FIVE_Y_START = "2021-08-01"

results = {}


# ---------------------------------------------------------------- daily closes 5y
def load_daily_5y():
    gbp = pd.read_csv("data/fred_gbp_usd.csv", parse_dates=["observation_date"])
    jpy = pd.read_csv("data/fred_jpy_usd.csv", parse_dates=["observation_date"])
    fred = gbp.merge(jpy, on="observation_date").dropna()
    fred["close"] = fred.DEXUSUK * fred.DEXJPUS
    fred = fred.rename(columns={"observation_date": "date"})[["date", "close"]]
    fred["source"] = "FRED"

    capi = pd.read_csv("data/capi_gbpjpy_2026.csv", parse_dates=["date"])
    capi["date"] = capi.date - pd.Timedelta(days=1)  # snapshot -> trading day
    capi = capi.rename(columns={"gbpjpy": "close"})[["date", "close"]]
    capi = capi[capi.date.dt.dayofweek < 5]
    capi["source"] = "currency-api"
    capi = capi[capi.date > fred.date.max()]

    df = pd.concat([fred, capi], ignore_index=True).sort_values("date")
    df = df[df.date >= FIVE_Y_START].reset_index(drop=True)
    df["ret"] = np.log(df.close / df.close.shift(1)) * 100  # pct log return
    df["dow"] = df.date.dt.dayofweek
    df["year"] = df.date.dt.year
    return df.dropna()


def weekday_stats(g: pd.DataFrame, ret_col="ret") -> dict:
    r = g[ret_col]
    return {
        "n": int(len(g)),
        "mean_ret": round(float(r.mean()), 4),
        "median_ret": round(float(r.median()), 4),
        "std_ret": round(float(r.std()), 4),
        "pct_up": round(float((r > 0).mean() * 100), 1),
        "mean_abs_ret": round(float(r.abs().mean()), 4),
        "t_stat": round(float(r.mean() / (r.std() / np.sqrt(len(r)))), 2),
    }


def daily_5y_analysis(df):
    out = {"span": [str(df.date.min().date()), str(df.date.max().date())],
           "n_days": int(len(df)),
           "by_dow": {DOW[d]: weekday_stats(df[df.dow == d]) for d in range(5)}}
    # year-by-year mean return and mean abs return per weekday (consistency check)
    piv_ret = df.pivot_table(index="year", columns="dow", values="ret", aggfunc="mean").round(4)
    piv_abs = df.pivot_table(index="year", columns="dow", values="ret",
                             aggfunc=lambda s: s.abs().mean()).round(4)
    out["yearly_mean_ret"] = {str(y): [piv_ret.loc[y].get(d, np.nan) for d in range(5)]
                              for y in piv_ret.index}
    out["yearly_mean_abs"] = {str(y): [piv_abs.loc[y].get(d, np.nan) for d in range(5)]
                              for y in piv_abs.index}
    return out


# ---------------------------------------------------------------- OHLC daily (2012-2022)
def load_d1():
    d1 = pd.read_csv("data/ejtrader_gbpjpy_d1.csv", parse_dates=["Date"])
    for c in ["open", "high", "low", "close"]:
        d1[c] /= 1000
    d1["range_pips"] = (d1.high - d1.low) * PIP
    d1["ret"] = np.log(d1.close / d1.open) * 100  # intraday open->close
    d1["dow"] = d1.Date.dt.dayofweek
    d1["year"] = d1.Date.dt.year
    return d1[d1.dow < 5]


def d1_analysis(d1):
    def block(g):
        s = weekday_stats(g)
        s.update({
            "mean_range_pips": round(float(g.range_pips.mean()), 1),
            "median_range_pips": round(float(g.range_pips.median()), 1),
            "p95_range_pips": round(float(g.range_pips.quantile(0.95)), 1),
            "worst_drop_pct": round(float(g.ret.min()), 2),
        })
        return s
    out = {}
    for label, sub in [("full_2012_2022", d1), ("recent_2017_2022", d1[d1.year >= 2017])]:
        out[label] = {"span": [str(sub.Date.min().date()), str(sub.Date.max().date())],
                      "by_dow": {DOW[d]: block(sub[sub.dow == d]) for d in range(5)}}
    piv = d1.pivot_table(index="year", columns="dow", values="range_pips", aggfunc="mean").round(1)
    out["yearly_mean_range"] = {str(y): [piv.loc[y].get(d, np.nan) for d in range(5)]
                                for y in piv.index}
    return out


# ---------------------------------------------------------------- hourly (London time)
def load_h1():
    h1 = pd.read_csv("data/ejtrader_gbpjpy_h1.csv", parse_dates=["Date"])
    for c in ["open", "high", "low", "close"]:
        h1[c] /= 1000
    # MT-server time (EET-style, pegged to NY 17:00 close) -> London ~= server - 2h.
    h1["ldn"] = h1.Date - pd.Timedelta(hours=2)
    h1["hour"] = h1.ldn.dt.hour
    h1["dow"] = h1.ldn.dt.dayofweek
    h1["year"] = h1.ldn.dt.year
    h1["range_pips"] = (h1.high - h1.low) * PIP
    h1["move_pips"] = (h1.close - h1.open) * PIP
    return h1[h1.dow < 5]


SESSIONS = {  # London-time hour windows [start, end)
    "Asia (00-08)": (0, 8),
    "London AM (08-12)": (8, 12),
    "London/NY overlap (12-17)": (12, 17),
    "NY late (17-22)": (17, 22),
}


def h1_analysis(h1):
    out = {}
    for label, sub in [("full", h1), ("recent_2017_2022", h1[h1.year >= 2017])]:
        heat_range = sub.pivot_table(index="dow", columns="hour", values="range_pips",
                                     aggfunc="mean").round(1)
        heat_drift = sub.pivot_table(index="dow", columns="hour", values="move_pips",
                                     aggfunc="mean").round(2)
        out[label] = {
            "heat_range": [[heat_range.loc[d].get(h, np.nan) for h in range(24)] for d in range(5)],
            "heat_drift": [[heat_drift.loc[d].get(h, np.nan) for h in range(24)] for d in range(5)],
            "hourly_range": [round(float(sub[sub.hour == h].range_pips.mean()), 1) for h in range(24)],
        }
    # session stats per weekday: aggregate each session's net move & high-low span per day
    sess = {}
    for name, (a, b) in SESSIONS.items():
        w = h1[(h1.hour >= a) & (h1.hour < b)]
        day = w.groupby([w.ldn.dt.date, "dow"]).agg(
            o=("open", "first"), c=("close", "last"), hi=("high", "max"), lo=("low", "min"))
        day = day.reset_index()
        day["net_pips"] = (day.c - day.o) * PIP
        day["span_pips"] = (day.hi - day.lo) * PIP
        sess[name] = {DOW[d]: {
            "n": int((day.dow == d).sum()),
            "mean_span_pips": round(float(day[day.dow == d].span_pips.mean()), 1),
            "mean_net_pips": round(float(day[day.dow == d].net_pips.mean()), 1),
            "pct_up": round(float((day[day.dow == d].net_pips > 0).mean() * 100), 1),
            "std_net_pips": round(float(day[day.dow == d].net_pips.std()), 1),
        } for d in range(5)}
    out["sessions"] = sess
    return out


# ---------------------------------------------------------------- naive backtests
def backtest_daily_direction(df, dow, direction, split="2025-01-01"):
    """Hold one full day (close[t-1] -> close[t]) on the given weekday. Returns pct sums."""
    sub = df[df.dow == dow]
    sign = 1 if direction == "long" else -1
    ins, oos = sub[sub.date < split], sub[sub.date >= split]
    def side(s):
        r = s.ret * sign
        return {"n": int(len(r)), "total_pct": round(float(r.sum()), 2),
                "win_rate": round(float((r > 0).mean() * 100), 1),
                "mean_pct": round(float(r.mean()), 4),
                "sharpe_ann": round(float(r.mean() / r.std() * np.sqrt(52)), 2) if len(r) > 2 else None}
    return {"in_sample": side(ins), "out_of_sample": side(oos)}


def backtest_session_hold(h1, dow, a, b, direction, split_year=2020):
    w = h1[(h1.dow == dow) & (h1.hour >= a) & (h1.hour < b)]
    day = w.groupby(w.ldn.dt.date).agg(o=("open", "first"), c=("close", "last"))
    day.index = pd.to_datetime(day.index)
    day["net_pips"] = (day.c - day.o) * PIP * (1 if direction == "long" else -1)
    ins, oos = day[day.index.year < split_year], day[day.index.year >= split_year]
    def side(s):
        return {"n": int(len(s)), "total_pips": round(float(s.net_pips.sum()), 0),
                "win_rate": round(float((s.net_pips > 0).mean() * 100), 1),
                "mean_pips": round(float(s.net_pips.mean()), 1)}
    return {"in_sample": side(ins), "out_of_sample": side(oos)}


def main():
    df5 = load_daily_5y()
    d1 = load_d1()
    h1 = load_h1()

    # cross-check ejtrader daily close vs FRED cross on 2021-08..2022-03 overlap
    fred_overlap = df5[df5.date <= d1.Date.max()][["date", "close"]]
    ej = d1[d1.Date >= FIVE_Y_START][["Date", "close"]].rename(columns={"Date": "date", "close": "ej"})
    m = fred_overlap.merge(ej, on="date")
    results["crosscheck"] = {
        "n": int(len(m)),
        "mean_abs_diff_pct": round(float(((m.close - m.ej).abs() / m.ej * 100).mean()), 3),
        "corr": round(float(m.close.corr(m.ej)), 5),
    }

    results["daily_5y"] = daily_5y_analysis(df5)
    results["d1"] = d1_analysis(d1)
    results["h1"] = h1_analysis(h1)

    # edge candidates (defined AFTER inspecting stats; backtested IS/OOS)
    results["backtests"] = {
        "daily": {f"{DOW[d]}_{s}": backtest_daily_direction(df5, d, s)
                  for d in range(5) for s in ("long", "short")},
    }
    sess_bt = {}
    for d in range(5):
        for name, (a, b) in SESSIONS.items():
            for direction in ("long", "short"):
                sess_bt[f"{DOW[d]}|{name}|{direction}"] = backtest_session_hold(h1, d, a, b, direction)
    results["backtests"]["session"] = sess_bt

    with open("results.json", "w") as f:
        json.dump(results, f, indent=1, default=lambda o: None if pd.isna(o) else o)
    print("wrote results.json")

    df5.to_csv("data/gbpjpy_daily_close_2021_2026.csv", index=False)
    print("daily 5y rows:", len(df5), df5.date.min().date(), "->", df5.date.max().date())


if __name__ == "__main__":
    main()
