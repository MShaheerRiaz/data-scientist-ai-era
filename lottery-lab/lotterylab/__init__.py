"""lotterylab - probability, game theory and fairness auditing for lotteries.

A dependency-free toolkit for analysing draw games honestly.

The library is built around one uncomfortable fact: **for a fair lottery,
past draws contain no information about future draws.**  Nothing here will
tell you which numbers are "due".  What it will do is:

* audit a draw history for genuine, measurable unfairness
  (:mod:`lotterylab.fairness`), and tell you how small a bias your data
  could even detect;
* compute exact odds and expected values, including the jackpot-sharing
  effect that most published EV figures ignore (:mod:`lotterylab.ev`);
* model which combinations *other players* favour, so you can pick
  combinations that pay more when they do win
  (:mod:`lotterylab.popularity`, :mod:`lotterylab.generate`);
* build covering designs with provable prize guarantees
  (:mod:`lotterylab.wheels`);
* analyse digit games such as 2D/3D (:mod:`lotterylab.digits`);
* backtest any number-picking strategy against a properly calibrated null
  (:mod:`lotterylab.backtest`).

Only the third and fourth of those change your expected outcome, and
neither makes a negative-EV game positive.
"""

from __future__ import annotations

__version__ = "1.0.0"

from .config import (
    UK_GAMES,
    BonusMode,
    DigitGameConfig,
    LotteryConfig,
    PrizeTier,
    DIGIT_PRESETS,
    PRESETS,
    get_preset,
    list_presets,
)
from .data import Draw, DrawHistory, SynthBias, load_csv, save_csv, synthesize
from .luckydip import Line, Slip, lucky_dip

__all__ = [
    "__version__",
    "BonusMode",
    "DigitGameConfig",
    "LotteryConfig",
    "PrizeTier",
    "PRESETS",
    "DIGIT_PRESETS",
    "UK_GAMES",
    "lucky_dip",
    "Line",
    "Slip",
    "get_preset",
    "list_presets",
    "Draw",
    "DrawHistory",
    "SynthBias",
    "load_csv",
    "save_csv",
    "synthesize",
]
