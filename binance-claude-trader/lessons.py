"""Trade review and accumulated lessons.

After every closed trade the bot reviews what happened and, when there is
something worth keeping, writes a lesson. Lessons are fed back into the
decision prompt so the same mistake is less likely twice.

The central idea, and the thing most trade journals get wrong:

    A losing trade is not automatically a mistake.
    A winning trade is not automatically correct.

Markets are noisy enough that a well-reasoned setup loses often, and a reckless
one wins often. If you only journal losses you will learn superstitions — you
will "fix" good decisions that happened to lose and keep bad decisions that
happened to win. So the review scores *process* and *outcome* separately, and
only sound-process losses are exempt from producing a lesson.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

REVIEW_SYSTEM_PROMPT = """\
You are reviewing a single closed trade to decide whether it contains a lesson \
worth carrying forward.

Judge process and outcome as separate axes. They are not the same thing:

- Sound process, profit      -> repeat it. Usually no lesson needed.
- Sound process, loss        -> normal variance. Usually NO LESSON. Do not \
invent a fault. Changing a good process because it lost once is how a strategy \
gets destroyed.
- Poor process, loss         -> the real teaching case. Name the specific error.
- Poor process, profit       -> the most dangerous case. The result rewarded a \
bad decision. Say so plainly, because this is what quietly builds bad habits.

A lesson is worth recording only if it would change a future decision. \
"Should have used a wider stop" is not a lesson unless you can say what in the \
data indicated a wider stop was needed at entry time.

Judge only on information available when the trade was opened. Anything \
knowable only afterwards is hindsight, not a lesson.

Most reviews should return should_record = false. A lessons file that grows on \
every trade is noise, and noise crowds out the few entries that matter.\
"""

REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "process_quality": {
            "type": "string",
            "enum": ["sound", "questionable", "poor"],
            "description": "quality of the decision judged on entry-time information only",
        },
        "outcome": {"type": "string", "enum": ["win", "loss"]},
        "should_record": {
            "type": "boolean",
            "description": "true only if this would change a future decision",
        },
        "lesson": {
            "type": "string",
            "description": "one specific, actionable sentence; empty when should_record is false",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "short kebab-case tags, e.g. mid-range-entry, stop-too-tight",
        },
        "analysis": {"type": "string", "description": "two sentences on what happened and why"},
    },
    "required": ["process_quality", "outcome", "should_record", "lesson", "tags", "analysis"],
    "additionalProperties": False,
}


@dataclass
class Lesson:
    text: str
    tags: list[str]
    recorded_at: str
    # How many separate trades produced this same lesson. A repeated mistake
    # matters more than a one-off, and this is what surfaces it.
    occurrences: int = 1
    last_seen: str = ""
    examples: list[str] = field(default_factory=list)


class LessonBook:
    """Persistent, deduplicated store of what the bot has learned.

    Capped in size on purpose: an unbounded list would grow past the point of
    being read carefully and would inflate every prompt.
    """

    def __init__(self, path: str, max_lessons: int = 25):
        self.path = path
        self.max_lessons = max_lessons
        self.lessons: list[Lesson] = []
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as fh:
                raw = json.load(fh)
            self.lessons = [Lesson(**item) for item in raw.get("lessons", [])]
        except (json.JSONDecodeError, OSError, TypeError) as exc:
            print(f"[lessons] could not read {self.path} ({exc}); starting empty")
            self.lessons = []

    def save(self) -> None:
        payload = {
            "lessons": [asdict(item) for item in self.lessons],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        os.replace(tmp, self.path)

    # Jaccard similarity above this counts as the same lesson.
    #
    # Tuned deliberately high. Trading lessons share a lot of vocabulary
    # (volume, stop, range, entry), so a loose threshold merges lessons that
    # are actually opposites: "volume spike means enter" and "volume spike
    # means wait" overlap on three of four content words. Merging those would
    # silently destroy one of them and leave the book asserting whichever
    # arrived first.
    SIMILARITY_THRESHOLD = 0.75

    _STOPWORDS = frozenset(
        """the a an and or but in on at to for of with is was were be been when
        while that this it as by from not do did does you your if then than so
        into over under after before during""".split()
    )

    @classmethod
    def _similar(cls, a: str, b: str) -> bool:
        """Cheap Jaccard token similarity, to avoid restating the same lesson.

        Deliberately not embeddings — this runs a handful of times a day over a
        list of at most 25 short strings, so a dependency-free heuristic beats
        a model call on every closed trade.

        Jaccard (intersection over *union*) rather than overlap over min():
        with min() a short lesson that is a token-subset of a longer one scores
        1.0 and always merges, so "stop too tight" would swallow every more
        specific stop-related lesson that followed it.
        """
        ta = {w for w in a.lower().split() if w not in cls._STOPWORDS and len(w) > 2}
        tb = {w for w in b.lower().split() if w not in cls._STOPWORDS and len(w) > 2}
        if not ta or not tb:
            return False
        union = len(ta | tb)
        return (len(ta & tb) / union) >= cls.SIMILARITY_THRESHOLD if union else False

    def record(self, text: str, tags: list[str], example: str) -> bool:
        """Add a lesson, merging into an existing one when it repeats.

        Returns True if a new lesson was created, False if an existing one was
        reinforced.
        """
        text = text.strip()
        if not text:
            return False

        now = datetime.now(timezone.utc).isoformat()

        for existing in self.lessons:
            if self._similar(existing.text, text):
                existing.occurrences += 1
                existing.last_seen = now
                existing.tags = sorted(set(existing.tags) | set(tags))
                existing.examples = (existing.examples + [example])[-5:]
                self._prune()
                self.save()
                return False

        self.lessons.append(
            Lesson(
                text=text,
                tags=sorted(set(tags)),
                recorded_at=now,
                last_seen=now,
                examples=[example],
            )
        )
        self._prune()
        self.save()
        return True

    def _prune(self) -> None:
        """Keep the most-repeated lessons, breaking ties by recency.

        Occurrences before recency: a mistake made five times is worth more
        prompt space than a fresher one-off.
        """
        self.lessons.sort(key=lambda l: (l.occurrences, l.last_seen), reverse=True)
        self.lessons = self.lessons[: self.max_lessons]

    def as_prompt_block(self) -> str:
        """Render lessons for injection into the decision prompt.

        Returns "" when empty so the caller can omit the section entirely
        rather than showing the model an empty heading.
        """
        if not self.lessons:
            return ""

        lines = []
        for item in self.lessons:
            marker = f" (seen {item.occurrences}x)" if item.occurrences > 1 else ""
            lines.append(f"- {item.text}{marker}")
        return "\n".join(lines)


def build_review_payload(
    position_symbol: str,
    entry: float,
    stop: float,
    target: float,
    exit_price: float,
    exit_reason: str,
    pnl: float,
    opened_at: str,
    original_reasoning: str,
    entry_snapshot: dict | None,
) -> dict[str, Any]:
    """Assemble the evidence for a trade review.

    `entry_snapshot` is the market state as it was when the trade was opened —
    without it the reviewer would be judging on data that did not exist at
    decision time, which produces hindsight rather than lessons.
    """
    return {
        "symbol": position_symbol,
        "entry": entry,
        "stop": stop,
        "target": target,
        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "pnl_quote": round(pnl, 4),
        "outcome": "win" if pnl > 0 else "loss",
        "planned_reward_risk": round((target - entry) / (entry - stop), 2)
        if entry > stop
        else None,
        "opened_at": opened_at,
        "original_reasoning": original_reasoning,
        "market_state_at_entry": entry_snapshot or {},
    }
