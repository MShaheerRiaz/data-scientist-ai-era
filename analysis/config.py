import os
from pathlib import Path

# ── API Keys ─────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
APIFY_TOKEN       = os.environ.get("APIFY_TOKEN", "")

# ── Scheduling ───────────────────────────────────────────────────────────────
# Time to run the daily report (24h HH:MM, local machine time)
DAILY_RUN_TIME = os.environ.get("DAILY_RUN_TIME", "08:00")

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "reports"
STATE_FILE  = BASE_DIR / ".state.json"

REPORTS_DIR.mkdir(exist_ok=True)

# ── Idea Sources ──────────────────────────────────────────────────────────────
REDDIT_SUBREDDITS  = ["SaaS", "microsaas", "startups", "entrepreneur", "indiehackers"]
REDDIT_POST_LIMIT  = 50   # newest posts fetched per subreddit
HN_STORY_LIMIT     = 100  # Show HN story IDs to evaluate

# ── Scoring ───────────────────────────────────────────────────────────────────
MIN_REPORT_SCORE = 5   # only include ideas that score >= this in the report

# ── HTTP ─────────────────────────────────────────────────────────────────────
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; SaaSRadar/1.0; +https://github.com/MShaheerRiaz)"
    )
}
REQUEST_TIMEOUT = 15   # seconds for direct HTTP calls
APIFY_TIMEOUT   = 90   # seconds for Apify actor calls

# ── Keyword filters (used before Claude to save cost) ─────────────────────────
IDEA_KEYWORDS = [
    "built", "launched", "made", "created", "released", "shipped",
    "saas", "mrr", "arr", "tool", "app", "software", "platform",
    "side project", "indie", "revenue", "subscribers", "paying customers",
    "show hn", "product", "startup",
]
SKIP_KEYWORDS = [
    "hiring", "looking for", "internship", "job offer", "funding round",
    "we are hiring", "apply now", "cofounder wanted",
]
