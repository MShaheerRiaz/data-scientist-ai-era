"""
Fallback scraper for lottery.co.uk statistics pages.
Returns synthesised DrawResult objects built from aggregate frequency data.
Not individual draws — used as a supplement when XML feed is unavailable.
"""
from datetime import datetime, timezone

import requests

from lottery.scraper.cache import DrawResult

STATS_URL = "https://www.lottery.co.uk/{slug}/statistics"

SLUG_MAP = {
    "lotto": "lotto",
    "euromillions": "euromillions",
    "set-for-life": "set-for-life",
    "thunderball": "thunderball",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


class LotteryCoUkScraper:
    def fetch(self, game_config) -> list:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise RuntimeError("beautifulsoup4 not installed — cannot use HTML fallback")

        slug = SLUG_MAP.get(game_config.slug, game_config.slug)
        url = STATS_URL.format(slug=slug)
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        return self._parse_frequency_table(soup, game_config)

    def _parse_frequency_table(self, soup, game_config) -> list:
        """
        Parse the frequency table and synthesise a single pseudo-draw per
        number that represents its historical frequency. This is used only
        for the frequency analyser — the draw_number field encodes frequency.
        """
        draws = []
        tables = soup.find_all("table")
        freq_map = {}

        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
                if len(cells) >= 2:
                    try:
                        ball_num = int(cells[0])
                        frequency = int(cells[1].replace(",", ""))
                        freq_map[ball_num] = frequency
                    except (ValueError, IndexError):
                        continue

        if not freq_map:
            return []

        # Build synthetic draw records: one per draw_number to represent frequency
        # Each "draw" has a single ball — the analyser aggregates counts from these
        max_freq = max(freq_map.values()) if freq_map else 1
        for ball_num, freq in freq_map.items():
            # Create synthetic draws proportional to frequency
            for i in range(freq):
                draws.append(DrawResult(
                    draw_date=datetime(2000, 1, 1, tzinfo=timezone.utc),
                    draw_number=i + 1,
                    main_balls=(ball_num,),
                    bonus_balls=(),
                    jackpot_value=0,
                ))
        return draws
