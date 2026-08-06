"""Fetching and parsing UK National Lottery draw history.

The National Lottery publishes complete draw history for every game as a
free CSV download. No key, no scraping, no terms-of-service problem — it
is a public download link intended for exactly this.

    https://www.national-lottery.co.uk/results/<game>/draw-history/csv

:func:`download` fetches it with the standard library only. If your
network blocks the site (some sandboxes and corporate networks do), save
the CSV by hand from the browser and pass the file to :func:`load` — the
parser is the useful half anyway.

The CSV column layouts differ per game and have changed over the years, so
:func:`load` identifies columns by *name* rather than position, which
survives the operator reordering or adding columns.
"""

from __future__ import annotations

import csv
import io
import re
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import PRESETS, LotteryConfig
from .data import Draw, DrawHistory

__all__ = ["UK_SOURCES", "download", "load", "parse", "DownloadResult"]


#: Operator slug and the column names each game uses for its balls.
UK_SOURCES: dict[str, dict[str, object]] = {
    "uk_lotto": {
        "slug": "lotto",
        "main": ("ball 1", "ball 2", "ball 3", "ball 4", "ball 5", "ball 6"),
        "bonus": ("bonus ball",),
    },
    "euromillions": {
        "slug": "euromillions",
        "main": ("ball 1", "ball 2", "ball 3", "ball 4", "ball 5"),
        "bonus": ("lucky star 1", "lucky star 2"),
    },
    "thunderball": {
        "slug": "thunderball",
        "main": ("ball 1", "ball 2", "ball 3", "ball 4", "ball 5"),
        "bonus": ("thunderball",),
    },
    "set_for_life": {
        "slug": "set-for-life",
        "main": ("ball 1", "ball 2", "ball 3", "ball 4", "ball 5"),
        "bonus": ("life ball",),
    },
}

_BASE = "https://www.national-lottery.co.uk/results/{slug}/draw-history/csv"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class DownloadResult:
    """Outcome of a download attempt."""

    game: str
    url: str
    ok: bool
    path: Optional[Path] = None
    bytes_received: int = 0
    error: str = ""

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        if self.ok:
            return f"  {self.game:<14} OK   {self.bytes_received:>9,} bytes -> {self.path}"
        return f"  {self.game:<14} FAIL  {self.error}"


def source_url(game: str) -> str:
    """The official download URL for a game."""
    if game not in UK_SOURCES:
        raise KeyError(f"unknown UK game {game!r}; "
                       f"available: {', '.join(sorted(UK_SOURCES))}")
    return _BASE.format(slug=UK_SOURCES[game]["slug"])


