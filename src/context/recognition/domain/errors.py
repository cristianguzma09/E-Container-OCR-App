"""Domain errors specific to recognition."""

from __future__ import annotations

from src.shared_kernel.domain import DomainError


class RecognitionError(DomainError):
    """Base for anything the recognition domain refuses."""


class InvalidImage(RecognitionError):
    """The upload is not usable as a container photograph."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"the image cannot be processed: {reason}")


class OcrEngineFailure(RecognitionError):
    """The engine itself broke, as opposed to reading nothing useful.

    Worth distinguishing: an unreadable photo is an ordinary outcome that ends
    in NEEDS_REVIEW, while an engine that crashes is an operational fault.
    """

    def __init__(self, engine: str, reason: str) -> None:
        self.engine = engine
        self.reason = reason
        super().__init__(f"{engine} failed: {reason}")
