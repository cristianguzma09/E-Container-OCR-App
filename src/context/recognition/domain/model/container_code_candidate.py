"""A container number the extractor believes it found."""

from __future__ import annotations

from dataclasses import dataclass

from src.context.recognition.domain.model.bounding_box import BoundingBox
from src.context.recognition.domain.model.confidence import Confidence
from src.shared_kernel.domain import ValueObject


@dataclass(frozen=True)
class ContainerCodeCandidate(ValueObject):
    """One reading of a container number, with everything known about it.

    The candidate keeps the raw text next to the cleaned-up value on purpose.
    When a read is sent for review, an operator needs to see what the camera
    actually produced, not only what the software decided it meant.
    """

    raw_text: str
    value: str
    confidence: Confidence
    check_digit_valid: bool
    expected_check_digit: int | None = None
    repaired: bool = False
    box: BoundingBox | None = None

    @property
    def score(self) -> float:
        """Ranking score. A valid check digit always beats an invalid one.

        The check digit is arithmetic, not a guess: a read that satisfies it
        is almost certainly right, and one that does not is almost certainly
        wrong no matter how confident the engine sounded. So it dominates the
        ranking, and the engine's own confidence only orders reads within each
        of those two groups.
        """
        if self.check_digit_valid:
            score = 0.5 + self.confidence.value * 0.5
        else:
            score = self.confidence.value * 0.4
        if self.repaired:
            score -= 0.05
        return max(0.0, min(1.0, round(score, 4)))

    @property
    def needs_human_confirmation(self) -> bool:
        """A repaired or check-digit-failing read is never accepted silently."""
        return self.repaired or not self.check_digit_valid

    def __str__(self) -> str:
        return self.value
