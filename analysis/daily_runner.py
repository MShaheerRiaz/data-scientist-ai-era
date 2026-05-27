"""
Daily SaaS Opportunity Report — main orchestrator.

Flow:
  1. Load state (seen IDs, last run date)
  2. Fetch new ideas from Reddit + HN
  3. For each idea:
       a. Cross-check against startups.rip  (did this already fail?)
       b. Validate with TrustMRR market data (is this category winning?)
       c. Score 1-10 with Claude
  4. Generate ranked markdown report
  5. Save report + updated state
"""

import json
import logging
import time
from datetime import date, datetime
from pathlib import Path

import anthropic

from config import (
    ANTHROPIC_API_KEY,
    REPORTS_DIR,
    STATE_FILE,
    MIN_REPORT_SCORE,
)
from idea_finder        import fetch_new_ideas
from startup_checker    import check_idea_against_rip
from trustmrr_scanner   import (
    fetch_market_snapshot,
    get_market_context,
    get_undervalued_opportunities,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None


# ── State management ──────────────────────────────────────────────────────────

def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                state = json.load(f)
                state["seen_ids"] = set(state.get("seen_ids", []))
                return state
        except Exception as exc:
            log.warning("State file corrupt, resetting: %s", exc)
    return {"seen_ids": set(), "last_run": None, "reports": []}


def _save_state(state: dict) -> None:
    serialisable = {**state, "seen_ids": list(state["seen_ids"])}
    with open(STATE_FILE, "w") as f:
        json.dump(serialisable, f, indent=2)


# ── Idea scoring ──────────────────────────────────────────────────────────────

def _score_idea(
    idea: dict,
    rip: dict,
    market: dict,
) -> dict:
    """
    Ask Claude to score an idea 1-10 and produce a short verdict.
    Returns the enriched idea dict with score + verdict fields.
    """
    if not client:
        return {**idea, "score": 5, "verdict": "Claude unavailable — manual review required."}

    rip_section = ""
    if rip["found"]:
        rip_section = (
            f"startups.rip found a SIMILAR FAILURE: {rip['similar_company']} "
            f"({rip['yc_batch']} · {rip['status']}, similarity {rip['similarity_score']}/10).\n"
            f"Why it failed: {rip['why_failed']}\n"
            f"Potential improvements: {rip['key_improvements']}"
        )
    else:
        rip_section = "startups.rip: No similar failure found in YC history."

    market_section = (
        f"TrustMRR market health: {market.get('category_health', 'unknown')}\n"
        f"Market signal: {market.get('market_signal', 'N/A')}\n"
        f"Similar live products: {json.dumps(market.get('similar_products', []))}"
    )

    prompt = (
        f"IDEA: {idea.get('idea_name')}\n"
        f"DESCRIPTION: {idea.get('idea_description')}\n\n"
        f"FAILURE HISTORY:\n{rip_section}\n\n"
        f"MARKET CONTEXT:\n{market_section}\n\n"
        "Score this idea 1-10 as a SaaS opportunity to pursue TODAY:\n"
        "- 9-10: Outstanding. Hot market, no major prior failures, clear monetisation.\n"
        "- 7-8:  Strong. Minor risks but good signals.\n"
        "- 5-6:  Moderate. Worth watching but has real challenges.\n"
        "- 1-4:  Weak. Market cold, prior failures unresolved, or idea is too vague.\n\n"
        "Return ONLY JSON:\n"
        '{"score": int, "verdict": str (2-3 sentences: why this score, '
        'what the founder should do differently from the failed version), '
        '"recommended_angle": str (one sentence: the specific niche or GTM to pursue)}'
    )

    for attempt in range(2):
        try:
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            result = json.loads(text.strip())
            return {**idea, **result, "rip": rip, "market": market}
        except Exception as exc:
            log.warning("Score attempt %d failed: %s", attempt + 1, exc)
            time.sleep(2)

    return {
        **idea,
        "score": 5,
        "verdict": "Scoring failed — manual review required.",
        "recommended_angle": "N/A",
        "rip": rip,
        "market": market,
    }


# ── Report generation ─────────────────────────────────────────────────────────

def _fmt_mrr(usd: int | float | None) -> str:
    if usd is None:
        return "N/A"
    if usd >= 1_000_000:
        return f"${usd/1_000_000:.1f}M"
    if usd >= 1_000:
        return f"${usd/1_000:.0f}k"
    return f"${usd:.0f}"


def _fmt_growth(pct: float | None) -> str:
    if pct is None:
        return "—"
    return f"{pct:+.0f}% MoM"


def _generate_report(
    scored_ideas: list[dict],
    market_data: dict,
    run_date: str,
    stats: dict,
) -> str:
    high  = [i for i in scored_ideas if i.get("score", 0) >= MIN_REPORT_SCORE]
    caution = [i for i in scored_ideas if 3 <= i.get("score", 0) < MIN_REPORT_SCORE]

    lines = [
        f"# SaaS Opportunity Report — {run_date}",
        "",
        "## Summary",
        f"- Ideas scanned: **{stats['total']}**",
        f"- High-potential (score ≥ {MIN_REPORT_SCORE}): **{len(high)}**",
        f"- Caution flags (score 3-{MIN_REPORT_SCORE-1}): **{len(caution)}**",
        f"- TrustMRR data: {'✅ Live' if market_data.get('available') else '⚠️  Unavailable (set APIFY_TOKEN)'}",
        "",
        "---",
        "",
    ]

    # ── Opportunities ──────────────────────────────────────────────────────
    if not high:
        lines += ["## No high-potential ideas found today", ""]
    else:
        lines += ["## 🚀 Opportunities", ""]
        for rank, idea in enumerate(
            sorted(high, key=lambda x: x.get("score", 0), reverse=True), 1
        ):
            rip    = idea.get("rip", {})
            market = idea.get("market", {})
            score  = idea.get("score", "?")

            emoji = "🔥" if score >= 8 else "✅"
            lines += [
                f"### {emoji} #{rank} — {idea.get('idea_name', 'Unnamed')} · Score {score}/10",
                f"**Source:** [{idea.get('source')}]({idea.get('source_url', '#')})",
                f"**Description:** {idea.get('idea_description', '')}",
                "",
            ]

            # RIP section
            if rip.get("found"):
                lines += [
                    "**⚠️ startups.rip: Similar failure found**",
                    f"- Company: [{rip['similar_company']}]({rip.get('rip_url', '#')}) "
                    f"({rip.get('yc_batch')} · {rip.get('status')}) "
                    f"— similarity {rip.get('similarity_score')}/10",
                ]
                if rip.get("why_failed"):
                    lines += ["- Why it failed:"]
                    for reason in rip["why_failed"]:
                        lines.append(f"  - {reason}")
                if rip.get("key_improvements"):
                    lines += ["- Improvements to consider:"]
                    for tip in rip["key_improvements"]:
                        lines.append(f"  - {tip}")
            else:
                lines.append("**✅ startups.rip: No similar YC failure found**")

            lines.append("")

            # TrustMRR section
            category_health = market.get("category_health", "unknown")
            health_icon = {"hot": "🔥", "warm": "📈", "cold": "❄️"}.get(category_health, "❓")
            lines += [
                f"**{health_icon} TrustMRR: {category_health.title()} market "
                f"({market.get('matching_category', 'unclassified')})**",
                market.get("market_signal", ""),
            ]
            similar = market.get("similar_products", [])
            if similar:
                lines.append("Live comparable products:")
                for sp in similar[:3]:
                    lines.append(
                        f"  - {sp.get('name')} — {_fmt_mrr(sp.get('mrr_usd'))} MRR "
                        f"({_fmt_growth(sp.get('mom_growth_pct'))})"
                    )

            lines += [
                "",
                f"**🧠 Verdict:** {idea.get('verdict', '')}",
                f"**Recommended angle:** {idea.get('recommended_angle', 'N/A')}",
                "",
                "---",
                "",
            ]

    # ── Caution list ───────────────────────────────────────────────────────
    if caution:
        lines += ["## ⚠️ Watch List (scored 3-{MIN_REPORT_SCORE-1})", ""]
        for idea in sorted(caution, key=lambda x: x.get("score", 0), reverse=True):
            lines.append(
                f"- **{idea.get('idea_name')}** (score {idea.get('score')}/10) — "
                f"{idea.get('verdict', '')[:100]}… "
                f"[source]({idea.get('source_url', '#')})"
            )
        lines.append("")

    # ── TrustMRR market pulse ──────────────────────────────────────────────
    lines += ["## 📊 TrustMRR Market Pulse", ""]

    hot_cats = market_data.get("hot_categories", [])
    if hot_cats:
        lines += [
            "### Hottest Categories",
            "| Category | Avg MRR | Avg Growth | Products |",
            "|---|---|---|---|",
        ]
        for cat in hot_cats[:8]:
            lines.append(
                f"| {cat.get('name')} | {_fmt_mrr(cat.get('avg_mrr_usd'))} | "
                f"{_fmt_growth(cat.get('avg_mom_growth_pct'))} | {cat.get('startup_count')} |"
            )
        lines.append("")

    # Top leaderboard movers
    movers = sorted(
        [s for s in market_data.get("leaderboard", []) if s.get("mom_growth_pct")],
        key=lambda x: x.get("mom_growth_pct", 0),
        reverse=True,
    )[:5]
    if movers:
        lines += ["### 📈 Fastest Growing This Week", ""]
        for m in movers:
            sale_tag = " *(FOR SALE)*" if m.get("for_sale") else ""
            lines.append(
                f"- **{m['name']}**{sale_tag} — {_fmt_mrr(m.get('mrr_usd'))} MRR "
                f"({_fmt_growth(m.get('mom_growth_pct'))})"
            )
        lines.append("")

    # Undervalued FOR SALE
    opportunities = get_undervalued_opportunities(market_data)
    if opportunities:
        lines += [
            "### 💰 Undervalued Acquisitions (< 1.5x multiple)",
            "| Product | MRR | Asking | Multiple | Why Interesting |",
            "|---|---|---|---|---|",
        ]
        for op in opportunities[:5]:
            lines.append(
                f"| {op['name']} | {_fmt_mrr(op.get('revenue_usd'))} | "
                f"{_fmt_mrr(op.get('asking_price_usd'))} | "
                f"{op.get('multiple_x')}x | {op.get('why_interesting', '')} |"
            )
        lines.append("")

    lines += [
        "---",
        f"*Generated by SaaS Radar on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
    ]

    return "\n".join(lines)


# ── Main routine ──────────────────────────────────────────────────────────────

def run() -> str:
    """
    Execute the full daily routine.
    Returns the path to the saved report file.
    """
    run_date = date.today().isoformat()
    log.info("=" * 60)
    log.info("SaaS Radar daily run — %s", run_date)
    log.info("=" * 60)

    # 1. Load state
    state    = _load_state()
    seen_ids = state["seen_ids"]

    # 2. Fetch live market data (single Apify call, cached for this run)
    market_data = fetch_market_snapshot()

    # 3. Find new ideas
    ideas, seen_ids = fetch_new_ideas(seen_ids)
    log.info("Found %d new ideas to analyse", len(ideas))

    # 4. Analyse each idea
    scored = []
    for i, idea in enumerate(ideas, 1):
        log.info("[%d/%d] Analysing: %s", i, len(ideas), idea.get("idea_name"))

        rip    = check_idea_against_rip(idea["idea_name"], idea["idea_description"])
        market = get_market_context(idea["idea_description"], market_data)
        scored_idea = _score_idea(idea, rip, market)
        scored.append(scored_idea)

        log.info(
            "  → Score %s/10 | RIP: %s | Market: %s",
            scored_idea.get("score"),
            "found" if rip["found"] else "clear",
            market.get("category_health", "?"),
        )
        time.sleep(0.5)  # avoid hammering APIs

    # 5. Generate report
    stats = {
        "total":    len(ideas),
        "high":     len([s for s in scored if s.get("score", 0) >= MIN_REPORT_SCORE]),
        "caution":  len([s for s in scored if 3 <= s.get("score", 0) < MIN_REPORT_SCORE]),
    }
    report_md = _generate_report(scored, market_data, run_date, stats)

    # 6. Save report
    report_path = REPORTS_DIR / f"{run_date}.md"
    if report_path.exists():
        ts = datetime.now().strftime("%H%M%S")
        report_path = REPORTS_DIR / f"{run_date}-{ts}.md"

    report_path.write_text(report_md, encoding="utf-8")
    log.info("Report saved → %s", report_path)

    # Also save raw JSON for downstream processing
    json_path = report_path.with_suffix(".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "date": run_date,
                "stats": stats,
                "ideas": scored,
                "market": market_data,
            },
            f,
            indent=2,
            default=str,
        )

    # 7. Update and save state
    state["seen_ids"] = seen_ids
    state["last_run"] = datetime.now().isoformat()
    state.setdefault("reports", []).append(str(report_path))
    _save_state(state)

    # Print to console
    print("\n" + report_md + "\n")
    log.info("Done. %d ideas analysed, %d high-potential.", len(ideas), stats["high"])
    return str(report_path)


if __name__ == "__main__":
    run()
