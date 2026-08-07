# Data provenance

| File | What it is | How to refresh |
|---|---|---|
| `ejtrader_gbpjpy_d1.csv`, `ejtrader_gbpjpy_h1.csv` | GBP/JPY OHLC (Dukascopy-derived, MT5 export), Nov 2012 – Mar 2022. Prices scaled ×1000 (132244 = 132.244). Timestamps in MT-server time (EET, UTC+2 winter / UTC+3 summer; London ≈ server − 2h). No Sunday bars; week = Mon 00:00 – Fri 23:59 server time. | `git clone --sparse https://github.com/ejtraderLabs/historical-data` (static archive, no longer updated) |
| `fred_gbp_usd.csv` | FRED `DEXUSUK` — USD per GBP, Fed H.10 noon-NY buying rates, 1971 → 2025-12-31 | FRED series DEXUSUK (mirrored in github.com/unbalancedparentheses/forex-centuries) |
| `fred_jpy_usd.csv` | FRED `DEXJPUS` — JPY per USD, same fixing | FRED series DEXJPUS |
| `capi_gbpjpy_2026.csv` | GBP→JPY daily ~00:00 UTC snapshots for 2026, extracted from the `@fawazahmed0/currency-api` npm package (one dated version per day) | see `analysis.py` docstring; download tarballs from registry.npmjs.org and read `package/v1/currencies/gbp.min.json` |
| `gbpjpy_daily_close_2021_2026.csv` | Output: stitched 5-year weekday close series used for the day-of-week stats. `source` column marks FRED vs currency-api rows; currency-api dates already shifted −1 day to label trading days. | regenerate with `python analysis.py` |

GBPJPY cross from FRED: `DEXUSUK × DEXJPUS`.

Cross-checks performed (see `results.json` → `crosscheck`): FRED cross vs Dukascopy daily closes on the 2021-08 → 2022-03 overlap: correlation 0.995, mean |diff| 0.11% (different daily fixing times).
