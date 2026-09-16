"""One piece of text an OCR engine returned."""

from __future__ import annotations

from dataclasses import dataclass

from src.context.recognition.domain.model.bounding_box import BoundingBox
from src.context.recognition.domain.model.confidence import Confidence
from src.shared_kernel.domain import ValueObject


@dataclass(frozen=True)
class TextFragment(ValueObject):
    """Raw engine output: some text, how sure it is, and where it was.

    This is the whole vocabulary of the :class:`OcrEngine` port. Every adapter
    - PaddleOCR, a cloud API, a stub - reduces its own result shape to a list
    of these, so nothing downstream can tell which engine produced them.
    """

    text: str
    confidence: Confidence
    box: BoundingBox | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", str(self.text).strip())

    @property
    def is_empty(self) -> bool:
        return not self.text

    def __str__(self) -> str:
        return self.text
