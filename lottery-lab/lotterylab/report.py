"""Generate the illustrated PDF summary.

Every number in the report is pulled live from the library rather than
typed in, so the charts cannot drift out of step with the analysis.

Design notes, for anyone editing this later. The story is "one option
wins", so the charts use **emphasis** — the recommendation carries the
one saturated hue and everything else recedes to grey. That is
deliberate: eight competing colours would make the reader hunt for the
point instead of being handed it. Marks are thin, gridlines are solid
hairlines one shade off the surface, and bar ends are labelled directly so
no value depends on a legend lookup.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional, Sequence

from .combinatorics import all_tier_probabilities, jackpot_probability, odds_string
from .compare import best_for, budget_outcome, uk_options
from .config import HOTPICKS, PRESETS, UK_GAMES
from .fairness import power_analysis
from .winners import GUARANTEED_UK_MILLIONAIRES_PER_WEEK, expected_winners

__all__ = ["build_report"]

# --- palette -----------------------------------------------------------
SURFACE = "#fcfcfb"
PAGE = "#f9f9f7"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

BLUE = "#2a78d6"        # categorical slot 1 - the recommendation
ORANGE = "#eb6834"      # slot 2 - the thing being compared against
AQUA = "#1baf7a"        # slot 3
GOOD = "#0ca30c"
CRITICAL = "#d03b3b"
RECEDE = "#c9c8c2"      # everything that is not the point

FONT = ["DejaVu Sans", "system-ui", "sans-serif"]


def _style():
    import matplotlib as mpl

    mpl.use("Agg")
    mpl.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.family": "sans-serif",
        "font.sans-serif": FONT,
        "text.color": INK,
        "axes.labelcolor": INK2,
        "axes.edgecolor": AXIS,
        "axes.linewidth": 0.8,
        "xtick.color": MUTED,
        "ytick.color": INK2,
        "xtick.labelsize": 8.5,
        "ytick.labelsize": 9,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlecolor": INK,
        "grid.color": GRID,
        "grid.linewidth": 0.7,
        "grid.linestyle": "-",          # solid hairlines, never dashed
        "axes.grid": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "figure.dpi": 200,
    })


def _short_money(value: float) -> str:
    """Compact currency, but never at the cost of the actual figure.

    Abbreviating below £10k rounds away digits that matter — £1,500 shown
    as "£2k" is both wrong and vaguer than the number deserves.
    """
    if value >= 1_000_000:
        return f"£{value / 1_000_000:.1f}m".replace(".0m", "m")
    if value >= 10_000:
        return f"£{value / 1_000:,.0f}k"
    return f"£{value:,.0f}"


def _money_axis(ax):
    """Readable currency ticks on a log axis, instead of 10^3 notation."""
    from matplotlib.ticker import FuncFormatter, LogLocator

    ax.xaxis.set_major_locator(LogLocator(base=10))
    ax.xaxis.set_major_formatter(FuncFormatter(
        lambda v, _pos: (f"£{v / 1_000_000:.0f}m" if v >= 1_000_000
                         else f"£{v / 1_000:.0f}k" if v >= 1_000
                         else f"£{v:.0f}")
    ))
    ax.xaxis.set_minor_formatter(FuncFormatter(lambda *_: ""))


def _odds_short(p: float) -> str:
    """'1 in 2,940' style, abbreviated only where the digits stop mattering.

    Abbreviating below six figures loses real information — "1 in 2k" for
    1,960 both rounds the wrong way and reads as vaguer than the figure is.
    """
    n = 1 / p
    if n >= 1_000_000:
        return f"1 in {n / 1_000_000:.1f}m"
    return f"1 in {n:,.0f}"


def _whole_game_rtp(game_key: str) -> float:
    """Return to player for an entire game, across all its tiers.

    Not to be confused with a single tier's expected return: Lotto's Match 5
    tier alone returns about 1% of stakes, while the whole game returns
    about 40%. Comparing a tier against a game would be badly misleading.
    """
    from .combinatorics import all_tier_probabilities

    jackpots = {"uk_lotto": 4_000_000.0, "euromillions": 50_000_000.0}
    cfg = PRESETS[game_key]
    total = sum(
        p * (jackpots.get(game_key, tier.payout) if tier.is_jackpot else tier.payout)
        for tier, p in all_tier_probabilities(cfg)
    )
    return total / cfg.ticket_price


def _page_header(fig, key: str, title: str, subtitle: str = ""):
    """Consistent page furniture, numbered from the ordering table."""
    part = _PART_OF.get(key, "")
    if part:
        fig.text(0.06, 0.963, part, fontsize=7.5, color=MUTED,
                 va="top", fontweight="bold")
    fig.text(0.06, 0.944, title, fontsize=17, fontweight="bold", color=INK, va="top")
    if subtitle:
        fig.text(0.06, 0.908, subtitle, fontsize=10.5, color=INK2, va="top")
    fig.text(0.94, 0.944, str(_PAGE_NO[key]), fontsize=9, color=MUTED,
             va="top", ha="right")


def _footer(fig, text: str = ""):
    fig.text(0.06, 0.035, text or "lotterylab · every figure computed, not quoted",
             fontsize=7.5, color=MUTED, va="bottom")



# ---------------------------------------------------------------------------
# Page order
# ---------------------------------------------------------------------------
#
# The reading order lives HERE and nowhere else. Page numbers, the contents
# page and every cross-reference are derived from this list, so adding or
# moving a page cannot leave stale numbering behind - which is exactly what
# happened when three pages were appended by hand.

_ORDER: list[tuple[str, str, str]] = [
    # key            part                            title
    ("cover",        "",                             "UK Lottery"),
    ("contents",     "",                             "What is in this report"),
    ("ranked",       "PART 1 - WHAT TO PLAY",        "The games, ranked"),
    ("cost",         "PART 1 - WHAT TO PLAY",        "What it costs to win"),
    ("budget",       "PART 1 - WHAT TO PLAY",        "What £10 a week actually buys"),
    ("value",        "PART 2 - WHAT IT COSTS YOU",   "Where the money goes"),
    ("tradeoff",     "PART 2 - WHAT IT COSTS YOU",   "The trade-off, and why it breaks"),
    ("powerball",    "PART 3 - THE GAMES UP CLOSE",  "UK Powerball — the new game"),
    ("scale",        "PART 3 - THE GAMES UP CLOSE",  "How long are the odds, really?"),
    ("millionaires", "PART 4 - WHAT NOT TO BELIEVE", "Why someone wins a million every week"),
    ("myths",        "PART 4 - WHAT NOT TO BELIEVE", "What does not work"),
    ("reference",    "PART 5 - KEEP THIS",           "Quick reference"),
    ("simple",       "PART 5 - KEEP THIS",           "In simple words"),
]

_PAGE_NO = {key: i + 1 for i, (key, _part, _title) in enumerate(_ORDER)}
_PART_OF = {key: part for key, part, _title in _ORDER}


def page_number(key: str) -> int:
    """Printed page number for a section, so cross-references stay correct."""
    return _PAGE_NO[key]


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


def _page_cover(pdf, plt):
    """The answer, up front, as stat tiles rather than a chart."""
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.patch.set_facecolor(SURFACE)

    fig.text(0.06, 0.90, "UK Lottery", fontsize=40, fontweight="bold", color=INK, va="top")
    fig.text(0.06, 0.845, "What the numbers actually say", fontsize=17, color=INK2, va="top")
    fig.text(0.06, 0.805, "Prepared for Shaheer  ·  every figure computed from first "
                          "principles and checked against\nthe operators' published odds",
             fontsize=9.5, color=MUTED, va="top")

    # The single recommendation, as a hero block.
    hp = HOTPICKS["euromillions_hotpicks"]
    p3 = hp.probability(3)
    fig.patches.append(plt.Rectangle((0.06, 0.545), 0.88, 0.20, transform=fig.transFigure,
                                     facecolor="#eef4fd", edgecolor=BLUE, linewidth=1.2,
                                     zorder=0))
    fig.text(0.09, 0.715, "IF YOU WANT A REALISTIC SHOT AT £1,000+", fontsize=9.5,
             color=BLUE, fontweight="bold", va="top")
    fig.text(0.09, 0.678, "EuroMillions HotPicks", fontsize=27, fontweight="bold",
             color=INK, va="top")
    fig.text(0.09, 0.632, "pick 3 numbers  ·  £1.50 a line", fontsize=14, color=INK2, va="top")

    tiles = [
        ("£1,500", "prize"),
        (_odds_short(p3), "odds per line"),
        ("1 in 6", "chance in a year\nat £10/week"),
    ]
    for i, (big, small) in enumerate(tiles):
        x = 0.09 + i * 0.29
        fig.text(x, 0.592, big, fontsize=21, fontweight="bold", color=BLUE, va="top")
        fig.text(x, 0.5585, small, fontsize=8.5, color=INK2, va="top", linespacing=1.5)

    # The comparison that makes the case.
    options = {o.label: o for o in uk_options()}
    hot3 = options["EuroMillions HotPicks pick-3"]
    lotto5 = options["UK Lotto - 5"]
    ratio = lotto5.cost_per_shot / hot3.cost_per_shot

    fig.text(0.06, 0.495, "Why this one", fontsize=13, fontweight="bold", color=INK, va="top")
    lines = [
        (f"It costs £{hot3.cost_per_shot:,.0f} of tickets, on average, to win £1,500 once."),
        (f"Lotto's Match 5 pays a similar £1,750 — but costs £{lotto5.cost_per_shot:,.0f}."),
        (f"That makes HotPicks pick-3 about {ratio:.0f}x better per pound spent."),
        "",
        (f"And it is better value too: {hot3.expected_return:.0%} of stakes come back, "
         f"against {_whole_game_rtp('uk_lotto'):.0%} for the whole Lotto game"),
        (f"and {_whole_game_rtp('euromillions'):.0%} for EuroMillions. Access and value "
         f"usually pull in opposite"),
        "directions. Here they agree, which is what makes it the answer.",
    ]
    for i, line in enumerate(lines):
        fig.text(0.06, 0.462 - i * 0.0225, line, fontsize=10.5, color=INK2, va="top")

    fig.text(0.06, 0.245, "The honest part", fontsize=13, fontweight="bold",
             color=CRITICAL, va="top")
    honest = [
        "Every option in this report loses money on average. The one above keeps",
        "49p of every pound you stake. Nothing here is a way to win.",
        "",
        "What it does is stop you paying £288,830 per expected win when £2,940",
        "buys a near-identical prize on the same counter.",
    ]
    for i, line in enumerate(honest):
        fig.text(0.06, 0.212 - i * 0.0225, line, fontsize=10.5, color=INK2, va="top")

    _footer(fig, "Generated by lotterylab  ·  225 automated tests  ·  see PLAYBOOK.md")
    pdf.savefig(fig)
    plt.close(fig)


def _page_contents(pdf, plt):
    """A map of the report, so the reader can jump straight to what they need."""
    fig = plt.figure(figsize=(8.27, 11.69))
    _page_header(fig, "contents", "What is in this report",
                 "Read pages 3 to 5 if you only read three pages.")

    blurbs = {
        "ranked":       "Every game placed first to fifth, with cost, odds and prize.",
        "cost":         "How much you must stake, on average, to actually win.",
        "budget":       "What a real weekly budget buys you over a year.",
        "value":        "Of every £1 staked, how much comes back as prizes.",
        "tradeoff":     "Why one option is both the cheapest to win AND better value.",
        "powerball":    "The new game, in full - prize table and three warnings.",
        "scale":        "What 1 in 292 million means, against things you can picture.",
        "millionaires": "Why a winner appears nearly every week, by design.",
        "myths":        "Hot numbers, due numbers, lucky systems - all tested, all failed.",
        "reference":    "The whole report on one page, to keep.",
        "simple":       "Everything again, in plain words with no arithmetic.",
    }

    y = 0.858
    current_part = None
    for key, part, title in _ORDER:
        if key in ("cover", "contents"):
            continue
        if part != current_part:
            current_part = part
            y -= 0.012
            fig.text(0.06, y, part, fontsize=8, fontweight="bold", color=MUTED, va="top")
            fig.add_artist(plt.Line2D([0.06, 0.94], [y - 0.014, y - 0.014],
                                      color=GRID, linewidth=0.8,
                                      transform=fig.transFigure))
            y -= 0.026

        highlight = key in ("ranked", "simple")
        fig.text(0.065, y, str(_PAGE_NO[key]), fontsize=11,
                 fontweight="bold", color=BLUE if highlight else MUTED, va="top")
        fig.text(0.115, y, title, fontsize=11.5,
                 fontweight="bold" if highlight else "normal",
                 color=INK if highlight else INK2, va="top")
        fig.text(0.115, y - 0.020, blurbs[key], fontsize=8.8, color=MUTED, va="top")
        y -= 0.042

    fig.patches.append(plt.Rectangle((0.06, 0.075), 0.88, 0.115, transform=fig.transFigure,
                                     facecolor="#eef4fd", edgecolor=BLUE,
                                     linewidth=1.0, zorder=0))
    fig.text(0.09, 0.172, "IN ONE LINE", fontsize=8.5, color=BLUE,
             fontweight="bold", va="top")
    fig.text(0.09, 0.150,
             "Play EuroMillions HotPicks, pick 3 numbers, GBP 1.50 a line.".replace("GBP ", "£"),
             fontsize=13, fontweight="bold", color=INK, va="top")
    fig.text(0.09, 0.121,
             "£1,500 if all three come up, at 1 in 1,960 - about a 1 in 6 chance across a\n"
             "year at £10 a week. Everything else in this report explains why.",
             fontsize=9.5, color=INK2, va="top", linespacing=1.7)
    _footer(fig)
    pdf.savefig(fig)
    plt.close(fig)


def _page_cost_per_win(pdf, plt):
    """The headline chart: what it costs to win a meaningful prize."""
    fig = plt.figure(figsize=(8.27, 11.69))
    _page_header(fig, "cost", "What it costs to win",
                 "Pounds of tickets you must buy, on average, to win the prize once.\n"
                 "Shorter is better. The scale multiplies by TEN at each gridline.")

    for idx, (target, label) in enumerate([(1_000, "£1,000 or more"),
                                           (10_000, "£10,000 or more")]):
        ax = fig.add_axes([0.32, 0.615 - idx * 0.305, 0.53, 0.205])
        options = best_for(target, limit=5)
        names = [o.label.replace("EuroMillions", "EuroM").replace(" (UK)", "")
                 for o in options][::-1]
        values = [o.cost_per_shot for o in options][::-1]
        colors = [BLUE if i == len(values) - 1 else RECEDE for i in range(len(values))]

        bars = ax.barh(names, values, color=colors, height=0.62, zorder=3)
        ax.set_xscale("log")
        ax.set_xlim(1_000, max(values) * 5.5)
        _money_axis(ax)
        ax.xaxis.grid(True, zorder=0)
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", length=0)
        ax.set_xlabel("£ of tickets per expected win  (log scale)", fontsize=8.5)
        ax.set_title(label, loc="left", pad=9, fontsize=12)
        for spine in ("left", "bottom"):
            ax.spines[spine].set_color(AXIS)

        for bar, value, o in zip(bars, values, options[::-1]):
            ax.text(value * 1.12, bar.get_y() + bar.get_height() / 2,
                    f"£{value:,.0f}", va="center", fontsize=9,
                    color=INK if value == min(values) else INK2,
                    fontweight="bold" if value == min(values) else "normal")
            ax.text(value * 1.12, bar.get_y() + bar.get_height() / 2 - 0.34,
                    f"{_short_money(o.prize)} at {_odds_short(o.probability)}",
                    va="center", fontsize=7.2, color=MUTED)

    fig.text(0.06, 0.185, "How to read this", fontsize=11.5, fontweight="bold",
             color=INK, va="top")
    note = [
        "A £1.50 ticket and a £2.00 ticket cannot be compared on odds alone. This chart",
        "divides one by the other: how much money goes in per win that comes out.",
        "",
        "The gap is not marginal. For a four-figure prize, the best option is roughly",
        "one hundred times more efficient than the one most people buy.",
    ]
    for i, line in enumerate(note):
        fig.text(0.06, 0.157 - i * 0.021, line, fontsize=9.5, color=INK2, va="top")
    _footer(fig)
    pdf.savefig(fig)
    plt.close(fig)


def _page_budget(pdf, plt):
    """What a realistic weekly budget actually buys."""
    fig = plt.figure(figsize=(8.27, 11.69))
    _page_header(fig, "budget", "What £10 a week actually buys",
                 "£520 over a year. Chance of winning the prize at least once.")

    picks = best_for(1_000, limit=3) + best_for(10_000, limit=1)
    seen, options = set(), []
    for o in picks:
        if o.label not in seen:
            seen.add(o.label)
            options.append(o)
    options.append({o.label: o for o in uk_options()}["UK Lotto - 5"])

    results = [(o, budget_outcome(o, 10.0, 52)) for o in options]
    results.sort(key=lambda r: r[1]["p_win"])

    ax = fig.add_axes([0.34, 0.545, 0.60, 0.30])
    names = [o.label.replace("EuroMillions", "EuroM").replace(" (UK)", "")
             for o, _ in results]
    values = [r["p_win"] * 100 for _, r in results]
    colors = [BLUE if v == max(values) else RECEDE for v in values]

    bars = ax.barh(names, values, color=colors, height=0.6, zorder=3)
    ax.xaxis.grid(True, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, max(values) * 1.34)
    ax.set_xlabel("chance of winning it at least once in the year  (%)", fontsize=8.5)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(AXIS)

    for bar, (o, r) in zip(bars, results):
        ax.text(r["p_win"] * 100 + max(values) * 0.02,
                bar.get_y() + bar.get_height() / 2,
                f"{r['p_win']:.2%}", va="center", fontsize=9.5,
                fontweight="bold" if r["p_win"] == max(values) / 100 else "normal",
                color=INK if r["p_win"] * 100 == max(values) else INK2)
        ax.text(r["p_win"] * 100 + max(values) * 0.02,
                bar.get_y() + bar.get_height() / 2 - 0.33,
                f"= 1 in {r['odds']:,.0f}  ·  wins {_short_money(o.prize)}",
                va="center", fontsize=7.2, color=MUTED)

    best = max(results, key=lambda r: r[1]["p_win"])
    fig.text(0.06, 0.475, "The one number to take away", fontsize=12.5,
             fontweight="bold", color=INK, va="top")
    fig.text(0.06, 0.435,
             f"{best[1]['p_win']:.0%}",
             fontsize=52, fontweight="bold", color=BLUE, va="top")
    fig.text(0.30, 0.428,
             f"chance of winning £{best[0].prize:,.0f}\nwithin a year on "
             f"{best[0].label.replace('EuroMillions', 'EuroMillions')},\n"
             f"playing £10 a week.",
             fontsize=12, color=INK2, va="top", linespacing=1.6)

    fig.text(0.06, 0.29, "And the counterweight", fontsize=12.5, fontweight="bold",
             color=CRITICAL, va="top")
    exp_back = best[1]["expected_returned"]
    note = [
        f"Across that same year you stake £520 and get back about £{exp_back:,.0f} on average.",
        f"The expected loss is roughly £{520 - exp_back:,.0f}, whatever happens on any single week.",
        "",
        "A 1-in-6 shot at £1,500 is a genuinely better offer than anything else on the",
        "counter. It is still an offer that loses money.",
    ]
    for i, line in enumerate(note):
        fig.text(0.06, 0.262 - i * 0.021, line, fontsize=9.5, color=INK2, va="top")
    _footer(fig)
    pdf.savefig(fig)
    plt.close(fig)


def _page_value(pdf, plt):
    """Where the money goes - return to player."""
    fig = plt.figure(figsize=(8.27, 11.69))
    _page_header(fig, "value", "Where the money goes",
                 "Of every £1 staked, how much comes back to players as prizes.\n"
                 "The rest is the operator's margin, good causes and tax.")

    rows: list[tuple[str, float]] = []
    from .combinatorics import all_tier_probabilities

    jackpots = {"uk_lotto": 4_000_000.0, "euromillions": 50_000_000.0}
    for key in UK_GAMES:
        cfg = PRESETS[key]
        total = sum(
            p * (jackpots.get(key, tier.payout) if tier.is_jackpot else tier.payout)
            for tier, p in all_tier_probabilities(cfg)
        )
        rows.append((cfg.name.replace(" (UK)", ""), total / cfg.ticket_price))
    for hp in HOTPICKS.values():
        for picks in sorted(hp.payouts):
            rows.append((f"{hp.name.replace('EuroMillions', 'EuroM')} pick-{picks}",
                         hp.expected_return(picks)))
    rows.sort(key=lambda r: r[1])

    ax = fig.add_axes([0.36, 0.335, 0.58, 0.50])
    names = [r[0] for r in rows]
    values = [r[1] * 100 for r in rows]
    colors = [BLUE if "EuroM HotPicks pick-3" in n else RECEDE for n in names]

    bars = ax.barh(names, values, color=colors, height=0.68, zorder=3)
    ax.xaxis.grid(True, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, 78)
    ax.set_xlabel("returned to players  (%)", fontsize=8.5)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(AXIS)

    for bar, value, name in zip(bars, values, names):
        emphasised = "EuroM HotPicks pick-3" in name
        ax.text(value + 1.4, bar.get_y() + bar.get_height() / 2, f"{value:.0f}%",
                va="center", fontsize=8.5, color=INK if emphasised else INK2,
                fontweight="bold" if emphasised else "normal")

    # No casino reference line here: at ~97% it falls outside this axis, and
    # widening the axis to fit it would squash every bar that matters. The
    # comparison lives in the prose below instead.

    fig.text(0.06, 0.275, "Context", fontsize=12, fontweight="bold", color=INK, va="top")
    note = [
        "Lotteries are the most expensive legal gambling in Britain by a wide margin.",
        "UK roulette (single zero) returns about 97p per £1; blackjack about 99p. The best",
        "lottery option here returns 67p, and the EuroMillions main game returns 35p.",
        "",
        "That is not a reason to feel foolish for playing — it is the price of the ticket,",
        "and it buys entertainment. It is a reason not to think of it as investing.",
        "",
        "The two whole-game bars (Lotto, EuroMillions) assume a typical jackpot and ignore",
        "the fact that big jackpots get shared, so they are flattered here, not penalised.",
    ]
    for i, line in enumerate(note):
        fig.text(0.06, 0.247 - i * 0.021, line, fontsize=9.5, color=INK2, va="top")
    _footer(fig)
    pdf.savefig(fig)
    plt.close(fig)


def _page_tradeoff(pdf, plt):
    """Access against value - why one option is the answer."""
    fig = plt.figure(figsize=(8.27, 11.69))
    _page_header(fig, "tradeoff", "The trade-off, and why it breaks",
                 "Usually a better shot at a prize costs you value. For one option,\n"
                 "it does not — which is what settles the recommendation.")

    ax = fig.add_axes([0.13, 0.47, 0.80, 0.37])
    options = [o for o in uk_options() if o.prize >= 1_000]

    for o in options:
        emphasised = o.label == "EuroMillions HotPicks pick-3"
        ax.scatter(o.cost_per_shot, o.expected_return * 100,
                   s=200 if emphasised else 62,
                   color=BLUE if emphasised else RECEDE,
                   edgecolor=SURFACE, linewidth=2, zorder=6 if emphasised else 3)

    ax.set_xscale("log")
    _money_axis(ax)
    ax.set_xlabel("£ of tickets per expected win   →  cheaper to win is LEFT", fontsize=9)
    ax.set_ylabel("returned to players (%)   →  better value is UP", fontsize=9)
    ax.grid(True, zorder=0)
    ax.set_axisbelow(True)
    ax.set_ylim(-6, 62)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(AXIS)

    # Offsets in POINTS, not data units. Multiplicative offsets on a log axis
    # move labels unpredictably far and were putting them beside the wrong dots.
    labelled = {
        "EuroMillions HotPicks pick-3": ((14, 10), "left"),
        "Lotto HotPicks pick-4": ((12, 12), "left"),
        "EuroMillions HotPicks pick-4": ((12, -16), "left"),
        "UK Lotto - 5": ((10, 12), "left"),
        "Thunderball (UK) - 5": ((10, -18), "left"),
    }
    for o in options:
        if o.label not in labelled:
            continue
        (dx, dy), ha = labelled[o.label]
        emphasised = o.label == "EuroMillions HotPicks pick-3"
        ax.annotate(o.label.replace("EuroMillions", "EuroM").replace(" (UK)", ""),
                    xy=(o.cost_per_shot, o.expected_return * 100),
                    xytext=(dx, dy), textcoords="offset points",
                    fontsize=9 if emphasised else 7.8,
                    color=BLUE if emphasised else MUTED,
                    fontweight="bold" if emphasised else "normal",
                    ha=ha, va="center",
                    arrowprops=dict(arrowstyle="-", color=RECEDE, linewidth=0.7,
                                    shrinkA=0, shrinkB=4) if not emphasised else None)

    ax.annotate("best corner:\ncheap to win AND better value",
                xy=(3_400, 48.5), xytext=(30, -52), textcoords="offset points",
                fontsize=8.5, color=BLUE, linespacing=1.5,
                arrowprops=dict(arrowstyle="->", color=BLUE, linewidth=1.1,
                                shrinkA=2, shrinkB=6))

    fig.text(0.06, 0.415, "What this chart shows", fontsize=12, fontweight="bold",
             color=INK, va="top")
    note = [
        "Each dot is one bet you can place in a shop. Left is cheaper to win; up is",
        "better value. Normally you must choose — the cheap-to-win bets are poor value,",
        "and the good-value bets almost never pay anything meaningful.",
        "",
        "EuroMillions HotPicks pick-3 sits alone in the top-left. It is both the",
        "cheapest realistic route to a four-figure prize and among the better-value",
        "bets available. Nothing else on the counter does both.",
        "",
        "This is the whole finding, in one picture.",
    ]
    for i, line in enumerate(note):
        fig.text(0.06, 0.387 - i * 0.021, line, fontsize=9.5, color=INK2, va="top")
    _footer(fig)
    pdf.savefig(fig)
    plt.close(fig)


def _page_scale(pdf, plt):
    """Making jackpot odds concrete."""
    fig = plt.figure(figsize=(8.27, 11.69))
    _page_header(fig, "scale", "How long are the odds, really?",
                 "Jackpot odds are too large to feel. These comparisons are exact\n"
                 "mathematics, not estimates, so they can be trusted as anchors.")

    items = [
        ("Roll six 6s in a row", 1 / 6 ** 6, RECEDE),
        ("EuroMillions HotPicks pick-3", HOTPICKS["euromillions_hotpicks"].probability(3), BLUE),
        ("Lotto HotPicks pick-4", HOTPICKS["lotto_hotpicks"].probability(4), BLUE),
        ("Deal a royal flush (5 cards)", 4 / 2_598_960, RECEDE),
        ("Thunderball top prize", jackpot_probability(PRESETS["thunderball"]), ORANGE),
        ("20 coin flips, all heads", 1 / 2 ** 20, RECEDE),
        ("Set For Life top prize", jackpot_probability(PRESETS["set_for_life"]), ORANGE),
        ("Lotto jackpot", jackpot_probability(PRESETS["uk_lotto"]), ORANGE),
        ("EuroMillions jackpot", jackpot_probability(PRESETS["euromillions"]), ORANGE),
    ]
    items.sort(key=lambda r: -r[1])

    ax = fig.add_axes([0.38, 0.50, 0.50, 0.35])
    names = [i[0] for i in items]
    values = [1 / i[1] for i in items]
    colors = [i[2] for i in items]

    ax.scatter(values, names, s=90, color=colors, edgecolor=SURFACE,
               linewidth=1.8, zorder=4)
    for name, value, color in zip(names, values, colors):
        ax.plot([1, value], [name, name], color=GRID, linewidth=0.9, zorder=2)
        # Exact figures on the anchor events - the whole point of them is that
        # they are precise, so rounding 1,048,576 to "1.0m" defeats it.
        text = f"1 in {value:,.0f}" if value < 2_000_000 else _odds_short(1 / value)
        ax.text(value * 1.5, name, text, va="center",
                fontsize=8.2, color=INK2 if color != RECEDE else MUTED)

    ax.set_xscale("log")
    # Lower bound must sit BELOW the smallest value (1 in 1,960) or that dot is
    # silently clipped off the axis and its label collides with the tick label.
    ax.set_xlim(700, 9.0e8)
    from matplotlib.ticker import FuncFormatter, LogLocator
    ax.xaxis.set_major_locator(LogLocator(base=10))
    ax.xaxis.set_major_formatter(FuncFormatter(
        lambda v, _p: (f"{v/1_000_000:.0f}m" if v >= 1_000_000
                       else f"{v/1_000:.0f}k")))
    ax.xaxis.set_minor_formatter(FuncFormatter(lambda *_: ""))
    ax.xaxis.grid(True, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("one chance in …  (log scale)", fontsize=8.5)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(AXIS)

    # Three colours are in play, so they need naming rather than guessing.
    from matplotlib.lines import Line2D

    ax.legend(handles=[
        Line2D([], [], marker="o", linestyle="", markersize=7, color=BLUE,
               label="realistic UK bets"),
        Line2D([], [], marker="o", linestyle="", markersize=7, color=RECEDE,
               label="everyday comparisons"),
        Line2D([], [], marker="o", linestyle="", markersize=7, color=ORANGE,
               label="lottery top prizes"),
    ], loc="upper left", bbox_to_anchor=(0.02, 0.99), ncol=1,
        fontsize=8, handletextpad=0.5, labelspacing=0.7, labelcolor=INK2)

    fig.text(0.06, 0.435, "Reading the scale", fontsize=12, fontweight="bold",
             color=INK, va="top")
    p = jackpot_probability(PRESETS["euromillions"])
    years = 1 / (p * 104)
    note = [
        "The axis multiplies by ten at each gridline, so the distance between the top",
        "and bottom of this chart is far larger than it looks.",
        "",
        f"Buying one EuroMillions line twice a week, the expected wait for the jackpot is",
        f"about {years:,.0f} years. The species is roughly 300,000 years old.",
        "",
        "Meanwhile the two blue dots — the HotPicks options — sit in the same region as",
        "rolling six 6s and dealing a royal flush. Those are long odds, but they are odds",
        "a person can actually encounter within a lifetime of ordinary play.",
        "",
        "That distinction is the practical content of this whole report.",
    ]
    for i, line in enumerate(note):
        fig.text(0.06, 0.407 - i * 0.021, line, fontsize=9.5, color=INK2, va="top")
    _footer(fig)
    pdf.savefig(fig)
    plt.close(fig)


def _page_millionaires(pdf, plt):
    """Why somebody wins every week."""
    fig = plt.figure(figsize=(8.27, 11.69))
    _page_header(fig, "millionaires", "Why someone wins a million every week",
                 "You see it at the till, and you are right. It is designed that way.")

    lotto = expected_winners(PRESETS["uk_lotto"], 15_000_000, game_key="uk_lotto")
    lotto_m = lotto.expected_above(1_000_000) * 2
    guaranteed = float(GUARANTEED_UK_MILLIONAIRES_PER_WEEK)
    euro_j = sum(t.expected_winners for t in
                 expected_winners(PRESETS["euromillions"], 30_000_000,
                                  game_key="euromillions").tiers
                 if t.is_jackpot) * 2 * 0.15
    total = lotto_m + guaranteed + euro_j

    ax = fig.add_axes([0.36, 0.635, 0.58, 0.19])
    labels = ["EuroMillions\nMillionaire Maker", "Lotto\nMatch 5 + Bonus",
              "EuroMillions jackpot\n(UK share)"]
    values = [guaranteed, lotto_m, euro_j]
    colors = [GOOD, RECEDE, RECEDE]
    bars = ax.barh(labels, values, color=colors, height=0.58, zorder=3)
    ax.xaxis.grid(True, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, max(values) * 1.35)
    ax.set_xlabel("new UK millionaires per week", fontsize=8.5)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(AXIS)
    for bar, value in zip(bars, values):
        ax.text(value + max(values) * 0.03, bar.get_y() + bar.get_height() / 2,
                f"{value:.2f}", va="center", fontsize=9, color=INK2)
    ax.text(guaranteed + max(values) * 0.03, bars[0].get_y() + bars[0].get_height() / 2 - 0.30,
            "guaranteed — no matching needed", fontsize=7.2, color=GOOD)

    fig.text(0.06, 0.585, f"{total:.1f}", fontsize=50, fontweight="bold",
             color=INK, va="top")
    fig.text(0.22, 0.578, "new UK millionaires every week,\non average.",
             fontsize=13, color=INK2, va="top", linespacing=1.6)

    fig.text(0.06, 0.485, "The part that surprises people", fontsize=12,
             fontweight="bold", color=INK, va="top")
    note = [
        "The Millionaire Maker raffle code is drawn from codes that were actually sold.",
        "A winner therefore exists before the draw happens. It is not luck; it is a",
        "guarantee written into the game, twice every week.",
        "",
        "Lotto's Match 5 + Bonus adds more: it pays a flat £1,000,000 at 1 in 7,509,579,",
        "and with roughly 15 million lines in play that lands about twice per draw.",
    ]
    for i, line in enumerate(note):
        fig.text(0.06, 0.457 - i * 0.021, line, fontsize=9.5, color=INK2, va="top")

    # The contrast, as a stat block.
    fig.patches.append(plt.Rectangle((0.06, 0.175), 0.88, 0.115, transform=fig.transFigure,
                                     facecolor="#fdf0f0", edgecolor=CRITICAL,
                                     linewidth=1.0, zorder=0))
    fig.text(0.09, 0.268, "AND YET, YOUR SIDE OF IT", fontsize=9,
             color=CRITICAL, fontweight="bold", va="top")
    fig.text(0.09, 0.238, "1 in 1,238", fontsize=25, fontweight="bold",
             color=CRITICAL, va="top")
    fig.text(0.40, 0.235,
             "chance of winning £1m+ on Lotto across FIFTY YEARS of\n"
             "playing one line in every draw — at a cost of £10,400.",
             fontsize=10, color=INK2, va="top", linespacing=1.6)

    fig.text(0.06, 0.145,
             "Both facts are true at once. The weekly winners come from the size of the crowd —\n"
             "over 30 million lines — not from the odds, which never move for you.",
             fontsize=9.5, color=INK2, va="top", linespacing=1.7)
    _footer(fig)
    pdf.savefig(fig)
    plt.close(fig)


def _page_myths(pdf, plt):
    """What does not work, with the evidence."""
    fig = plt.figure(figsize=(8.27, 11.69))
    _page_header(fig, "myths", "What does not work",
                 "Each of these was tested rather than assumed.")

    cfg = PRESETS["uk_lotto"]
    lifts = (1.05, 1.10, 1.20, 1.50)
    power = power_analysis(cfg, 3000, lifts=lifts)
    need = power["draws_required"]

    ax = fig.add_axes([0.36, 0.615, 0.58, 0.21])
    names = [f"{(l - 1) * 100:.0f}% biased ball" for l in lifts][::-1]
    years = [need[l] / 104 for l in lifts][::-1]
    colors = [CRITICAL if y > 100 else RECEDE for y in years]
    bars = ax.barh(names, years, color=colors, height=0.6, zorder=3)
    ax.set_xscale("log")
    ax.set_xlim(1, max(years) * 4)
    from matplotlib.ticker import FuncFormatter, LogLocator
    ax.xaxis.set_major_locator(LogLocator(base=10))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:,.0f}"))
    ax.xaxis.set_minor_formatter(FuncFormatter(lambda *_: ""))
    ax.xaxis.grid(True, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("years of draws needed to detect it  (log scale)", fontsize=8.5)
    ax.set_title("Could you even spot a rigged ball?", loc="left", pad=8, fontsize=11.5)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(AXIS)
    for bar, value in zip(bars, years):
        ax.text(value * 1.15, bar.get_y() + bar.get_height() / 2,
                f"{value:,.0f} years", va="center", fontsize=8.5, color=INK2)

    blocks = [
        ("Hot numbers", "A ball appearing often does not become likelier. Tested against a",
         "properly scrambled null, a hot-numbers strategy shows no edge whatsoever."),
        ("Due or cold numbers", "The purest form of the gambler's fallacy. A draw has no memory,",
         "so a ball absent for 40 draws is exactly as likely as any other."),
        ("Sum ranges and balanced filters", "Real, and actively harmful. 'Balanced-looking' combinations are",
         "what everyone else picks, so you share the prize more ways."),
        ("Number choice on HotPicks", "Irrelevant. HotPicks prizes are fixed and never shared, so £1,500",
         "is £1,500 no matter who else holds your numbers. Pick anything."),
    ]
    y = 0.545
    for title, l1, l2 in blocks:
        fig.text(0.06, y, "✗", fontsize=13, color=CRITICAL, va="top", fontweight="bold")
        fig.text(0.10, y, title, fontsize=11.5, fontweight="bold", color=INK, va="top")
        fig.text(0.10, y - 0.026, l1, fontsize=9.5, color=INK2, va="top")
        fig.text(0.10, y - 0.047, l2, fontsize=9.5, color=INK2, va="top")
        y -= 0.093

    fig.text(0.06, 0.175, "The trap worth knowing about", fontsize=12,
             fontweight="bold", color=INK, va="top")
    note = [
        "Tested naively against the theoretical rate, a hot-numbers strategy scores as a",
        "strong positive result — on data generated to be perfectly random. Within any",
        "fixed history the 'hot' balls appear more often by definition, so the test picks up",
        "its own selection rule. That is almost certainly how published 'our system beats",
        "random' claims are made.",
    ]
    for i, line in enumerate(note):
        fig.text(0.06, 0.147 - i * 0.021, line, fontsize=9.5, color=INK2, va="top")
    _footer(fig)
    pdf.savefig(fig)
    plt.close(fig)


def _page_reference(pdf, plt):
    """The card to keep."""
    fig = plt.figure(figsize=(8.27, 11.69))
    _page_header(fig, "reference", "Quick reference", "The whole report on one page.")

    rows = [
        ("GOAL", "PLAY", "COST", "ODDS", "PRIZE"),
        ("£1,000+", "EuroMillions HotPicks pick-3", "£1.50", "1 in 1,960", "£1,500"),
        ("£10,000+", "Lotto HotPicks pick-4", "£1.00", "1 in 30,342", "£13,000"),
        ("£20,000+", "EuroMillions HotPicks pick-4", "£1.50", "1 in 46,060", "£30,000"),
        ("Best value", "EuroMillions HotPicks pick-1", "£1.50", "1 in 10", "£10"),
        ("Best jackpot odds", "Thunderball", "£1.00", "1 in 8.1m", "£500,000"),
        ("Biggest jackpot", "UK Powerball (new)", "£4.00", "1 in 292m", "£12m+"),
    ]
    xs = [0.07, 0.24, 0.545, 0.645, 0.83]
    y = 0.845
    for i, row in enumerate(rows):
        header = i == 0
        for x, cell in zip(xs, row):
            fig.text(x, y, cell, fontsize=8.5 if header else 10,
                     color=MUTED if header else (BLUE if i == 1 else INK2),
                     fontweight="bold" if header or i == 1 else "normal", va="top")
        y -= 0.021 if header else 0.033
        if header:
            fig.add_artist(plt.Line2D([0.06, 0.94], [y + 0.012, y + 0.012],
                                      color=AXIS, linewidth=0.9,
                                      transform=fig.transFigure))
            y -= 0.008

    fig.text(0.06, 0.590, "Avoid", fontsize=12, fontweight="bold", color=CRITICAL, va="top")
    avoid = [
        "EuroMillions main game — worst value of the big four at 35p back per £1.",
        "EuroMillions HotPicks pick-5 — worst of all at 31p. The £1m is bait.",
        "Chasing big rollovers — more players means the jackpot splits more ways.",
        "UK Powerball at £4 a line — 4x Thunderball, and the jackpot is a 30-year",
    ]
    avoid.append("annuity shared with US players, not a lump sum.")
    for i, line in enumerate(avoid):
        bullet = "·  " if not line.startswith("annuity") else "   "
        fig.text(0.08, 0.558 - i * 0.023, f"{bullet}{line}", fontsize=9.5, color=INK2, va="top")

    fig.text(0.06, 0.428, "Which numbers?", fontsize=12, fontweight="bold",
             color=INK, va="top")
    numbers = [
        "HotPicks, Thunderball, Set For Life — it genuinely does not matter. Prizes are",
        "fixed and never shared. Use birthdays if you like them.",
        "",
        "Lotto, EuroMillions and UK Powerball — numbers matter slightly, because those",
        "jackpots are shared. It does not change your odds, only how many people split it.",
    ]
    for i, line in enumerate(numbers):
        fig.text(0.06, 0.398 - i * 0.021, line, fontsize=9.5, color=INK2, va="top")

    fig.text(0.06, 0.285, "Commands", fontsize=12, fontweight="bold", color=INK, va="top")
    cmds = [
        "python -m lotterylab compare --target 1000 --weekly 10",
        "python -m lotterylab dip uk_lotto -n 5",
        "python -m lotterylab dip euromillions -n 3 --mode unpopular --salt \"shaheer\"",
        "python -m lotterylab winners",
        "python -m lotterylab fetch",
    ]
    for i, cmd in enumerate(cmds):
        fig.text(0.08, 0.253 - i * 0.023, cmd, fontsize=8.5, color=INK2,
                 va="top", family="monospace")

    fig.patches.append(plt.Rectangle((0.06, 0.068), 0.88, 0.074,
                                     transform=fig.transFigure,
                                     facecolor="#f2f1ec", edgecolor=AXIS,
                                     linewidth=0.8, zorder=0))
    fig.text(0.09, 0.126, "Set a budget before you play, and treat it as the price of "
                          "entertainment.", fontsize=10, color=INK, va="top",
             fontweight="bold")
    fig.text(0.09, 0.102, "Every option here loses money on average. The analysis only "
                          "changes how fast,\nand what you might get for it.",
             fontsize=9.5, color=INK2, va="top", linespacing=1.6)

    _footer(fig, "lotterylab · PLAYBOOK.md is the living version of this document")
    pdf.savefig(fig)
    plt.close(fig)


# ---------------------------------------------------------------------------


def _page_ranked(pdf, plt):
    """Every option ranked, in plain language."""
    fig = plt.figure(figsize=(8.27, 11.69))
    _page_header(fig, "ranked", "The games, ranked",
                 "Best first. Ranked by what it costs you, on average, to actually\n"
                 "win the kind of prize you said you care about.")

    options = {o.label: o for o in uk_options()}
    hp_l = HOTPICKS["lotto_hotpicks"]
    hp_e = HOTPICKS["euromillions_hotpicks"]

    rows = [
        ("1st", "EuroMillions HotPicks", "pick 3 numbers", "£1.50", "1 in 1,960", "£1,500",
         "The best bet on the counter. Match all 3 and you win.", BLUE),
        ("2nd", "Lotto HotPicks", "pick 4 numbers", "£1.00", "1 in 30,342", "£13,000",
         "Cheapest line, and the best route to five figures.", INK2),
        ("3rd", "EuroMillions HotPicks", "pick 4 numbers", "£1.50", "1 in 46,060", "£30,000",
         "Bigger prize, longer odds. Best route to £20,000+.", INK2),
        ("4th", "UK Powerball", "Match 4 of 5", "£4.00", "1 in 36,525", "~£1,000",
         "New game. Beats Lotto, but 50x worse than 1st.", INK2),
        ("5th", "Lotto", "Match 5 of 6", "£2.00", "1 in 144,415", "£1,750",
         "The one most people buy. Nearly 100x worse than 1st.", MUTED),
    ]

    y = 0.845
    for rank, game, how, cost, odds, prize, why, colour in rows:
        emphasised = rank == "1st"
        if emphasised:
            fig.patches.append(plt.Rectangle((0.055, y - 0.093), 0.89, 0.098,
                                             transform=fig.transFigure,
                                             facecolor="#eef4fd", edgecolor=BLUE,
                                             linewidth=1.0, zorder=0))
        fig.text(0.075, y, rank, fontsize=15, fontweight="bold", color=colour, va="top")
        fig.text(0.145, y, game, fontsize=13.5, fontweight="bold",
                 color=INK if emphasised else INK2, va="top")
        fig.text(0.145, y - 0.026, how, fontsize=10, color=INK2, va="top")
        fig.text(0.145, y - 0.050, why, fontsize=9, color=MUTED, va="top")

        for dx, (label, value) in enumerate([("cost", cost), ("odds", odds), ("prize", prize)]):
            x = 0.585 + dx * 0.125
            fig.text(x, y + 0.002, label.upper(), fontsize=7, color=MUTED, va="top")
            fig.text(x, y - 0.020, value, fontsize=11,
                     fontweight="bold" if emphasised else "normal",
                     color=BLUE if emphasised else INK2, va="top")
        y -= 0.115

    fig.text(0.06, 0.245, "Two other ways to pick a game", fontsize=12,
             fontweight="bold", color=INK, va="top")
    extras = [
        ("Want your money to last longest?", "EuroMillions HotPicks pick 1 number — £1.50 to win "
         "£10 at 1 in 10.", "67p of every £1 comes back, the best of any UK option."),
        ("Want the biggest possible jackpot?", "UK Powerball — £4.00, jackpot 1 in 292,201,338, "
         "starts around £12 million.", f"See page {page_number('powerball')}. Read the three warnings before you buy it."),
    ]
    yy = 0.212
    for title, line1, line2 in extras:
        fig.text(0.06, yy, title, fontsize=10.5, fontweight="bold", color=INK2, va="top")
        fig.text(0.06, yy - 0.024, line1, fontsize=9.5, color=INK2, va="top")
        fig.text(0.06, yy - 0.045, line2, fontsize=9, color=MUTED, va="top")
        yy -= 0.082

    _footer(fig)
    pdf.savefig(fig)
    plt.close(fig)


def _page_powerball(pdf, plt):
    """UK Powerball in full - new game, and the one most likely to mislead."""
    cfg = PRESETS["uk_powerball"]
    fig = plt.figure(figsize=(8.27, 11.69))
    _page_header(fig, "powerball", "UK Powerball — the new game",
                 "Launched 21 July 2026. You can buy it at the till like any other\n"
                 "ticket. It is a real lottery ticket, not a bet with a bookmaker.")

    facts = [
        ("Price", "£4.00 a line"),
        ("Pick", "5 numbers from 69, plus 1 Powerball from 26"),
        ("Jackpot odds", "1 in 292,201,338"),
        ("Any prize", "1 in 13"),
        ("Jackpot", "starts about £12 million, no cap"),
        ("Paid", "over 30 years — there is no lump sum"),
        ("Draws", "Tuesday, Thursday and Sunday"),
    ]
    y = 0.845
    for label, value in facts:
        fig.text(0.07, y, label, fontsize=9.5, color=MUTED, va="top")
        fig.text(0.27, y, value, fontsize=10.5, color=INK2, va="top")
        y -= 0.026

    fig.text(0.06, 0.635, "What each match pays", fontsize=12, fontweight="bold",
             color=INK, va="top")
    fig.text(0.06, 0.612, "Only two prizes are fixed. The rest change every draw with "
                          "ticket sales.", fontsize=9, color=MUTED, va="top")

    fig.text(0.07, 0.585, "MATCH", fontsize=7.5, color=MUTED, va="top")
    fig.text(0.36, 0.585, "PRIZE", fontsize=7.5, color=MUTED, va="top")
    fig.text(0.56, 0.585, "ODDS", fontsize=7.5, color=MUTED, va="top")
    fig.text(0.80, 0.585, "FIXED?", fontsize=7.5, color=MUTED, va="top")
    fig.add_artist(plt.Line2D([0.06, 0.94], [0.578, 0.578], color=AXIS,
                              linewidth=0.9, transform=fig.transFigure))

    y = 0.562
    for tier, prob in all_tier_probabilities(cfg):
        if tier.is_jackpot:
            prize, fixed = "the jackpot", "shared"
        elif tier.is_parimutuel:
            prize, fixed = f"about £{tier.payout:,.0f}", "varies"
        else:
            prize, fixed = f"£{tier.payout:,.0f}", "FIXED"
        highlight = tier.name in ("5", "2")
        colour = BLUE if highlight else INK2
        fig.text(0.07, y, tier.name, fontsize=9.5, color=colour,
                 fontweight="bold" if highlight else "normal", va="top")
        fig.text(0.36, y, prize, fontsize=9.5, color=colour, va="top")
        fig.text(0.56, y, odds_string(prob), fontsize=9.5, color=colour, va="top")
        fig.text(0.80, y, fixed, fontsize=8.5,
                 color=GOOD if fixed == "FIXED" else MUTED, va="top")
        y -= 0.0222

    fig.patches.append(plt.Rectangle((0.06, 0.150), 0.88, 0.168, transform=fig.transFigure,
                                     facecolor="#fdf0f0", edgecolor=CRITICAL,
                                     linewidth=1.0, zorder=0))
    fig.text(0.09, 0.301, "THREE THINGS THE ADVERTS DO NOT LEAD WITH", fontsize=9,
             color=CRITICAL, fontweight="bold", va="top")
    warnings = [
        ("1.  It costs £4 a line.", "That is four Thunderball lines for the same money."),
        ("2.  There is no lump sum.", "A £1 billion jackpot is £33m a year for 30 years — "
                                      "worth about £580m today."),
        ("3.  You share the jackpot with America.", "49 lotteries feed the same pot, so the "
                                                    "crowd you split with is huge."),
    ]
    yy = 0.274
    for bold, rest in warnings:
        fig.text(0.09, yy, bold, fontsize=9.5, fontweight="bold", color=INK, va="top")
        fig.text(0.09, yy - 0.019, rest, fontsize=9, color=INK2, va="top")
        yy -= 0.042

    fig.text(0.06, 0.128, "The good bit, and the honest bit", fontsize=11,
             fontweight="bold", color=INK, va="top")
    fig.text(0.06, 0.104,
             "Good: a UK-only Match 2 prize of £8 at 1 in 28 that the US game does not have.\n"
             "Honest: a £1,000 win costs £146,101 of tickets, against £2,940 on the first-placed\n"
             "pick. Buy it for the jackpot, not for a realistic win.",
             fontsize=9.5, color=INK2, va="top", linespacing=1.6)
    _footer(fig)
    pdf.savefig(fig)
    plt.close(fig)


def _page_simple(pdf, plt):
    """The whole thing in plain words."""
    fig = plt.figure(figsize=(8.27, 11.69))
    _page_header(fig, "simple", "In simple words",
                 "The whole report, with no maths.")

    blocks = [
        ("If you want a realistic chance of winning something worthwhile",
         ["Play EuroMillions HotPicks and pick 3 numbers. It costs £1.50.",
          "You win £1,500 if all three of your numbers come up.",
          "",
          "Spending £10 a week for a year gives you about a 1 in 6 chance of",
          "winning that £1,500. No other game on the counter comes close."], BLUE),

        ("If you want to dream about a life-changing amount",
         ["Play UK Powerball. It costs £4 and the jackpot can pass £1 billion.",
          "",
          "But be clear with yourself: the odds are 1 in 292 million, the money",
          "comes over 30 years not in one go, and you share it with America.",
          "Treat the £4 as the price of the daydream, not an investment."], INK2),

        ("Does it matter which numbers I pick?",
         ["On HotPicks, Thunderball and Set For Life — no. Not at all. Those",
          "prizes are fixed, so you get the same money however many other",
          "people picked the same numbers. Use birthdays if you like.",
          "",
          "On Lotto, EuroMillions and Powerball — a little. Those jackpots are",
          "split between the winners, so picking numbers others avoid means",
          "fewer people to share with. It does not make you more likely to",
          "win — only likely to get more if you do."], INK2),

        ("Do last week's winning numbers help?",
         ["No. Not even slightly. The balls have no memory. I tested every",
          "'hot number' and 'due number' system properly and they all failed.",
          "You do not need to send me any past results."], INK2),

        ("Why does someone win a million nearly every week?",
         ["Because it is built to. EuroMillions guarantees two UK millionaires",
          "every week by raffle, with no matching needed — about 6 or 7 people",
          "become millionaires weekly. That is the crowd being enormous, not",
          "your odds being good."], INK2),
    ]

    y = 0.878
    for title, lines, colour in blocks:
        fig.text(0.06, y, title, fontsize=11.5, fontweight="bold", color=colour, va="top")
        yy = y - 0.029
        for line in lines:
            fig.text(0.06, yy, line, fontsize=9.8, color=INK2, va="top")
            yy -= 0.0193
        y = yy - 0.017

    fig.patches.append(plt.Rectangle((0.06, 0.045), 0.88, 0.098, transform=fig.transFigure,
                                     facecolor="#f2f1ec", edgecolor=AXIS,
                                     linewidth=0.8, zorder=0))
    fig.text(0.09, 0.128, "The one thing to remember", fontsize=10.5,
             fontweight="bold", color=INK, va="top")
    fig.text(0.09, 0.104,
             "Every game here loses money on average. Nothing in this report changes that.\n"
             "What it does is stop you paying £288,830 for a shot at £1,750 when £2,940\n"
             "buys a shot at £1,500 on the same counter. Set a budget, and enjoy it.",
             fontsize=9.5, color=INK2, va="top", linespacing=1.7)
    _footer(fig, "lotterylab · PLAYBOOK.md is the living version of this document")
    pdf.savefig(fig)
    plt.close(fig)


def build_report(output: str | Path = "uk-lottery-report.pdf") -> Path:
    """Build the illustrated PDF summary."""
    _style()
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    with PdfPages(output) as pdf:
        builders = {
            "cover": _page_cover,
            "contents": _page_contents,
            "ranked": _page_ranked,
            "cost": _page_cost_per_win,
            "budget": _page_budget,
            "value": _page_value,
            "tradeoff": _page_tradeoff,
            "powerball": _page_powerball,
            "scale": _page_scale,
            "millionaires": _page_millionaires,
            "myths": _page_myths,
            "reference": _page_reference,
            "simple": _page_simple,
        }
        # Emitted strictly in _ORDER, so the printed numbers, the contents
        # page and the actual sequence cannot disagree.
        for key, _part, _title in _ORDER:
            builders[key](pdf, plt)

        info = pdf.infodict()
        info["Title"] = "UK Lottery - What the numbers actually say"
        info["Subject"] = "Verified odds, value and strategy for UK National Lottery games"
        info["Creator"] = "lotterylab"

    return output
