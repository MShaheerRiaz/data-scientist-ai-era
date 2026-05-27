"""
Cross-checks a startup idea against startups.rip to find similar failed YC startups.

Requirements:
  - ANTHROPIC_API_KEY env var (for Claude analysis)
  - APIFY_TOKEN env var (for web scraping — startups.rip blocks direct requests)

Install: pip install anthropic requests
"""

import json
import os
import time
import requests
import anthropic

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
BASE_URL = "https://startups.rip"
APIFY_ACTOR = "apify~rag-web-browser"
APIFY_RUN_URL = f"https://api.apify.com/v2/acts/{APIFY_ACTOR}/run-sync-get-dataset-items"

client = anthropic.Anthropic()


def _apify_fetch(url: str) -> str:
    """Fetch a URL via Apify RAG web browser. Returns markdown content."""
    if not APIFY_TOKEN:
        raise EnvironmentError("APIFY_TOKEN env var is not set.")

    resp = requests.post(
        APIFY_RUN_URL,
        params={"token": APIFY_TOKEN},
        json={"query": url, "maxResults": 1, "outputFormats": ["markdown"]},
        timeout=90,
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list) and data:
        return data[0].get("markdown", "")
    return ""


def _generate_search_queries(idea_name: str, idea_description: str) -> list[str]:
    """Use Claude to generate 2-3 search terms for finding similar startups."""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": (
                f"I'm searching a database of failed YC startups for companies similar to this idea:\n"
                f"Name: {idea_name}\n"
                f"Description: {idea_description}\n\n"
                f"Generate 2-3 short search queries (2-4 words each) to find similar startups. "
                f"Return ONLY a JSON array of strings. Example: [\"location sharing app\", \"friend finder mobile\"]"
            ),
        }],
    )
    text = response.content[0].text.strip()
    try:
        queries = json.loads(text)
        return [q for q in queries if isinstance(q, str)][:3]
    except json.JSONDecodeError:
        return [idea_name]


def _search_startups_rip(query: str) -> list[dict]:
    """
    Search startups.rip and return list of {name, slug} candidates.
    Uses Apify to handle JavaScript rendering.
    """
    search_url = f"{BASE_URL}/?search={requests.utils.quote(query)}"
    markdown = _apify_fetch(search_url)

    candidates = []
    seen = set()
    # Parse markdown links like [Company Name](/company/slug)
    for line in markdown.split("\n"):
        if "/company/" in line:
            start = line.find("/company/")
            end = line.find(")", start) if ")" in line[start:] else len(line)
            slug_part = line[start + len("/company/"):end].strip().strip(")")
            slug = slug_part.split("?")[0].split("#")[0].strip()
            if not slug or slug in seen:
                continue
            seen.add(slug)
            # Try to extract name from markdown link text [Name](/company/slug)
            name = slug
            bracket_end = line.find(f"(/company/{slug}")
            if bracket_end > 0:
                bracket_start = line.rfind("[", 0, bracket_end)
                if bracket_start >= 0:
                    name = line[bracket_start + 1:bracket_end].strip()
            candidates.append({"name": name or slug, "slug": slug})

    return candidates


def _fetch_company_content(slug: str) -> str:
    """Fetch company page content via Apify."""
    markdown = _apify_fetch(f"{BASE_URL}/company/{slug}")
    return markdown[:8000]


def _analyse_similarity_and_failures(
    idea_name: str,
    idea_description: str,
    company_name: str,
    company_content: str,
) -> dict:
    """Ask Claude whether the company is similar and extract failure lessons."""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=800,
        messages=[{
            "role": "user",
            "content": (
                f"NEW STARTUP IDEA:\nName: {idea_name}\nDescription: {idea_description}\n\n"
                f"FAILED STARTUP FROM startups.rip:\nName: {company_name}\nContent:\n{company_content}\n\n"
                f"Tasks:\n"
                f"1. Score similarity 0-10 (10 = nearly identical idea)\n"
                f"2. If score >= 5, extract: why it failed (bullet points) and what improvements could make a new attempt succeed\n"
                f"3. Also extract: YC batch and final status (Acquired/Inactive/etc) if visible\n\n"
                f"Return ONLY a JSON object:\n"
                f'{{"similarity_score": int, "yc_batch": str_or_null, "status": str_or_null, '
                f'"why_failed": list_or_null, "key_improvements": list_or_null}}'
            ),
        }],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
        if text.endswith("```"):
            text = text[: text.rfind("```")]
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return {
            "similarity_score": 0,
            "yc_batch": None,
            "status": None,
            "why_failed": None,
            "key_improvements": None,
        }


def check_idea_against_rip(idea_name: str, idea_description: str) -> dict:
    """
    Cross-check a startup idea against startups.rip.

    Returns:
        {
          "found": bool,
          "similar_company": str | None,
          "yc_batch": str | None,
          "status": str | None,
          "why_failed": list[str] | None,
          "key_improvements": list[str] | None,
          "rip_url": str | None,
          "similarity_score": int | None,
        }
    """
    no_match = {
        "found": False,
        "similar_company": None,
        "yc_batch": None,
        "status": None,
        "why_failed": None,
        "key_improvements": None,
        "rip_url": None,
        "similarity_score": None,
    }

    queries = _generate_search_queries(idea_name, idea_description)

    seen_slugs: set[str] = set()
    candidates: list[dict] = []

    for query in queries:
        results = _search_startups_rip(query)
        for r in results:
            if r["slug"] not in seen_slugs:
                seen_slugs.add(r["slug"])
                candidates.append(r)
        if candidates:
            break
        time.sleep(0.5)

    if not candidates:
        return no_match

    best_match = None
    best_score = 0

    for candidate in candidates[:3]:
        content = _fetch_company_content(candidate["slug"])
        if not content:
            continue

        analysis = _analyse_similarity_and_failures(
            idea_name, idea_description, candidate["name"], content
        )

        score = analysis.get("similarity_score", 0)
        if score >= 5 and score > best_score:
            best_score = score
            best_match = {
                "found": True,
                "similar_company": candidate["name"],
                "yc_batch": analysis.get("yc_batch"),
                "status": analysis.get("status"),
                "why_failed": analysis.get("why_failed"),
                "key_improvements": analysis.get("key_improvements"),
                "rip_url": f"{BASE_URL}/company/{candidate['slug']}",
                "similarity_score": score,
            }

    return best_match or {**no_match, "similarity_score": best_score or None}


if __name__ == "__main__":
    test_ideas = [
        {
            "name": "FriendMap",
            "description": (
                "A mobile app that lets you see where your friends are in real time "
                "on a map and get notified when they're nearby."
            ),
        },
        {
            "name": "LegalBot",
            "description": (
                "An AI-powered law firm for startups that automates contracts, "
                "compliance, and legal workflows using proprietary technology."
            ),
        },
    ]

    for idea in test_ideas:
        print(f"\n{'='*60}")
        print(f"Checking: {idea['name']}")
        print(f"Description: {idea['description']}")
        print("-" * 60)
        result = check_idea_against_rip(idea["name"], idea["description"])
        if result["found"]:
            print(f"⚠️  SIMILAR FAILURE: {result['similar_company']} ({result['yc_batch']} · {result['status']})")
            print(f"   Similarity: {result['similarity_score']}/10  |  {result['rip_url']}")
            print("\n   WHY IT FAILED:")
            for r in result["why_failed"] or []:
                print(f"   • {r}")
            print("\n   KEY IMPROVEMENTS:")
            for t in result["key_improvements"] or []:
                print(f"   • {t}")
        else:
            print("✅ No similar failure found on startups.rip")
