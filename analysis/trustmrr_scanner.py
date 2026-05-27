"""
TrustMRR market intelligence module.

Fetches the TrustMRR leaderboard and for-sale listings, then uses Claude
to extract structured market data and validate whether a given idea has
traction in the current market.
"""

import json
import logging
import time
import requests
import anthropic

from config import ANTHROPIC_API_KEY, APIFY_TOKEN, APIFY_TIMEOUT, DEFAULT_HEADERS

log = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

APIFY_URL = "https://api.apify.com/v2/acts/apify~rag-web-browser/run-sync-get-dataset-items"


# ── Apify fetch ───────────────────────────────────────────────────────────────

def _apify_fetch(url: str) -> str:
    """Fetch a JS-rendered page via Apify RAG web browser. Returns markdown."""
    if not APIFY_TOKEN:
        log.warning("APIFY_TOKEN not set — skipping TrustMRR fetch")
        return ""
    try:
        resp = requests.post(
            APIFY_URL,
            params={"token": APIFY_TOKEN},
            json={"query": url, "maxResults": 1, "outputFormats": ["markdown"]},
            timeout=APIFY_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            return data[0].get("markdown", "")
    except Exception as exc:
        log.error("Apify fetch failed for %s: %s", url, exc)
    return ""


# ── Claude extraction ─────────────────────────────────────────────────────────

def _parse_market_data(markdown: str) -> dict:
    """
    Use Claude to extract structured leaderboard + for-sale data from
    the TrustMRR markdown page dump.
    """
    if not client or not markdown:
        return {"leaderboard": [], "for_sale": [], "categories": []}

    prompt = (
        "Extract structured data from this TrustMRR page content.\n\n"
        "Return ONLY a JSON object with these keys:\n"
        "- leaderboard: list of top startups [{name, mrr_usd, mom_growth_pct, category, for_sale}]\n"
        "  mrr_usd = integer (e.g. 3569654). mom_growth_pct = float or null if '_'.\n"
        "  for_sale = true/false based on 'FOR SALE' label.\n"
        "- for_sale: list of acquisition listings [{name, revenue_usd, asking_price_usd, "
        "multiple_x, category}] from the 'Recently listed' / 'Best deals' sections.\n"
        "  All prices as integers (e.g. $8.1k → 8100, $175k → 175000).\n"
        "- hot_categories: list of categories with multiple startups showing growth "
        "[{name, startup_count, avg_mrr_usd, avg_mom_growth_pct}]\n\n"
        "Content:\n" + markdown[:12000]
    )

    for attempt in range(2):
        try:
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            return json.loads(text.strip())
        except (json.JSONDecodeError, Exception) as exc:
            log.warning("Claude market parse attempt %d failed: %s", attempt + 1, exc)
            time.sleep(2)

    return {"leaderboard": [], "for_sale": [], "hot_categories": []}


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_market_snapshot() -> dict:
    """
    Fetch live TrustMRR market data.

    Returns:
        {
          "leaderboard": [{name, mrr_usd, mom_growth_pct, category, for_sale}],
          "for_sale": [{name, revenue_usd, asking_price_usd, multiple_x, category}],
          "hot_categories": [{name, startup_count, avg_mrr_usd, avg_mom_growth_pct}],
          "available": bool,
        }
    """
    log.info("Fetching TrustMRR market snapshot…")
    markdown = _apify_fetch("https://trustmrr.com/")
    if not markdown:
        return {"leaderboard": [], "for_sale": [], "hot_categories": [], "available": False}

    data = _parse_market_data(markdown)
    data["available"] = bool(data.get("leaderboard"))
    log.info(
        "TrustMRR: %d leaderboard, %d for-sale, %d hot categories",
        len(data.get("leaderboard", [])),
        len(data.get("for_sale", [])),
        len(data.get("hot_categories", [])),
    )
    return data


def get_market_context(idea_description: str, market_data: dict) -> dict:
    """
    Use the cached market snapshot to validate an idea.

    Returns:
        {
          "similar_products": [{name, mrr_usd, mom_growth_pct}],
          "matching_category": str | None,
          "category_health": "hot" | "warm" | "cold" | "unknown",
          "market_signal": str,   # short human-readable summary
        }
    """
    if not client or not market_data.get("available"):
        return {
            "similar_products": [],
            "matching_category": None,
            "category_health": "unknown",
            "market_signal": "TrustMRR data unavailable.",
        }

    leaderboard_summary = json.dumps(market_data.get("leaderboard", [])[:30], indent=2)
    categories_summary  = json.dumps(market_data.get("hot_categories", []), indent=2)

    prompt = (
        f"IDEA: {idea_description}\n\n"
        f"TRUSTMRR LEADERBOARD (top 30):\n{leaderboard_summary}\n\n"
        f"HOT CATEGORIES:\n{categories_summary}\n\n"
        "Tasks:\n"
        "1. Find startups in the leaderboard that are in the same space as the idea (similar products).\n"
        "2. Identify the matching category.\n"
        "3. Rate category health: 'hot' (multiple products >$30k MRR with growth), "
        "'warm' (some products, moderate growth), 'cold' (no similar), 'unknown'.\n"
        "4. Write a 1-sentence market signal summary.\n\n"
        "Return ONLY JSON:\n"
        '{"similar_products": [{name: str, mrr_usd: int, mom_growth_pct: float_or_null}], '
        '"matching_category": str_or_null, "category_health": str, "market_signal": str}'
    )

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        return json.loads(text.strip())
    except Exception as exc:
        log.error("get_market_context failed: %s", exc)
        return {
            "similar_products": [],
            "matching_category": None,
            "category_health": "unknown",
            "market_signal": "Market context analysis failed.",
        }


def get_undervalued_opportunities(market_data: dict) -> list[dict]:
    """
    Return FOR SALE listings that look undervalued (multiple < 1.5x or
    high revenue relative to asking price).
    """
    opportunities = []
    for item in market_data.get("for_sale", []):
        multiple = item.get("multiple_x")
        revenue  = item.get("revenue_usd", 0)
        asking   = item.get("asking_price_usd", 0)
        if multiple is not None and multiple < 1.5 and revenue > 500:
            item["why_interesting"] = (
                f"{multiple}x multiple is well below the 2–4x market norm. "
                f"Verified ${revenue:,}/mo revenue at ${asking:,} asking."
            )
            opportunities.append(item)
    return sorted(opportunities, key=lambda x: x.get("revenue_usd", 0), reverse=True)
