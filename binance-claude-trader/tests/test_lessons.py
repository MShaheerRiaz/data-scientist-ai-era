"""Lesson book and volume-anomaly tests."""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from binance_client import Candle  # noqa: E402
from catalyst import anomalous_symbols, volume_profile  # noqa: E402
from lessons import LessonBook, build_review_payload  # noqa: E402


def book(**kwargs) -> tuple[LessonBook, tempfile.TemporaryDirectory]:
    tmp = tempfile.TemporaryDirectory()
    return LessonBook(os.path.join(tmp.name, "lessons.json"), **kwargs), tmp


# --- lesson book ----------------------------------------------------------


def test_records_a_new_lesson():
    b, tmp = book()
    with tmp:
        assert b.record("Avoid entering mid-range with mixed structure", ["mid-range"], "BTC")
        assert len(b.lessons) == 1
        assert b.lessons[0].occurrences == 1


def test_similar_lessons_merge_rather_than_duplicate():
    b, tmp = book()
    with tmp:
        b.record("Avoid entering mid-range when structure is mixed", ["mid-range"], "BTC")
        is_new = b.record("Avoid entering mid-range while structure is mixed", ["chop"], "ETH")
        assert not is_new, "near-identical lessons must merge"
        assert len(b.lessons) == 1
        assert b.lessons[0].occurrences == 2
        # Tags from both are kept.
        assert "mid-range" in b.lessons[0].tags and "chop" in b.lessons[0].tags


def test_distinct_lessons_stay_separate():
    b, tmp = book()
    with tmp:
        b.record("Avoid entering mid-range with mixed structure", [], "BTC")
        b.record("Stops inside one ATR get taken out by noise", [], "ETH")
        assert len(b.lessons) == 2


def test_repeated_lessons_outrank_recent_one_offs():
    """Prompt space is finite; a mistake made repeatedly matters more."""
    b, tmp = book(max_lessons=2)
    with tmp:
        b.record("Repeated error about chasing extended moves", [], "A")
        b.record("Repeated error about chasing extended moves", [], "B")
        b.record("Repeated error about chasing extended moves", [], "C")
        b.record("One off thing that happened once only", [], "D")
        b.record("Another different single occurrence entirely", [], "E")
        assert b.lessons[0].occurrences == 3
        assert len(b.lessons) == 2


def test_lesson_cap_is_enforced():
    b, tmp = book(max_lessons=3)
    with tmp:
        distinct = [
            "Chasing extended moves after five percent gives poor entries",
            "Stops inside one ATR are removed by ordinary noise",
            "Mid range entries with mixed swing structure rarely resolve",
            "Thin liquidity pairs slip badly against the quoted price",
            "Weekend sessions produce unreliable breakout signals",
        ]
        for text in distinct:
            b.record(text, [], "X")
        assert len(b.lessons) == 3


def test_opposite_lessons_are_not_merged():
    """The failure the similarity metric was retuned to prevent.

    These share three of four content words but say contradictory things.
    Merging them would silently discard one and leave the book asserting
    whichever happened to be recorded first.
    """
    b, tmp = book()
    with tmp:
        b.record("Volume spike means enter immediately", [], "A")
        b.record("Volume spike means wait patiently", [], "B")
        assert len(b.lessons) == 2, "opposite lessons must stay distinct"


def test_short_lesson_does_not_swallow_more_specific_ones():
    """Overlap-over-min() would merge these, since the first is a subset."""
    b, tmp = book()
    with tmp:
        b.record("Stop too tight", [], "A")
        b.record("Stop too tight relative to ATR on low liquidity altcoin pairs", [], "B")
        assert len(b.lessons) == 2


def test_empty_lessons_render_as_empty_string():
    """So the caller can omit the section instead of showing an empty heading."""
    b, tmp = book()
    with tmp:
        assert b.as_prompt_block() == ""


def test_prompt_block_marks_repeat_offences():
    b, tmp = book()
    with tmp:
        b.record("Do not chase extended moves on high volume", [], "A")
        b.record("Do not chase extended moves on high volume", [], "B")
        block = b.as_prompt_block()
        assert "seen 2x" in block


