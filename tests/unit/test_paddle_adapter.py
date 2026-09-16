"""Unit tests for the PaddleOCR adapter's translation layer.

The engine itself is not exercised here - these tests feed the adapter the
result shapes PaddleOCR produces and check it reduces them to the port's
vocabulary. That is the part most likely to break when PaddleOCR changes its
output format between versions, and it needs no model download to verify.
"""

from __future__ import annotations

import pytest

from src.context.recognition.domain import OcrEngineFailure
from src.context.recognition.infrastructure.ocr.paddle_engine import PaddleOcrEngine

SQUARE = [[10, 20], [110, 20], [110, 60], [10, 60]]


@pytest.fixture
def engine() -> PaddleOcrEngine:
    return PaddleOcrEngine(minimum_confidence=0.3)


# --------------------------------------------------------------------------- #
# The classic 2.x nested-list format                                           #
# --------------------------------------------------------------------------- #
def test_classic_format_is_translated(engine: PaddleOcrEngine) -> None:
    raw = [
        [
            [SQUARE, ("CSQU3054383", 0.97)],
            [SQUARE, ("22G1", 0.88)],
        ]
    ]

    fragments = engine._to_fragments(raw)

    assert [f.text for f in fragments] == ["CSQU3054383", "22G1"]
    assert fragments[0].confidence.value == pytest.approx(0.97)
    assert fragments[0].box is not None
    assert (fragments[0].box.left, fragments[0].box.top) == (10, 20)
    assert (fragments[0].box.width, fragments[0].box.height) == (100, 40)


def test_classic_format_with_nothing_found(engine: PaddleOcrEngine) -> None:
    """PaddleOCR 2.7 returns ``[None]`` when the image has no text."""
    assert engine._to_fragments([None]) == []
    assert engine._to_fragments([[]]) == []
    assert engine._to_fragments([]) == []
    assert engine._to_fragments(None) == []


def test_malformed_entries_are_skipped_not_fatal(engine: PaddleOcrEngine) -> None:
    raw = [
        [
            [SQUARE, ("CSQU3054383", 0.97)],
            None,
            ["nonsense"],
            [SQUARE],
        ]
    ]

    fragments = engine._to_fragments(raw)

    assert [f.text for f in fragments] == ["CSQU3054383"]


# --------------------------------------------------------------------------- #
# The 3.x dictionary format                                                    #
# --------------------------------------------------------------------------- #
def test_dictionary_format_is_translated(engine: PaddleOcrEngine) -> None:
    raw = [
        {
            "rec_texts": ["CSQU3054383", "MAERSK"],
            "rec_scores": [0.96, 0.77],
            "rec_polys": [SQUARE, SQUARE],
        }
    ]

    fragments = engine._to_fragments(raw)

    assert [f.text for f in fragments] == ["CSQU3054383", "MAERSK"]
    assert fragments[1].confidence.value == pytest.approx(0.77)


def test_dictionary_format_falls_back_to_detection_polygons(
    engine: PaddleOcrEngine,
) -> None:
    raw = [{"rec_texts": ["CSQU3054383"], "rec_scores": [0.9], "dt_polys": [SQUARE]}]
    assert engine._to_fragments(raw)[0].box is not None


def test_dictionary_format_without_polygons(engine: PaddleOcrEngine) -> None:
    raw = [{"rec_texts": ["CSQU3054383"], "rec_scores": [0.9]}]

    fragments = engine._to_fragments(raw)

    assert fragments[0].text == "CSQU3054383"
    assert fragments[0].box is None


def test_dictionary_format_with_missing_scores(engine: PaddleOcrEngine) -> None:
    """A text with no matching score scores zero and is filtered out."""
    raw = [{"rec_texts": ["CSQU3054383", "EXTRA"], "rec_scores": [0.9]}]
    assert [f.text for f in engine._to_fragments(raw)] == ["CSQU3054383"]


# --------------------------------------------------------------------------- #
# Filtering and robustness                                                     #
# --------------------------------------------------------------------------- #
def test_low_confidence_text_is_dropped(engine: PaddleOcrEngine) -> None:
    raw = [[[SQUARE, ("CSQU3054383", 0.95)], [SQUARE, ("smudge", 0.05)]]]
    assert [f.text for f in engine._to_fragments(raw)] == ["CSQU3054383"]


def test_the_threshold_is_configurable() -> None:
    lenient = PaddleOcrEngine(minimum_confidence=0.0)
    raw = [[[SQUARE, ("smudge", 0.05)]]]
    assert [f.text for f in lenient._to_fragments(raw)] == ["smudge"]


def test_blank_text_is_dropped(engine: PaddleOcrEngine) -> None:
    raw = [[[SQUARE, ("   ", 0.99)], [SQUARE, ("", 0.99)]]]
    assert engine._to_fragments(raw) == []


def test_a_broken_polygon_keeps_the_text_and_drops_the_box(
    engine: PaddleOcrEngine,
) -> None:
    raw = [[[[["x", "y"]], ("CSQU3054383", 0.9)]]]

    fragments = engine._to_fragments(raw)

    assert fragments[0].text == "CSQU3054383"
    assert fragments[0].box is None


def test_a_score_above_one_is_clamped(engine: PaddleOcrEngine) -> None:
    raw = [[[SQUARE, ("CSQU3054383", 1.4)]]]
    assert engine._to_fragments(raw)[0].confidence.value == 1.0


# --------------------------------------------------------------------------- #
# Optional dependency                                                          #
# --------------------------------------------------------------------------- #
def test_the_engine_reports_its_name(engine: PaddleOcrEngine) -> None:
    assert engine.name == "paddleocr"


def test_constructing_the_adapter_does_not_import_paddleocr() -> None:
    """The whole point of the lazy import - this must not be slow or fail."""
    PaddleOcrEngine()


def test_a_missing_library_gives_an_actionable_message(
    engine: PaddleOcrEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    import builtins

    real_import = builtins.__import__

    def fail_paddle(name, *args, **kwargs):
        if name.startswith("paddleocr"):
            raise ImportError("No module named 'paddleocr'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_paddle)

    with pytest.raises(OcrEngineFailure) as excinfo:
        engine._reader()

    message = str(excinfo.value)
    assert "requirements-ocr.txt" in message
    assert "OCR_ENGINE=stub" in message
