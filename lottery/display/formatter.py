"""
Terminal output formatter. Uses `rich` if available, else plain ASCII.
"""

try:
    from rich.console import Console
    from rich.table import Table
    from rich import box
    from rich.panel import Panel
    from rich.rule import Rule
    _RICH = True
    _console = Console()
except ImportError:
    _RICH = False
    _console = None


def _fmt_money_eur(eur: float) -> str:
    if eur >= 1_000_000:
        return f"€{eur/1_000_000:.0f}M"
    if eur >= 1_000:
        return f"€{eur/1_000:.0f}K"
    return f"€{eur:.0f}"


def _fmt_money_gbp(pence: int) -> str:
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
# EV / Jackpot context
# ------------------------------------------------------------------ #

def print_ev_context(jackpot_eur: float):
    """Show jackpot EV analysis — call before printing picks."""
    from lottery.analysis.ev_calculator import expected_value, break_even_jackpot
    ev = expected_value(jackpot_eur)
    bep = break_even_jackpot()

    if _RICH:
        color = "bold green" if ev["is_positive_ev"] else (
            "yellow" if ev["ev_per_pound_spent"] > 0.65 else "dim"
        )
        lines = [
            f"  Jackpot:           [bold]{_fmt_money_eur(jackpot_eur)}[/bold]  "
            f"(break-even ≈ {_fmt_money_eur(bep)})",
            f"  Tickets sold est:  ~{ev['estimated_tickets_sold']/1_000_000:.0f}M",
            f"  Sharing factor:    {ev['sharing_factor']:.3f}×",
            f"  Total EV/ticket:   €{ev['total_ev']:.3f}  "
            f"({ev['ev_per_pound_spent']*100:.1f}p return per €1 spent)",
            f"  [{color}]{ev['verdict']}[/{color}]",
        ]
        _console.print(Panel("\n".join(lines), title="[bold]Jackpot EV Analysis[/bold]",
                              expand=False))
    else:
        bep_fmt = _fmt_money_eur(bep)
        print(f"\n  Jackpot EV Analysis")
        print(f"  Jackpot: {_fmt_money_eur(jackpot_eur)}  (break-even ≈ {bep_fmt})")
        print(f"  EV/ticket: €{ev['total_ev']:.3f}  ({ev['ev_per_pound_spent']*100:.1f}p per €1)")
        print(f"  {ev['verdict']}")


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
        prize = _fmt_money_gbp(tier.fixed_value * 100) if tier.fixed_value else "Jackpot share"
        if tier.prize_type == "monthly":
            prize = "£10K/mo×30yr"
        t.add_row(tier.name, _fmt_odds(tier.odds), _fmt_prob(tier.odds), prize, tier.description)
    _console.print(t)
    _console.print(f"  Ticket: £{game.ticket_cost_gbp:.2f}  |  Draws: {', '.join(game.draw_days)}\n")


def _ascii_odds_table(game):
    print(f"\n{'='*70}\n  {game.display_name} — Prize Tiers\n{'='*70}")
    print(f"  {'Tier':<30} {'Odds':<18} {'Prob':<14} Prize")
    print(f"  {'-'*66}")
    for tier in game.prize_tiers:
        prize = _fmt_money_gbp(tier.fixed_value * 100) if tier.fixed_value else "Jackpot"
        if tier.prize_type == "monthly":
            prize = "£10K/mo×30yr"
        print(f"  {tier.name:<30} {_fmt_odds(tier.odds):<18} {_fmt_prob(tier.odds):<14} {prize}")
    print(f"\n  Ticket: £{game.ticket_cost_gbp:.2f}  |  Draws: {', '.join(game.draw_days)}\n")


# ------------------------------------------------------------------ #
# Pick results
# ------------------------------------------------------------------ #

def print_picks(picks: list, game_config, strategy: str, jackpot_eur: float = None):
    if jackpot_eur and game_config.slug == "euromillions":
        print_ev_context(jackpot_eur)
    if _RICH:
        _rich_picks(picks, game_config, strategy)
    else:
        _ascii_picks(picks, game_config, strategy)


