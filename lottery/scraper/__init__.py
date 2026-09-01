from lottery.scraper.cache import DrawCache, DrawResult
from lottery.scraper.national_lottery import NationalLotteryXMLScraper
from lottery.scraper.lottery_co_uk import LotteryCoUkScraper


class ScraperUnavailableError(Exception):
    pass


class NoDataSourceError(Exception):
    pass


def fetch_draws(game_config, force_refresh: bool = False) -> list:
    """
    Fetch draw history for a game using the fallback chain:
      1. Cached CSV (if fresh)
      2. National Lottery XML feed
      3. lottery.co.uk HTML stats (aggregate only)
    """
    cache = DrawCache()

    if not force_refresh and not cache.is_stale(game_config.slug):
        draws = cache.load(game_config.slug)
        if draws:
            return draws

    # Try primary XML scraper
    try:
        scraper = NationalLotteryXMLScraper()
        draws = scraper.fetch(game_config)
        if draws:
            cache.save(game_config.slug, draws)
            return draws
    except Exception:
        pass

    # Try HTML fallback (returns aggregate stats, not individual draws)
    try:
        scraper = LotteryCoUkScraper()
        draws = scraper.fetch(game_config)
        if draws:
            cache.save(game_config.slug, draws)
            return draws
    except Exception:
        pass

    # Return stale cache if available
    draws = cache.load(game_config.slug)
    if draws:
        return draws

    raise NoDataSourceError(
        f"No data available for '{game_config.slug}'.\n"
        "Try running with internet access, or place a seed CSV at "
        f"data/cache/{game_config.slug}.csv"
    )
