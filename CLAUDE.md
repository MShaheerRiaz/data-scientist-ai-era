# Daily SaaS & App Idea Scout — Project Context

This repository contains the **Daily SaaS & App Idea Scout** — a research routine that finds profitable SaaS/app ideas and validates them against failure history and live market data.

## The Routine

The full routine is in **`daily_saas_scout_routine.md`** — copy its contents to use as your Claude prompt.

### What it does (6 steps)

1. **Reddit** — scrapes r/SaaS, r/microsaas, r/startups, r/AppIdeas, r/SideProject, r/indiehackers for new ideas (Apify or WebSearch fallback)
2. **Twitter/X** — searches for building-in-public, MRR announcements, launched SaaS
3. **Revenue sources** — IndieHackers, ProductHunt, SaaSHub, Starter Story, Acquire.com
4. **TrustMRR** — fetches the live leaderboard (payment-verified MRR for 1,000+ startups) to identify hot categories and undervalued acquisitions
5. **startups.rip** — cross-checks each idea against 1,739+ failed YC startups so you know what was already tried, why it failed, and what to do differently
6. **14-point analysis** + ranked report written to `saas_ideas_report.md`

### Output: `saas_ideas_report.md` sections

- Executive summary (top 3 picks)
- All ideas ranked by viability (1–10)
- ⚠️ Failure Pattern Warnings (startups.rip data)
- 📈 TrustMRR Live Market Pulse + undervalued acquisitions
- ⚡ Quick Wins and 🚀 High Potential sections
- All sources used

## Python automation modules (optional)

These can be used programmatically if you want to automate the pipeline without Claude running it interactively:

```bash
cd analysis
# Run once for testing
python run_daily.py --now

# Loop daily at 08:00
python run_daily.py
```

Required env vars:
- `ANTHROPIC_API_KEY` — Claude API
- `APIFY_TOKEN` — for scraping JS-rendered sites (startups.rip, TrustMRR)

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