def _label_bonus(game) -> str:
    labels = {
        "lotto": "Bonus",
        "euromillions": "⭐ Lucky Stars",
        "set-for-life": "Life Ball",
        "thunderball": "Thunderball",
    }
    return labels.get(game.slug, "Bonus")


def _rich_picks(picks, game, strategy):
    _console.print()
    _console.print(Panel(
        f"[bold green]{game.display_name}[/bold green] — Smart Picks  "
        f"[dim](strategy: {strategy} | v2 research-calibrated)[/dim]",
        expand=False,
    ))
    bonus_label = _label_bonus(game)
    for i, pick in enumerate(picks, 1):
        main_str = "  ".join(f"[bold yellow]{n:2d}[/bold yellow]" for n in sorted(pick.main_balls))
        bonus_str = ", ".join(str(b) for b in pick.bonus_balls)
        _console.rule(f"[dim] Pick {i} [/dim]")
        _console.print(f"  {main_str}   [cyan]{bonus_label}: {bonus_str}[/cyan]")
        _console.print(
            f"  [bold]{pick.ev_multiplier:.1f}×[/bold] EV  |  "
            f"Sum: {pick.ball_sum}  |  "
            f"Spread: {pick.spread}  |  "
            f"Odd/Even: {pick.odd_count}/{game.main_pick - pick.odd_count}  |  "
            f"Birthday nums: {pick.birthday_count}"
        )
        _console.print(f"  [dim]{pick.rationale}[/dim]")
    _console.print()
    _console.print(
        "[bold]EV multiplier[/bold]: if you win, your expected jackpot share is this many "
        "times larger than an average ticket (research-calibrated bias model)."
    )
    _console.print()


def _ascii_picks(picks, game, strategy):
    bonus_label = _label_bonus(game)
    print(f"\n{'='*70}\n  {game.display_name} — Smart Picks (strategy: {strategy})\n{'='*70}")
    for i, pick in enumerate(picks, 1):
        main_str = "  ".join(f"{n:2d}" for n in sorted(pick.main_balls))
        bonus_str = ", ".join(str(b) for b in pick.bonus_balls)
        print(f"\n  Pick {i}:  {main_str}   {bonus_label}: {bonus_str}")
        print(f"    EV: {pick.ev_multiplier:.1f}×  Sum: {pick.ball_sum}  "
              f"Spread: {pick.spread}  Odd/Even: {pick.odd_count}/{game.main_pick - pick.odd_count}  "
              f"Birthday: {pick.birthday_count}")
        print(f"    {pick.rationale}")
    print()


# ------------------------------------------------------------------ #
# Stats
# ------------------------------------------------------------------ #

def print_frequency_stats(summary: list, game_config, last_n: int):
    if _RICH:
        _rich_stats(summary, game_config, last_n)
    else:
        _ascii_stats(summary, game_config, last_n)


def _rich_stats(summary, game, last_n):
    t = Table(
        title=f"[bold]{game.display_name}[/bold] — Ball Frequency  [dim]({last_n} draws)[/dim]",
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
            status, style = "—", "dim"
        t.add_row(str(row["ball"]), str(row["count"]), str(row["expected"]),
                  f"[{style}]{dev:+.1f}%[/{style}]", f"[{style}]{status}[/{style}]")
    _console.print(t)


def _ascii_stats(summary, game, last_n):
    print(f"\n{game.display_name} — Ball Frequency ({last_n} draws)")
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
            t.add_row(slug, game.display_name, f"1–{game.main_pool}", str(game.main_pick),
                      f"1–{game.bonus_pool} (×{game.bonus_count})",
                      ", ".join(game.draw_days), f"£{game.ticket_cost_gbp:.2f}")
        _console.print(t)
    else:
        print("\nAvailable Games:")
        for slug, game in registry.items():
            print(f"  {slug:<15} {game.display_name:<15}  "
                  f"Pick {game.main_pick} from 1–{game.main_pool}  "
                  f"+ {game.bonus_count} bonus from 1–{game.bonus_pool}  "
                  f"Draws: {', '.join(game.draw_days)}")
        print()