def test_blank_lessons_are_ignored():
    b, tmp = book()
    with tmp:
        assert not b.record("   ", [], "X")
        assert len(b.lessons) == 0


def test_lessons_persist_across_instances():
    tmp = tempfile.TemporaryDirectory()
    with tmp:
        path = os.path.join(tmp.name, "lessons.json")
        first = LessonBook(path)
        first.record("Persisted lesson about stop placement discipline", ["stops"], "BTC")

        second = LessonBook(path)
        assert len(second.lessons) == 1
        assert "stop placement" in second.lessons[0].text


def test_corrupt_lessons_file_does_not_crash():
    tmp = tempfile.TemporaryDirectory()
    with tmp:
        path = os.path.join(tmp.name, "lessons.json")
        with open(path, "w") as fh:
            fh.write("{ not valid json")
        assert LessonBook(path).lessons == []


def test_review_payload_carries_entry_state_not_exit_state():
    """Reviews must judge on what was knowable at entry, or they are hindsight."""
    payload = build_review_payload(
        position_symbol="BTCUSDT", entry=100.0, stop=96.0, target=110.0,
        exit_price=96.0, exit_reason="stop", pnl=-40.0, opened_at="t0",
        original_reasoning="range low bounce",
        entry_snapshot={"rsi_14": 31.0, "position_in_range": 0.05},
    )
    assert payload["market_state_at_entry"]["rsi_14"] == 31.0
    assert payload["original_reasoning"] == "range low bounce"
    assert payload["planned_reward_risk"] == 2.5
    assert payload["outcome"] == "loss"


# --- volume anomalies -----------------------------------------------------


def candles(volumes: list[float], ranges: list[float] | None = None) -> list[Candle]:
    ranges = ranges or [1.0] * len(volumes)
    return [
        Candle(i, 100.0, 100.0 + r / 2, 100.0 - r / 2, 100.0, v, i)
        for i, (v, r) in enumerate(zip(volumes, ranges))
    ]


def test_flat_volume_is_not_anomalous():
    profile = volume_profile(candles([100.0] * 80))
    assert profile["volume_ratio"] == 1.0
    assert not profile["is_anomalous"]


def test_volume_spike_with_range_expansion_is_anomalous():
    vols = [100.0] * 60 + [400.0] * 8
    rngs = [1.0] * 60 + [3.0] * 8
    profile = volume_profile(candles(vols, rngs))
    assert profile["volume_ratio"] == 4.0
    assert profile["range_expansion"] == 3.0
    assert profile["is_anomalous"]


def test_volume_spike_without_range_expansion_is_not_anomalous():
    """A big print that moves no price is churn, not a catalyst."""
    vols = [100.0] * 60 + [400.0] * 8
    rngs = [1.0] * 68
    profile = volume_profile(candles(vols, rngs))
    assert profile["volume_ratio"] == 4.0
    assert not profile["is_anomalous"], "volume without range expansion is not a move"


def test_short_history_is_never_anomalous():
    assert not volume_profile(candles([100.0] * 10))["is_anomalous"]


def test_zero_baseline_volume_does_not_divide_by_zero():
    profile = volume_profile(candles([0.0] * 60 + [500.0] * 8))
    assert profile["volume_ratio"] == 1.0


def test_anomalous_symbols_ranked_by_volume_ratio():
    snapshots = [
        {"symbol": "AAA", "is_anomalous": True, "volume_ratio": 3.0},
        {"symbol": "BBB", "is_anomalous": False, "volume_ratio": 9.0},
        {"symbol": "CCC", "is_anomalous": True, "volume_ratio": 7.0},
    ]
    assert anomalous_symbols(snapshots) == ["CCC", "AAA"]


def test_anomalous_symbols_respects_limit():
    snapshots = [
        {"symbol": f"S{i}", "is_anomalous": True, "volume_ratio": float(i)}
        for i in range(10)
    ]
    assert len(anomalous_symbols(snapshots, limit=3)) == 3


if __name__ == "__main__":
    import traceback

    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception:  # noqa: BLE001 - test harness
            failed += 1
            print(f"  FAIL  {name}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
