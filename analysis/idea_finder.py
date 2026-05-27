"""
Idea discovery module.

Scrapes Reddit and Hacker News for newly posted SaaS/startup ideas,
filters by relevance keywords, then uses Claude (one batch call) to
extract structured idea objects from the surviving posts.

Fallback: if direct Reddit/HN requests are blocked (e.g. in a restricted
network), the module falls back to Apify for Reddit scraping.
"""

import json
import logging
import time
import requests
import anthropic

from config import (
    ANTHROPIC_API_KEY,
    APIFY_TOKEN,
    REDDIT_SUBREDDITS,
    REDDIT_POST_LIMIT,
    HN_STORY_LIMIT,
    DEFAULT_HEADERS,
    REQUEST_TIMEOUT,
    APIFY_TIMEOUT,
    IDEA_KEYWORDS,
    SKIP_KEYWORDS,
)

APIFY_URL = "https://api.apify.com/v2/acts/apify~rag-web-browser/run-sync-get-dataset-items"

log = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_relevant(title: str, text: str) -> bool:
    combined = (title + " " + text).lower()
    if any(k in combined for k in SKIP_KEYWORDS):
        return False
    return any(k in combined for k in IDEA_KEYWORDS)


def _safe_get(url: str, **kwargs) -> dict | list | None:
    """GET with retry (up to 3 attempts, exponential backoff)."""
    for attempt in range(3):
        try:
            resp = requests.get(
                url, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT, **kwargs
            )
            if resp.status_code == 429:
                wait = 2 ** attempt * 5
                log.warning("Rate limited on %s — waiting %ds", url, wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            log.warning("Request failed (attempt %d): %s — %s", attempt + 1, url, exc)
            time.sleep(2 ** attempt)
    return None


# ── Apify fallback ────────────────────────────────────────────────────────────

def _apify_fetch_markdown(url: str) -> str:
    """Fetch a page via Apify when direct requests are blocked."""
    if not APIFY_TOKEN:
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
        log.warning("Apify fallback failed for %s: %s", url, exc)
    return ""


def _parse_reddit_posts_from_markdown(markdown: str, subreddit: str, seen_ids: set[str]) -> list[dict]:
    """Extract post info from Apify-scraped Reddit markdown."""
    posts = []
    lines = markdown.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Reddit posts typically appear as markdown headers or bold links
        if line.startswith("###") or (line.startswith("**") and "comments" in markdown[markdown.find(line):markdown.find(line)+200].lower()):
            title = line.lstrip("#").strip().strip("*")
            if not _is_relevant(title, ""):
                i += 1
                continue
            # Create a pseudo-ID from the title hash
            pid = f"reddit_{subreddit}_{abs(hash(title)) % 1_000_000}"
            if pid not in seen_ids and len(title) > 10:
                posts.append({
                    "id":          pid,
                    "title":       title,
                    "body":        "",
                    "source":      f"r/{subreddit}",
                    "url":         f"https://reddit.com/r/{subreddit}/new/",
                    "score":       0,
                    "created_utc": 0,
                })
        i += 1
    return posts[:20]


# ── Reddit ────────────────────────────────────────────────────────────────────

def _fetch_reddit(subreddits: list[str], seen_ids: set[str]) -> list[dict]:
    """Fetch new posts from given subreddits, skip already-seen IDs."""
    raw = []
    for sub in subreddits:
        api_url = f"https://www.reddit.com/r/{sub}/new.json"
        data    = _safe_get(api_url, params={"limit": REDDIT_POST_LIMIT})

        if data:
            # Direct Reddit JSON API worked
            posts = data.get("data", {}).get("children", [])
            for post in posts:
                p   = post.get("data", {})
                pid = f"reddit_{p.get('id', '')}"
                if pid in seen_ids:
                    continue
                title = p.get("title", "")
                text  = p.get("selftext", "")
                if not _is_relevant(title, text):
                    continue
                raw.append({
                    "id":          pid,
                    "title":       title,
                    "body":        text[:500],
                    "source":      f"r/{sub}",
                    "url":         f"https://reddit.com{p.get('permalink', '')}",
                    "score":       p.get("score", 0),
                    "created_utc": p.get("created_utc", 0),
                })
        else:
            # Fall back to Apify if direct request is blocked
            log.info("Reddit API blocked for r/%s — trying Apify fallback", sub)
            md = _apify_fetch_markdown(f"https://www.reddit.com/r/{sub}/new/")
            if md:
                apify_posts = _parse_reddit_posts_from_markdown(md, sub, seen_ids)
                raw.extend(apify_posts)
                log.info("Apify fallback: %d posts from r/%s", len(apify_posts), sub)

        time.sleep(1)  # be polite to Reddit
    log.info("Reddit: %d relevant posts from %s", len(raw), subreddits)
    return raw


# ── Hacker News ───────────────────────────────────────────────────────────────

def _fetch_hn(seen_ids: set[str]) -> list[dict]:
    """Fetch recent Show HN stories. Falls back to Apify if direct request blocked."""
    story_ids = _safe_get(
        "https://hacker-news.firebaseio.com/v0/showstories.json"
    )
    if not story_ids:
        # Apify fallback for HN
        log.info("HN API blocked — trying Apify fallback")
        md = _apify_fetch_markdown("https://news.ycombinator.com/show")
        if md:
            return _parse_hn_from_markdown(md, seen_ids)
        return []

    raw = []
    for sid in story_ids[:HN_STORY_LIMIT]:
        pid = f"hn_{sid}"
        if pid in seen_ids:
            continue
        item = _safe_get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")
        if not item:
            continue
        title = item.get("title", "")
        text  = item.get("text", "") or ""
        if not _is_relevant(title, text):
            continue
        raw.append({
            "id":          pid,
            "title":       title,
            "body":        text[:500],
            "source":      "Hacker News",
            "url":         item.get("url") or f"https://news.ycombinator.com/item?id={sid}",
            "score":       item.get("score", 0),
            "created_utc": item.get("time", 0),
        })

    log.info("HN: %d relevant Show HN stories", len(raw))
    return raw


def _parse_hn_from_markdown(markdown: str, seen_ids: set[str]) -> list[dict]:
    """Extract Show HN posts from Apify-scraped HN page."""
    posts = []
    for line in markdown.split("\n"):
        line = line.strip()
        if "show hn" in line.lower() and len(line) > 15:
            title = line.lstrip("#").strip()
            if not _is_relevant(title, ""):
                continue
            pid = f"hn_apify_{abs(hash(title)) % 1_000_000}"
            if pid not in seen_ids:
                posts.append({
                    "id":          pid,
                    "title":       title,
                    "body":        "",
                    "source":      "Hacker News",
                    "url":         "https://news.ycombinator.com/show",
                    "score":       0,
                    "created_utc": 0,
                })
    return posts[:20]


# ── Claude batch extraction ───────────────────────────────────────────────────

def _extract_ideas(posts: list[dict]) -> list[dict]:
    """
    Send filtered posts to Claude in one call.
    Returns a list of structured idea objects — only genuine new SaaS/product ideas.
    """
    if not client or not posts:
        return []

    posts_text = "\n\n---\n\n".join(
        f"ID: {p['id']}\nSOURCE: {p['source']}\nURL: {p['url']}\n"
        f"TITLE: {p['title']}\nBODY: {p['body']}"
        for p in posts
    )

    prompt = (
        "Below are social media posts. Extract only the ones that describe a specific, "
        "concrete SaaS product or startup idea (not general advice, job posts, or discussions).\n\n"
        "For each qualifying post return:\n"
        '{"post_id": str, "idea_name": str, "idea_description": str (2-3 sentences, '
        "what problem it solves and who pays for it), "
        '"source": str, "source_url": str}\n\n'
        "Return ONLY a JSON array. If no posts qualify, return [].\n\n"
        "POSTS:\n" + posts_text[:12000]
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
            ideas = json.loads(text.strip())
            if isinstance(ideas, list):
                return ideas
        except Exception as exc:
            log.warning("Claude idea extraction attempt %d failed: %s", attempt + 1, exc)
            time.sleep(3)

    return []


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_new_ideas(seen_ids: set[str]) -> tuple[list[dict], set[str]]:
    """
    Discover new SaaS ideas from Reddit and HN.

    Args:
        seen_ids: set of post IDs already processed (for deduplication)

    Returns:
        (ideas, updated_seen_ids)
        Each idea: {post_id, idea_name, idea_description, source, source_url}
    """
    log.info("Fetching new ideas from Reddit and HN…")
    reddit_posts = _fetch_reddit(REDDIT_SUBREDDITS, seen_ids)
    hn_posts     = _fetch_hn(seen_ids)
    all_posts    = reddit_posts + hn_posts

    # Update seen_ids with everything we fetched (even if filtered out later)
    all_fetched_ids = {p["id"] for p in reddit_posts + hn_posts}
    updated_seen    = seen_ids | all_fetched_ids

    if not all_posts:
        log.info("No new relevant posts found.")
        return [], updated_seen

    log.info("Sending %d posts to Claude for idea extraction…", len(all_posts))
    ideas = _extract_ideas(all_posts)
    log.info("Extracted %d concrete ideas from %d posts", len(ideas), len(all_posts))
    return ideas, updated_seen
