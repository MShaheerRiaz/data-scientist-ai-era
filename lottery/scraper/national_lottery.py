import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests

from lottery.scraper.cache import DrawResult

DRAW_HISTORY_URL = "https://www.national-lottery.co.uk/results/{slug}/draw-history/xml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/xml, text/xml, */*",
}


class NationalLotteryXMLScraper:
    def fetch(self, game_config) -> list:
        url = DRAW_HISTORY_URL.format(slug=game_config.xml_slug)
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return self._parse(game_config.slug, resp.content)

    def _parse(self, slug: str, content: bytes) -> list:
        root = ET.fromstring(content)
        draws = []
        # The XML structure varies slightly per game; try common patterns
        for draw_elem in root.iter("draw"):
            try:
                result = self._parse_draw(slug, draw_elem)
                if result:
                    draws.append(result)
            except (ValueError, AttributeError, TypeError):
                continue
        return draws

    def _parse_draw(self, slug: str, elem) -> DrawResult | None:
        # Draw number
        num_text = elem.findtext("drawNumber") or elem.findtext("id") or "0"
        draw_number = int(num_text)

        # Draw date
        date_text = elem.findtext("drawDate") or elem.findtext("date") or ""
        if not date_text:
            return None
        try:
            draw_date = datetime.strptime(date_text.strip(), "%d-%b-%Y").replace(tzinfo=timezone.utc)
        except ValueError:
            try:
                draw_date = datetime.fromisoformat(date_text.strip()).replace(tzinfo=timezone.utc)
            except ValueError:
                return None

        jackpot = 0
        jackpot_text = elem.findtext("jackpot") or elem.findtext("prizePool") or "0"
        try:
            jackpot = int(float(jackpot_text.replace(",", "").replace("£", "").strip()) * 100)
        except (ValueError, AttributeError):
            pass

        # Ball numbers vary per game
        if slug == "lotto":
            return self._parse_lotto(elem, draw_number, draw_date, jackpot)
        elif slug == "euromillions":
            return self._parse_euromillions(elem, draw_number, draw_date, jackpot)
        elif slug == "set-for-life":
            return self._parse_setforlife(elem, draw_number, draw_date, jackpot)
        elif slug == "thunderball":
            return self._parse_thunderball(elem, draw_number, draw_date, jackpot)
        return None

    def _get_balls(self, elem, tag_patterns: list[str]) -> list[int]:
        for tag in tag_patterns:
            found = [e.text for e in elem.findall(tag) if e.text]
            if found:
                return [int(v.strip()) for v in found]
        # Try numbered tags: ball1, ball2, ...
        balls = []
        for i in range(1, 10):
            for prefix in ("ball", "Ball", "number", "Number"):
                val = elem.findtext(f"{prefix}{i}")
                if val:
                    balls.append(int(val.strip()))
                    break
        return balls

    def _parse_lotto(self, elem, num, date, jackpot) -> DrawResult | None:
        mains = self._get_balls(elem, ["ball", "mainNumbers/ball"])
        bonus_text = elem.findtext("bonusBall") or elem.findtext("bonus")
        if len(mains) < 6 or not bonus_text:
            return None
        return DrawResult(
            draw_date=date, draw_number=num,
            main_balls=tuple(sorted(mains[:6])),
            bonus_balls=(int(bonus_text.strip()),),
            jackpot_value=jackpot,
        )

    def _parse_euromillions(self, elem, num, date, jackpot) -> DrawResult | None:
        mains = self._get_balls(elem, ["ball", "mainNumbers/ball"])
        stars = [e.text for e in elem.findall("luckyStars/star") if e.text]
        if not stars:
            stars = [e.text for e in elem.findall("star") if e.text]
        if len(mains) < 5 or len(stars) < 2:
            return None
        return DrawResult(
            draw_date=date, draw_number=num,
            main_balls=tuple(sorted(int(v) for v in mains[:5])),
            bonus_balls=tuple(sorted(int(v) for v in stars[:2])),
            jackpot_value=jackpot,
        )

    def _parse_setforlife(self, elem, num, date, jackpot) -> DrawResult | None:
        mains = self._get_balls(elem, ["ball", "mainNumbers/ball"])
        life = elem.findtext("lifeBall") or elem.findtext("bonusBall")
        if len(mains) < 5 or not life:
            return None
        return DrawResult(
            draw_date=date, draw_number=num,
            main_balls=tuple(sorted(mains[:5])),
            bonus_balls=(int(life.strip()),),
            jackpot_value=jackpot,
        )

    def _parse_thunderball(self, elem, num, date, jackpot) -> DrawResult | None:
        mains = self._get_balls(elem, ["ball", "mainNumbers/ball"])
        tb = elem.findtext("thunderball") or elem.findtext("bonusBall")
        if len(mains) < 5 or not tb:
            return None
        return DrawResult(
            draw_date=date, draw_number=num,
            main_balls=tuple(sorted(mains[:5])),
            bonus_balls=(int(tb.strip()),),
            jackpot_value=jackpot,
        )
