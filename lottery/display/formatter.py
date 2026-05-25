"""
Terminal output formatter. Uses `rich` if available, else falls back to plain ASCII.
"""
import math

try:
    from rich.console import Console
    from rich.table import Table
    from rich import box
    from rich.panel import Panel
    from rich.text import Text
    from rich.style import Style
    _RICH = True
    _console = Console()
except ImportError:
    _RICH = False
    _console = None


def _fmt_money(pence: int) -> str:
    if pence == 0:
        return "varies"
    gbp = pence / 100
    if gbp >= 1_000_000:
        return f"£{gbp/1_000_000:.1f}M"
    if gbp >= 1_000:
        return f"£{gbp/1_000:.0f}K"
    return f"£{gbp:.0f}"


def _fmt_odds(odds: int) -> str:
    if odds >= 1_000_000:
        return f"1 in {odds/1_000_000:.1f}M"
    if odds >= 1_000:
        return f"1 in {odds/1_000:.0f}K"
    return f"1 in {odds:,}"


def _fmt_prob(odds: int) -> str:
    if odds <= 0:
        return "N/A"
    pct = 100 / odds
    if pct < 0.001:
        return f"{pct:.2e}%"
    return f"{pct:.4f}%"


# ------------------------------------------------------------------ #
# Odds table
# ------------------------------------------------------------------ #

def print_odds_table(game_config):
    if _RICH:
        _rich_odds_table(game_config)
    else:
        _ascii_odds_table(game_config)


def _rich_odds_table(game):
    t = Table(title=f"[bold]{game.display_name}[/bold] — Prize Tiers",
              box=box.ROUNDED, show_lines=True)
    t.add_column("Tier", style="cyan", no_wrap=True)
    t.add_column("Odds", justify="right")
    t.add_column("Probability", justify="right")
    t.add_column("Prize", justify="right", style="green")
    t.add_column("Notes", style="dim")

    for tier in game.prize_tiers:
        prize = _fmt_money(tier.fixed_value * 100) if tier.fixed_value else "Jackpot share"
        if tier.prize_type == "monthly":
            prize = "£10K/mo × 30yr"
        t.add_row(
            tier.name,
            _fmt_odds(tier.odds),
            _fmt_prob(tier.odds),
            prize,
            tier.description,
        )
    _console.print(t)
    _console.print(f"  Ticket cost: £{game.ticket_cost_gbp:.2f}  |  "
                   f"Draws: {', '.join(game.draw_days)}\n")


def _ascii_odds_table(game):
    print(f"\n{'='*70}")
    print(f"  {game.display_name} — Prize Tiers")
    print(f"{'='*70}")
    print(f"  {'Tier':<30} {'Odds':<18} {'Probability':<14} Prize")
    print(f"  {'-'*66}")
    for tier in game.prize_tiers:
        prize = _fmt_money(tier.fixed_value * 100) if tier.fixed_value else "Jackpot"
        if tier.prize_type == "monthly":
            prize = "£10K/mo×30yr"
        print(f"  {tier.name:<30} {_fmt_odds(tier.odds):<18} {_fmt_prob(tier.odds):<14} {prize}")
    print(f"\n  Ticket cost: £{game.ticket_cost_gbp:.2f}  |  Draws: {', '.join(game.draw_days)}\n")


# ------------------------------------------------------------------ #
# Pick results
# ------------------------------------------------------------------ #

def print_picks(picks: list, game_config, strategy: str):
    if _RICH:
        _rich_picks(picks, game_config, strategy)
    else:
        _ascii_picks(picks, game_config, strategy)


def _format_main_balls(balls: tuple) -> str:
    return "  ".join(f"{n:2d}" for n in sorted(balls))


def _format_bonus_balls(balls: tuple, game) -> str:
    if not balls:
        return ""
    label = {1: "Lucky Stars", 2: "Lucky Stars"}.get(game.bonus_count, "Bonus")
    if game.slug == "lotto":
        label = "Bonus"
    elif game.slug == "set-for-life":
        label = "Life Ball"
    elif game.slug == "thunderball":
        label = "Thunderball"
    return f"  +  {label}: {', '.join(str(b) for b in balls)}"


