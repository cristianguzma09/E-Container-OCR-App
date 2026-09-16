"""Live PaddleOCR test - runs the real engine against a real image.

Skipped unless ``RUN_PADDLE_TESTS=1``. It is kept out of the default run for
two reasons: it needs ``requirements-ocr.txt`` installed, and loading the
detection and recognition models costs tens of seconds on the first call,
which would wreck a suite that otherwise finishes in five.

Run it after touching the adapter or upgrading PaddleOCR::

    RUN_PADDLE_TESTS=1 venv/Scripts/python -m pytest tests/integration/test_paddle_engine_live.py -v
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import pytest

from src.context.recognition.domain import ContainerCodeExtractor
from src.context.recognition.infrastructure.ocr.paddle_engine import PaddleOcrEngine

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("RUN_PADDLE_TESTS") != "1",
        reason="set RUN_PADDLE_TESTS=1 to exercise the real engine",
    ),
]

VALID = "CSQU3054383"


def _painted_container(tmp_path: Path) -> bytes:
    """A crude stand-in for a container photo: light text on rust-orange."""
    PIL = pytest.importorskip("PIL")
    from PIL import Image, ImageDraw, ImageFont

    def font(size: int):
        for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        return ImageFont.load_default()

    image = Image.new("RGB", (900, 320), (196, 122, 60))
    draw = ImageDraw.Draw(image)
    draw.text((60, 40), "CSQU 305438 3", fill=(245, 245, 245), font=font(96))
    draw.text((60, 180), "22G1", fill=(245, 245, 245), font=font(72))
    draw.text((420, 200), "MAX GROSS 30480 KG", fill=(235, 235, 235), font=font(36))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture(scope="module")
def engine() -> PaddleOcrEngine:
    """One engine for the module - building it downloads and loads models."""
    return PaddleOcrEngine(minimum_confidence=0.3)


def test_the_real_engine_reads_a_painted_container_number(
    engine: PaddleOcrEngine, tmp_path: Path
) -> None:
    fragments = engine.read_text(_painted_container(tmp_path))

    assert fragments, "PaddleOCR returned nothing at all"
    texts = [f.text for f in fragments]
    assert any("305438" in text for text in texts), texts

    candidates = ContainerCodeExtractor().extract(fragments)

    assert candidates, f"nothing looked like a container number in {texts}"
    best = candidates[0]
    assert best.value == VALID
    assert best.check_digit_valid is True
    assert best.repaired is False


def test_the_real_engine_populates_confidence_and_boxes(
    engine: PaddleOcrEngine, tmp_path: Path
) -> None:
    fragments = engine.read_text(_painted_container(tmp_path))

    for fragment in fragments:
        assert 0.0 <= fragment.confidence.value <= 1.0
        if fragment.box is not None:
            assert fragment.box.width > 0
            assert fragment.box.height > 0


def test_the_real_engine_returns_nothing_for_a_blank_image(
    engine: PaddleOcrEngine,
) -> None:
    """An empty result is a normal answer, not a failure."""
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (400, 200), (128, 128, 128)).save(buffer, format="PNG")

    assert engine.read_text(buffer.getvalue()) == []
