# SaaS Radar — Project Context

This repository contains a daily automated SaaS opportunity intelligence system.

## What this project does

Every day it:
1. Scrapes Reddit (`r/SaaS`, `r/microsaas`, `r/startups`) and Hacker News Show HN for new startup ideas
2. Cross-checks each idea against **startups.rip** — a database of 1,739+ failed YC startups — to see if the idea already failed and why
3. Validates each idea against **TrustMRR** live market data — verified MRR leaderboard and for-sale listings
4. Scores each idea 1–10 with Claude and generates a ranked report

## Running the daily routine

```bash
cd analysis

# Run once (testing)
python run_daily.py --now

# Run now + loop daily at 08:00
python run_daily.py

# Custom time
python run_daily.py --time 07:30
```

Required env vars:
- `ANTHROPIC_API_KEY` — Claude API
- `APIFY_TOKEN` — for scraping startups.rip and TrustMRR (JS-rendered sites)

## File map

| File | Role |
|---|---|
| `analysis/run_daily.py` | Entry point + scheduler |
| `analysis/daily_runner.py` | Orchestrator — ties everything together |
| `analysis/idea_finder.py` | Reddit + HN scraper (Apify fallback built in) |
| `analysis/startup_checker.py` | startups.rip cross-check via Apify |
| `analysis/trustmrr_scanner.py` | TrustMRR market intelligence |
| `analysis/config.py` | All settings (subreddits, thresholds, schedule time) |
| `analysis/reports/` | Daily output — `YYYY-MM-DD.md` + `.json` |
| `analysis/.state.json` | Seen-ID deduplication across runs (auto-created) |

## Integration with existing routines

The main callable is:

```python
from daily_runner import run
report_path = run()   # returns path to today's saved report
```

Each idea in the output JSON (`reports/YYYY-MM-DD.json`) has this shape:

```json
{
  "idea_name": "...",
  "idea_description": "...",
  "source": "r/microsaas",
  "source_url": "...",
  "score": 8,
  "verdict": "...",
  "recommended_angle": "...",
  "rip": { "found": true, "similar_company": "...", "why_failed": [...] },
  "market": { "category_health": "hot", "market_signal": "..." }
}
```

## Adding new idea sources

Add a new fetcher to `analysis/idea_finder.py` that returns a list of dicts:
```python
{"id": str, "title": str, "body": str, "source": str, "url": str}
```
Then append the results to `all_posts` inside `fetch_new_ideas()`.