def download(
    game: str,
    destination: str | Path,
    *,
    timeout: int = 60,
    insecure: bool = False,
) -> DownloadResult:
    """Download one game's full draw history to ``destination``.

    Standard library only, so there is nothing to install. Returns a
    :class:`DownloadResult` rather than raising, because the usual failure
    is a blocked network and that deserves a clear message rather than a
    traceback.
    """
    url = source_url(game)
    destination = Path(destination)

    request = urllib.request.Request(url, headers={
        "User-Agent": _USER_AGENT,
        "Accept": "text/csv,application/csv,text/plain,*/*",
        "Accept-Language": "en-GB,en;q=0.9",
    })

    context = ssl._create_unverified_context() if insecure else None
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        return DownloadResult(game, url, False, error=f"HTTP {exc.code} {exc.reason}")
    except urllib.error.URLError as exc:
        return DownloadResult(game, url, False,
                              error=f"network error: {exc.reason} "
                                    f"(if you are behind a proxy or firewall, download "
                                    f"the file in a browser and use `load` instead)")
    except Exception as exc:  # pragma: no cover - defensive
        return DownloadResult(game, url, False, error=f"{type(exc).__name__}: {exc}")

    text = payload.decode("utf-8-sig", errors="replace")
    if "<html" in text[:400].lower():
        return DownloadResult(
            game, url, False,
            error="server returned an HTML page rather than CSV - the download URL "
                  "may have changed, or a captcha/consent page intercepted it",
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    return DownloadResult(game, url, True, path=destination, bytes_received=len(payload))


def download_all(
    directory: str | Path,
    *,
    games: Optional[tuple[str, ...]] = None,
    timeout: int = 60,
) -> list[DownloadResult]:
    """Download every UK game's history into ``directory``."""
    directory = Path(directory)
    targets = games or tuple(UK_SOURCES)
    return [
        download(game, directory / f"{game}.csv", timeout=timeout)
        for game in targets
    ]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_DATE_FORMATS = ("%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d %b %Y", "%d-%m-%Y")


def _parse_uk_date(raw: str) -> Optional[datetime]:
    text = (raw or "").strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def parse(text: str, game: str, config: Optional[LotteryConfig] = None) -> DrawHistory:
    """Parse National Lottery CSV text into a :class:`DrawHistory`.

    Columns are matched by name, case-insensitively and ignoring spaces and
    underscores, so the operator can reorder or rename around the edges
    without breaking this.
    """
    if game not in UK_SOURCES:
        raise KeyError(f"unknown UK game {game!r}")
    cfg = config or PRESETS[game]
    spec = UK_SOURCES[game]

    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return DrawHistory(config=cfg, draws=[], source=f"{game} csv",
                           warnings=["file contained no data rows"])

    def normalise(name: str) -> str:
        return re.sub(r"[\s_]+", " ", (name or "").strip().lower())

    header_map = {normalise(h): h for h in rows[0].keys() if h}

    def resolve(names: tuple[str, ...]) -> list[str]:
        found = []
        for wanted in names:
            key = normalise(wanted)
            if key in header_map:
                found.append(header_map[key])
        return found

    main_cols = resolve(tuple(spec["main"]))          # type: ignore[arg-type]
    bonus_cols = resolve(tuple(spec["bonus"]))        # type: ignore[arg-type]
    date_col = header_map.get("drawdate") or header_map.get("draw date") or header_map.get("date")

    warnings: list[str] = []
    if len(main_cols) != cfg.main_pick:
        warnings.append(
            f"expected {cfg.main_pick} main-ball columns {spec['main']}, "
            f"found {len(main_cols)}: {main_cols or 'none'}. "
            f"Header was: {list(rows[0].keys())}"
        )
        return DrawHistory(config=cfg, draws=[], source=f"{game} csv", warnings=warnings)

    draws: list[Draw] = []
    for line_no, row in enumerate(rows, start=2):
        try:
            main = tuple(int(str(row[c]).strip()) for c in main_cols)
            bonus = tuple(
                int(str(row[c]).strip())
                for c in bonus_cols
                if str(row.get(c, "")).strip().isdigit()
            )
            when = _parse_uk_date(row.get(date_col, "")) if date_col else None
            draws.append(Draw(
                main=tuple(sorted(main)),
                bonus=tuple(sorted(bonus)),
                draw_date=when.date() if when else None,
                index=len(draws),
            ))
        except (ValueError, TypeError, KeyError) as exc:
            warnings.append(f"line {line_no}: {exc}")

    # The operator publishes newest-first; the library wants oldest-first so
    # gap and serial tests read chronologically.
    if all(d.draw_date for d in draws) and len(draws) > 1:
        draws.sort(key=lambda d: d.draw_date)  # type: ignore[arg-type,return-value]
    draws = [Draw(d.main, d.bonus, d.draw_date, i) for i, d in enumerate(draws)]

    history = DrawHistory(config=cfg, draws=draws, source=f"{game} csv", warnings=warnings)
    problems = history.validate()
    if problems:
        history.warnings.extend(problems[:20])
    return history


def load(path: str | Path, game: str, config: Optional[LotteryConfig] = None) -> DrawHistory:
    """Load a National Lottery CSV file from disk."""
    return parse(Path(path).read_text(encoding="utf-8-sig"), game, config)
