"""Port: reading text out of an image."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.context.recognition.domain.model.text_fragment import TextFragment


class OcrEngine(ABC):
    """Whatever actually reads the pixels.

    The entire contract is bytes in, fragments out. PaddleOCR, a cloud vision
    API and a canned stub all reduce to the same shape, so nothing downstream
    can tell which one ran - and swapping engines never reaches the domain.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Identifies the engine in logs and failure messages."""

    @abstractmethod
    def read_text(self, image: bytes) -> list[TextFragment]:
        """Return everything legible in the image.

        Returning an empty list is a normal answer - a blurred or badly framed
        photo. Raise :class:`OcrEngineFailure` only when the engine itself
        broke.
        """
