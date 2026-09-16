"""Composition root for the recognition HTTP layer."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from src.context.recognition.application import RecognitionUnitOfWork
from src.context.recognition.domain import ImageStore, OcrEngine
from src.context.recognition.infrastructure.ocr.stub_engine import StubOcrEngine
from src.context.recognition.infrastructure.persistence.unit_of_work import (
    SqlAlchemyRecognitionUnitOfWork,
)
from src.context.recognition.infrastructure.storage.local_image_store import (
    LocalImageStore,
)
from src.platform.config import get_settings
from src.shared_kernel.application import EventDispatcher

logger = logging.getLogger(__name__)


def get_unit_of_work() -> RecognitionUnitOfWork:
    return SqlAlchemyRecognitionUnitOfWork()


@lru_cache
def get_image_store() -> ImageStore:
    return LocalImageStore(get_settings().image_store_path)


@lru_cache
def get_ocr_engine() -> OcrEngine:
    """Build the configured engine once and keep it.

    PaddleOCR loads its models on first use and they are expensive to build,
    so the instance is cached for the life of the process. The import happens
    inside this branch, which is what keeps PaddleOCR optional.
    """
    settings = get_settings()
    choice = (settings.ocr_engine or "stub").strip().lower()

    if choice in {"paddle", "paddleocr"}:
        from src.context.recognition.infrastructure.ocr.paddle_engine import (
            PaddleOcrEngine,
        )

        logger.info("OCR engine: PaddleOCR (lang=%s)", settings.ocr_language)
        return PaddleOcrEngine(
            language=settings.ocr_language,
            minimum_confidence=settings.ocr_minimum_confidence,
        )

    if choice != "stub":
        logger.warning("unknown OCR_ENGINE %r; falling back to the stub", choice)
    logger.info("OCR engine: stub (set OCR_ENGINE=paddleocr for real reading)")
    return StubOcrEngine()


@lru_cache
def get_event_dispatcher() -> EventDispatcher:
    return EventDispatcher()


UnitOfWorkDep = Annotated[RecognitionUnitOfWork, Depends(get_unit_of_work)]
ImageStoreDep = Annotated[ImageStore, Depends(get_image_store)]
OcrEngineDep = Annotated[OcrEngine, Depends(get_ocr_engine)]
EventsDep = Annotated[EventDispatcher, Depends(get_event_dispatcher)]