def _rich_picks(picks, game, strategy):
    header = f"[bold green]{game.display_name}[/bold green] — Smart Picks  " \
             f"[dim](strategy: {strategy})[/dim]"
    _console.print()
    _console.print(Panel(header, expand=False))

    for i, pick in enumerate(picks, 1):
        main = _format_main_balls(pick.main_balls)
        bonus = _format_bonus_balls(pick.bonus_balls, game)
        line1 = f"  [bold yellow]{main}[/bold yellow][cyan]{bonus}[/cyan]"

        stats = (
            f"  EV multiplier: [bold]{pick.ev_multiplier:.2f}×[/bold]  |  "
            f"Numbers >31: {sum(1 for n in pick.main_balls if n > 31)}/{game.main_pick}  |  "
            f"Spread: {pick.spread}  |  "
            f"Birthday nums: {pick.birthday_count}"
        )
        rationale = f"  [dim]{pick.rationale}[/dim]"

        _console.rule(f"[dim] Pick {i} [/dim]")
        _console.print(line1)
        _console.print(stats)
        _console.print(rationale)

    _console.print()
    _console.print(
        "[bold]EV multiplier[/bold]: if you win the jackpot, your expected share is this many "
        "times larger than an average ticket (due to fewer people choosing the same numbers)."
    )
    _console.print()


def _ascii_picks(picks, game, strategy):
    print(f"\n{'='*70}")
    print(f"  {game.display_name} — Smart Picks  (strategy: {strategy})")
    print(f"{'='*70}")
    for i, pick in enumerate(picks, 1):
        main = _format_main_balls(pick.main_balls)
        bonus = _format_bonus_balls(pick.bonus_balls, game)
        print(f"\n  Pick {i}:  {main}{bonus}")
        print(f"    EV multiplier: {pick.ev_multiplier:.2f}×  |  "
              f"Numbers >31: {sum(1 for n in pick.main_balls if n > 31)}/{game.main_pick}  |  "
              f"Spread: {pick.spread}  |  Birthday nums: {pick.birthday_count}")
        print(f"    {pick.rationale}")
    print()
    print("  EV multiplier: if you win, your expected jackpot share is this many")
    print("  times larger than an average ticket (fewer people chose the same numbers).")
    print()


# ------------------------------------------------------------------ #
# Stats / frequency table
# ------------------------------------------------------------------ #

def print_frequency_stats(summary: list, game_config, last_n: int):
    if _RICH:
        _rich_stats(summary, game_config, last_n)
    else:
        _ascii_stats(summary, game_config, last_n)


def _rich_stats(summary, game, last_n):
    t = Table(
        title=f"[bold]{game.display_name}[/bold] — Ball Frequency  [dim](last {last_n} draws)[/dim]",
        box=box.SIMPLE_HEAVY,
    )
    t.add_column("Ball", justify="right", style="cyan")
    t.add_column("Drawn", justify="right")
    t.add_column("Expected", justify="right", style="dim")
    t.add_column("Deviation", justify="right")
    t.add_column("Status", justify="center")

    for row in summary:
        dev = row["deviation"]
        if dev > 10:
            status, style = "HOT", "bold red"
        elif dev < -10:
            status, style = "COLD", "bold blue"
        else:
            status, style = "normal", "dim"
        dev_str = f"{dev:+.1f}%"
        t.add_row(
            str(row["ball"]),
            str(row["count"]),
            str(row["expected"]),
            f"[{style}]{dev_str}[/{style}]",
            f"[{style}]{status}[/{style}]",
        )
    _console.print(t)


def _ascii_stats(summary, game, last_n):
    print(f"\n{game.display_name} — Ball Frequency (last {last_n} draws)")
    print(f"  {'Ball':>4}  {'Drawn':>6}  {'Expected':>8}  {'Deviation':>10}  Status")
    print(f"  {'-'*50}")
    for row in summary:
        dev = row["deviation"]
        status = "HOT" if dev > 10 else ("COLD" if dev < -10 else "")
        print(f"  {row['ball']:>4}  {row['count']:>6}  {row['expected']:>8}  "
              f"{dev:>+9.1f}%  {status}")
    print()


# ------------------------------------------------------------------ #
# Games list
# ------------------------------------------------------------------ #

def print_games_list(registry: dict):
    if _RICH:
        t = Table(title="Available Games", box=box.ROUNDED)
        t.add_column("Slug", style="cyan")
        t.add_column("Name")
        t.add_column("Main Pool")
        t.add_column("Pick")
        t.add_column("Bonus Pool")
        t.add_column("Draws")
        t.add_column("Ticket")
        for slug, game in registry.items():
            t.add_row(
                slug, game.display_name,
                f"1–{game.main_pool}", str(game.main_pick),
                f"1–{game.bonus_pool} (×{game.bonus_count})",
                ", ".join(game.draw_days),
                f"£{game.ticket_cost_gbp:.2f}",
            )
        _console.print(t)
    else:
        print("\nAvailable Games:")
        for slug, game in registry.items():
            print(f"  {slug:<15} {game.display_name:<15}  "
                  f"Pick {game.main_pick} from 1–{game.main_pool}  "
                  f"+ {game.bonus_count} bonus from 1–{game.bonus_pool}  "
                  f"Draws: {', '.join(game.draw_days)}")
        print()
