"""PaddleOCR adapter.

PaddleOCR is a heavy dependency - well over a gigabyte once PaddlePaddle and
its models are on disk - so it is imported *inside* the constructor rather
than at module level. That keeps ``pytest`` and ``uvicorn`` starting in a
second on a machine that has never installed it, and it means choosing a
different engine later costs nothing.

Install it with::

    pip install -r requirements-ocr.txt

then set ``OCR_ENGINE=paddleocr`` in ``.env``.
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Any

from src.context.recognition.domain import (
    BoundingBox,
    Confidence,
    OcrEngine,
    OcrEngineFailure,
    TextFragment,
)

logger = logging.getLogger(__name__)


class PaddleOcrEngine(OcrEngine):
    """Reads container markings with PaddleOCR's detect-then-recognise pipeline.

    Angle classification is on by default: container numbers are frequently
    photographed at a slant, and on many boxes the number is painted
    vertically down the door post.

    oneDNN is off by default. It normally speeds up CPU inference, but
    PaddlePaddle 3.3 raises ``ConvertPirAttribute2RuntimeAttribute not
    support`` from its oneDNN kernels on some Windows CPUs, which takes the
    whole pipeline down. A slower engine beats an engine that does not run, so
    it is opt-in via ``OCR_ENABLE_MKLDNN=true``.
    """

    def __init__(
        self,
        *,
        language: str = "en",
        use_angle_classification: bool = True,
        minimum_confidence: float = 0.3,
        enable_mkldnn: bool = False,
    ) -> None:
        self._language = language
        self._use_angle_classification = use_angle_classification
        self._minimum_confidence = minimum_confidence
        self._enable_mkldnn = enable_mkldnn
        self._engine: Any | None = None

    @property
    def name(self) -> str:
        return "paddleocr"

    # -- lazy construction --------------------------------------------------
    def _reader(self) -> Any:
        """Build the reader on first use; downloads models the first time."""
        if self._engine is not None:
            return self._engine

        try:
            from paddleocr import PaddleOCR
        except ImportError as error:
            raise OcrEngineFailure(
                self.name,
                "paddleocr is not installed - run "
                "'pip install -r requirements-ocr.txt', or set OCR_ENGINE=stub",
            ) from error

        # Constructor keywords moved between PaddleOCR 2.x and 3.x - angle
        # classification is `use_textline_orientation` in 3.x and
        # `use_angle_cls` in 2.x - so the 3.x form is tried first and the
        # options are progressively narrowed until one is accepted.
        base: dict[str, Any] = {
            "lang": self._language,
            "enable_mkldnn": self._enable_mkldnn,
        }
        attempts: list[dict[str, Any]] = [
            {**base, "use_textline_orientation": self._use_angle_classification},
            {**base, "use_angle_cls": self._use_angle_classification},
            base,
            {"lang": self._language, "use_angle_cls": self._use_angle_classification},
            {"lang": self._language},
            {},
        ]
        last_error: Exception | None = None
        for kwargs in attempts:
            try:
                self._engine = PaddleOCR(**kwargs)
                logger.info("PaddleOCR ready (options: %s)", sorted(kwargs))
                return self._engine
            except (TypeError, ValueError) as error:
                last_error = error

        raise OcrEngineFailure(
            self.name, f"could not construct PaddleOCR: {last_error}"
        )

    # -- reading ------------------------------------------------------------
    def read_text(self, image: bytes) -> list[TextFragment]:
        reader = self._reader()

        # Written to a file rather than decoded in-process: every PaddleOCR
        # version accepts a path, while the in-memory array route depends on
        # which of numpy/opencv/PIL that version happens to pull in.
        handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        try:
            handle.write(image)
            handle.close()
            raw = self._invoke(reader, handle.name)
        except OcrEngineFailure:
            raise
        except Exception as error:
            raise OcrEngineFailure(self.name, str(error)) from error
        finally:
            handle.close()
            try:
                os.unlink(handle.name)
            except OSError:
                logger.debug("could not remove temp file %s", handle.name)

        return self._to_fragments(raw)

    def _invoke(self, reader: Any, path: str) -> Any:
        """Call whichever entry point this PaddleOCR version exposes."""
        if hasattr(reader, "predict"):
            return reader.predict(path)
        try:
            return reader.ocr(path, cls=self._use_angle_classification)
        except TypeError:
            return reader.ocr(path)

    # -- translation --------------------------------------------------------
    def _to_fragments(self, raw: Any) -> list[TextFragment]:
        """Flatten PaddleOCR's result into the port's vocabulary.

        Two shapes are handled: the 3.x dictionary form with parallel
        ``rec_texts`` / ``rec_scores`` lists, and the classic 2.x nested form
        of ``[polygon, (text, score)]`` pairs.
        """
        if not raw:
            return []

        fragments: list[TextFragment] = []
        for page in raw:
            if page is None:
                continue
            if isinstance(page, dict) or hasattr(page, "get"):
                fragments.extend(self._from_mapping(page))
            else:
                fragments.extend(self._from_pairs(page))
        return fragments

    def _from_mapping(self, page: Any) -> list[TextFragment]:
        texts = page.get("rec_texts") or []
        scores = page.get("rec_scores") or []
        polygons = page.get("rec_polys") or page.get("dt_polys") or []

        fragments = []
        for index, text in enumerate(texts):
            score = float(scores[index]) if index < len(scores) else 0.0
            polygon = polygons[index] if index < len(polygons) else None
            fragment = self._build(text, score, polygon)
            if fragment is not None:
                fragments.append(fragment)
        return fragments

    def _from_pairs(self, page: Any) -> list[TextFragment]:
        fragments = []
        for entry in page or []:
            if not entry:
                continue
            try:
                polygon, recognition = entry[0], entry[1]
                text, score = recognition[0], float(recognition[1])
            except (IndexError, TypeError, ValueError):
                logger.debug("skipping unrecognised PaddleOCR entry: %r", entry)
                continue
            fragment = self._build(text, score, polygon)
            if fragment is not None:
                fragments.append(fragment)
        return fragments

    def _build(self, text: Any, score: float, polygon: Any) -> TextFragment | None:
        text = str(text).strip()
        if not text or score < self._minimum_confidence:
            return None

        box = None
        if polygon is not None:
            try:
                box = BoundingBox.around([(float(p[0]), float(p[1])) for p in polygon])
            except (TypeError, ValueError, IndexError):
                box = None

        return TextFragment(
            text=text,
            confidence=Confidence(max(0.0, min(1.0, score))),
            box=box,
        )
