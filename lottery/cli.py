import sys
from datetime import datetime, timezone

import click

from lottery.games import REGISTRY, get_game
from lottery.scraper import fetch_draws, NoDataSourceError
from lottery.scraper.cache import DrawCache
from lottery.analysis.frequency import DrawFrequencyAnalyzer
from lottery.picker.smart_picker import SmartPicker
from lottery.display.formatter import (
    print_odds_table,
    print_picks,
    print_frequency_stats,
    print_games_list,
)


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _load_draws(game_config, offline: bool = False, force: bool = False):
    if offline:
        cache = DrawCache()
        draws = cache.load(game_config.slug)
        if not draws:
            click.echo(
                f"No cached data for {game_config.slug}. "
                "Run without --offline first to populate the cache.",
                err=True,
            )
            sys.exit(1)
        return draws
    try:
        return fetch_draws(game_config, force_refresh=force)
    except NoDataSourceError as e:
        click.echo(str(e), err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Warning: could not fetch live data ({e}). Trying cache...", err=True)
        cache = DrawCache()
        draws = cache.load(game_config.slug)
        if not draws:
            click.echo("No cached data available either. Aborting.", err=True)
            sys.exit(1)
        click.echo(f"Using {len(draws)} cached draws for {game_config.display_name}.", err=True)
        return draws


# ------------------------------------------------------------------ #
# CLI root
# ------------------------------------------------------------------ #

@click.group()
@click.version_option("1.0.0", prog_name="lottery")
def cli():
    """
    UK National Lottery smart number picker.

    Picks numbers that maximise your expected jackpot share by targeting
    statistically under-chosen combinations.
    """
    pass


# ------------------------------------------------------------------ #
# pick
# ------------------------------------------------------------------ #

@cli.command()
@click.argument("game", default="euromillions",
                type=click.Choice(list(REGISTRY.keys()), case_sensitive=False))
@click.option("--count", "-n", default=5, show_default=True,
              help="Number of picks to generate")
@click.option("--strategy", "-s",
              type=click.Choice(["ev"]), default="ev", show_default=True,
              help="ev=max expected jackpot share (only strategy with academic support)")
@click.option("--offline", is_flag=True,
              help="Use cached data only, no network requests")
@click.option("--bias-preset", default="research", show_default=True,
              type=click.Choice(["research", "conservative"]),
              help="Calibration preset for human-picking bias model")
@click.option("--jackpot", "-j", default=None, type=float,
              help="Current jackpot in millions EUR (e.g. 130 for €130M). Shows EV analysis.")
def pick(game, count, strategy, offline, bias_preset, jackpot):
    """Generate smart number picks for GAME (default: euromillions)."""
    game_config = get_game(game)
    click.echo(f"\nLoading draw history for {game_config.display_name}...")
    draws = _load_draws(game_config, offline=offline)
    click.echo(f"Analysing {len(draws)} historical draws...")

    picker = SmartPicker(
        game_config=game_config,
        draws=draws,
        strategy=strategy,
        bias_preset=bias_preset,
    )
    picks = picker.generate(count=count)
    jackpot_eur = jackpot * 1_000_000 if jackpot else None
    print_picks(picks, game_config, strategy, jackpot_eur=jackpot_eur)


# ------------------------------------------------------------------ #
# stats
# ------------------------------------------------------------------ #

@cli.command()
@click.argument("game", default="lotto",
                type=click.Choice(list(REGISTRY.keys()), case_sensitive=False))
@click.option("--last-draws", "-n", default=104, show_default=True,
              help="Restrict analysis to this many most recent draws (~2 years)")
@click.option("--offline", is_flag=True)
@click.option("--since", default=None,
              help="Only include draws since this date (YYYY-MM-DD). "
                   "Useful to restrict Lotto to post-2015 pool change.")
def stats(game, last_draws, offline, since):
    """Show ball frequency statistics for GAME."""
    game_config = get_game(game)
    draws = _load_draws(game_config, offline=offline)

    since_date = None
    if since:
        try:
            since_date = datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            click.echo("Invalid date format. Use YYYY-MM-DD.", err=True)
            sys.exit(1)

    analyzer = DrawFrequencyAnalyzer(draws, game_config)
    summary = analyzer.number_summary(since_date=since_date)

    effective_draws = len([d for d in draws if since_date is None or d.draw_date >= since_date])
    effective_n = min(last_draws, effective_draws)

    hot = analyzer.hot_balls(top_n=5, since_date=since_date)
    cold = analyzer.cold_balls(top_n=5, since_date=since_date)
    overdue = analyzer.overdue_balls(threshold_draws=20)

    click.echo(f"\n  Draws analysed: {effective_draws}")
    click.echo(f"  Hot balls (most drawn): {hot}")
    click.echo(f"  Cold balls (least drawn): {cold}")
    click.echo(f"  Overdue (not seen in last 20 draws): {overdue}")

    print_frequency_stats(summary, game_config, effective_n)


# ------------------------------------------------------------------ #
# odds
# ------------------------------------------------------------------ #

@cli.command()
@click.argument("game", default="lotto",
                type=click.Choice(list(REGISTRY.keys()), case_sensitive=False))
def odds(game):
    """Display all prize tiers and exact odds for GAME."""
    game_config = get_game(game)
    print_odds_table(game_config)


# ------------------------------------------------------------------ #
# update
# ------------------------------------------------------------------ #

@cli.command()
@click.option("--game", "-g", default="all",
              help="Game slug to update, or 'all'")
def update(game):
    """Force-refresh the draw history cache from National Lottery."""
    games = list(REGISTRY.values()) if game == "all" else [get_game(game)]
    for g in games:
        click.echo(f"Updating {g.display_name}...")
        try:
            draws = fetch_draws(g, force_refresh=True)
            click.echo(f"  {len(draws)} draws cached for {g.display_name}.")
        except Exception as e:
            click.echo(f"  Failed: {e}", err=True)


# ------------------------------------------------------------------ #
# games
# ------------------------------------------------------------------ #

@cli.command("games")
def list_games():
    """List all supported lottery games."""
    print_games_list(REGISTRY)
