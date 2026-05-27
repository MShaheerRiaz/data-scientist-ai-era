"""
Example: how to plug startup_checker into your existing daily idea-scraping routine.

Your routine produces a list of ideas → pass each one through check_idea_against_rip
→ get back a structured result you can log, email, or store.
"""

from startup_checker import check_idea_against_rip


def process_ideas(ideas: list[dict]) -> list[dict]:
    """
    ideas: list of {"name": str, "description": str}
    Returns: each idea dict enriched with a "rip_check" key.
    """
    enriched = []
    for idea in ideas:
        rip = check_idea_against_rip(idea["name"], idea["description"])
        enriched.append({**idea, "rip_check": rip})
    return enriched


def format_daily_report(enriched_ideas: list[dict]) -> str:
    lines = ["=== Daily Idea Report: startups.rip Cross-Check ===\n"]
    for idea in enriched_ideas:
        rip = idea["rip_check"]
        lines.append(f"IDEA: {idea['name']}")
        lines.append(f"  {idea['description'][:100]}...")

        if rip["found"]:
            lines.append(f"  ⚠️  SIMILAR FAILURE: {rip['similar_company']} ({rip['yc_batch']} · {rip['status']})")
            lines.append(f"  Similarity: {rip['similarity_score']}/10  |  {rip['rip_url']}")
            if rip["why_failed"]:
                lines.append("  Why it failed:")
                for r in rip["why_failed"]:
                    lines.append(f"    • {r}")
            if rip["key_improvements"]:
                lines.append("  Improvements to consider:")
                for t in rip["key_improvements"]:
                    lines.append(f"    • {t}")
        else:
            lines.append("  ✅ No similar failure found on startups.rip")

        lines.append("")
    return "\n".join(lines)


# ── Drop-in usage in your existing routine ──────────────────────────────────
#
# Replace `your_scraper_output` with whatever your daily routine produces:
#
#   from daily_routine_integration import process_ideas, format_daily_report
#
#   ideas = your_scraper_output   # [{"name": "...", "description": "..."}, ...]
#   enriched = process_ideas(ideas)
#   print(format_daily_report(enriched))
#
# ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Simulate a day's scraper output
    sample_ideas = [
        {
            "name": "QuickLegal",
            "description": "AI-powered legal services platform for startups. Automates contracts, compliance, and legal workflows."
        },
        {
            "name": "GiftCard Exchange",
            "description": "Marketplace where users can buy and sell unused gift cards at a discount."
        },
    ]

    enriched = process_ideas(sample_ideas)
    print(format_daily_report(enriched))
