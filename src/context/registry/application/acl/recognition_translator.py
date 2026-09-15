"""Anti-corruption layer between the Recognition context and the Registry.

The OCR side speaks of candidates, bounding boxes and confidence scores. The
registry speaks of containers, size types and grades. This module is the only
place the two vocabularies meet, so a change to how recognition reports its
results never reaches the domain model.

:class:`RecognitionOutcome` is deliberately a *local copy* of the shape the
other context hands over, not an import from it. That is the whole point of an
ACL: if Recognition renames a field tomorrow, exactly one file here breaks.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.context.registry.application.dto import (
    ConditionObservation,
    RegisterContainerCommand,
)
from src.context.registry.domain import (
    ContainerNumber,
    IdentificationSource,
    InvalidContainerNumber,
    InvalidSizeTypeCode,
    SizeType,
)
from src.shared_kernel.domain import Result

#: Below this, a read is not worth writing to the register without a human.
DEFAULT_MINIMUM_CONFIDENCE = 0.80


@dataclass(frozen=True, kw_only=True)
class RecognitionOutcome:
    """What the Recognition context reports for one captured image."""

    job_id: str
    container_number: str
    size_type_code: str | None = None
    confidence: float = 1.0
    image_ref: str | None = None


class RecognitionTranslator:
    """Turns an OCR outcome into a command the registry will accept.

    Returns a :class:`Result` rather than raising, because a read that cannot
    be trusted is an ordinary, expected outcome of pointing a camera at a
    rusty container - not an exceptional one. The caller decides whether to
    queue it for human review or drop it.
    """

    def __init__(
        self, *, minimum_confidence: float = DEFAULT_MINIMUM_CONFIDENCE
    ) -> None:
        self._minimum_confidence = minimum_confidence

    def translate(
        self,
        outcome: RecognitionOutcome,
        observation: ConditionObservation,
        *,
        size_type_code: str | None = None,
    ) -> Result[RegisterContainerCommand]:
        """Validate and translate, or explain why the read is unusable.

        ``size_type_code`` overrides whatever OCR read, for the common case
        where an operator corrects the box type on the capture screen.
        """
        if outcome.confidence < self._minimum_confidence:
            return Result.fail(
                f"confidence {outcome.confidence:.2f} is below the "
                f"{self._minimum_confidence:.2f} threshold"
            )

        try:
            number = ContainerNumber.parse(outcome.container_number)
        except InvalidContainerNumber as error:
            return Result.fail(str(error))

        raw_size_type = size_type_code or outcome.size_type_code
        if not raw_size_type:
            return Result.fail("no size-type code was read or supplied")

        try:
            size_type = SizeType.parse(raw_size_type)
        except InvalidSizeTypeCode as error:
            return Result.fail(str(error))

        return Result.ok(
            RegisterContainerCommand(
                container_number=number.value,
                size_type_code=size_type.code,
                cleanliness=observation.cleanliness,
                structural=observation.structural,
                food_certified=observation.food_certified,
                source=IdentificationSource.OCR,
                inspected_by=observation.inspected_by,
                notes=observation.notes,
                evidence_image_ref=observation.evidence_image_ref or outcome.image_ref,
            )
        )
