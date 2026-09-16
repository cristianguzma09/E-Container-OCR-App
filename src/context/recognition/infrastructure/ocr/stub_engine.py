"""An OCR engine that reads nothing and returns whatever it was given.

The default engine, so the application starts and the whole suite runs without
PaddleOCR installed. It is also how every test above the adapter layer gets a
deterministic reading instead of depending on a model's mood.
"""

from __future__ import annotations

from collections.abc import Sequence

from src.context.recognition.domain import (
    Confidence,
    OcrEngine,
    OcrEngineFailure,
    TextFragment,
)


class StubOcrEngine(OcrEngine):
    """Returns canned fragments.

    Pass ``fragments`` for a fixed answer, or ``responses`` to hand back a
    different reading on each successive call - which is how a queue of
    captures is simulated.
    """

    def __init__(
        self,
        fragments: Sequence[TextFragment] | None = None,
        *,
        responses: Sequence[Sequence[TextFragment]] | None = None,
        fail_with: str | None = None,
    ) -> None:
        self._fragments = list(fragments or [])
        self._responses = [list(r) for r in responses] if responses else None
        self._fail_with = fail_with
        self.calls = 0

    @property
    def name(self) -> str:
        return "stub"

    @classmethod
    def reading(cls, *texts: str, confidence: float = 0.95) -> StubOcrEngine:
        """Build an engine that reads these lines, in this order."""
        return cls(
            [
                TextFragment(text=text, confidence=Confidence(confidence))
                for text in texts
            ]
        )

    def set_reading(self, *texts: str, confidence: float = 0.95) -> None:
        """Change what this engine reads, for a test that needs another photo."""
        self._fragments = [
            TextFragment(text=text, confidence=Confidence(confidence))
            for text in texts
        ]
        self._responses = None

    def read_text(self, image: bytes) -> list[TextFragment]:
        self.calls += 1

        if self._fail_with is not None:
            raise OcrEngineFailure(self.name, self._fail_with)

        if self._responses is not None:
            index = min(self.calls - 1, len(self._responses) - 1)
            return list(self._responses[index])

        return list(self._fragments)
