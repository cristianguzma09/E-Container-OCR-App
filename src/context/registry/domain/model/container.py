"""The Container aggregate root."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from src.context.registry.domain.events.container_events import (
    ContainerConditionChanged,
    ContainerIdentified,
    ContainerSizeTypeCorrected,
    InspectionRecorded,
)
from src.context.registry.domain.model.condition import Condition
from src.context.registry.domain.model.container_number import ContainerNumber
from src.context.registry.domain.model.inspection import Inspection
from src.context.registry.domain.model.size_type import ContainerType, SizeType
from src.shared_kernel.domain import AggregateRoot, BusinessRuleViolation


class IdentificationSource(StrEnum):
    """How the container's identity reached the registry."""

    OCR = "OCR"
    MANUAL = "MANUAL"
    IMPORT = "IMPORT"


class Container(AggregateRoot[ContainerNumber]):
    """A physical maritime container, as the business tracks it.

    Identity is the ISO 6346 number itself - two records carrying the same
    number are the same box - so the domain has no surrogate id. Inspections
    belong to this aggregate and are only reachable through it, which is what
    guarantees ``condition`` always matches the newest inspection on file.
    """

    def __init__(
        self,
        *,
        number: ContainerNumber,
        size_type: SizeType,
        condition: Condition,
        identified_at: datetime,
        identified_by: IdentificationSource,
        inspections: list[Inspection] | None = None,
    ) -> None:
        super().__init__(number)
        self._size_type = size_type
        self._condition = condition
        self._identified_at = identified_at
        self._identified_by = identified_by
        self._inspections: list[Inspection] = list(inspections or [])

    @classmethod
    def identify(
        cls,
        *,
        number: ContainerNumber,
        size_type: SizeType,
        condition: Condition,
        source: IdentificationSource = IdentificationSource.OCR,
        identified_at: datetime | None = None,
    ) -> Container:
        """Register a container the first time it is seen."""
        container = cls(
            number=number,
            size_type=size_type,
            condition=condition,
            identified_at=identified_at or datetime.now(UTC),
            identified_by=source,
        )
        container.record_event(
            ContainerIdentified(
                container_number=number.value,
                size_type_code=size_type.code,
                source=str(source),
            )
        )
        return container

    # -- state -------------------------------------------------------------
    @property
    def number(self) -> ContainerNumber:
        return self.id

    @property
    def size_type(self) -> SizeType:
        return self._size_type

    @property
    def container_type(self) -> ContainerType:
        return self._size_type.container_type

    @property
    def size_label(self) -> str:
        return self._size_type.size_label

    @property
    def condition(self) -> Condition:
        """The condition from the most recent inspection on file."""
        return self._condition

    @property
    def identified_at(self) -> datetime:
        return self._identified_at

    @property
    def identified_by(self) -> IdentificationSource:
        return self._identified_by

    @property
    def inspections(self) -> tuple[Inspection, ...]:
        """The full history, newest first."""
        return tuple(
            sorted(self._inspections, key=lambda i: i.inspected_at, reverse=True)
        )

    @property
    def latest_inspection(self) -> Inspection | None:
        return self.inspections[0] if self._inspections else None

    @property
    def is_available_for_loading(self) -> bool:
        return self._condition.is_available_for_loading

    # -- behaviour ---------------------------------------------------------
    def record_inspection(self, inspection: Inspection) -> None:
        """Attach an inspection; adopt its condition if it is the newest one.

        A late-arriving inspection (one stamped earlier than the latest on
        file) is still kept for the history, but it does not overwrite the
        current condition.
        """
        if any(existing.id == inspection.id for existing in self._inspections):
            raise BusinessRuleViolation(
                "inspection_already_recorded",
                f"inspection {inspection.id} is already on container {self.number}",
            )

        latest = self.latest_inspection
        is_newest = latest is None or inspection.inspected_at >= latest.inspected_at

        previous_grade = self._condition.cargo_grade
        self._inspections.append(inspection)
        if is_newest:
            self._condition = inspection.condition

        self.record_event(
            InspectionRecorded(
                container_number=self.number.value,
                inspection_id=inspection.id,
                cargo_grade=inspection.condition.cargo_grade,
                inspected_by=inspection.inspected_by,
            )
        )

        if is_newest and previous_grade is not inspection.condition.cargo_grade:
            self.record_event(
                ContainerConditionChanged(
                    container_number=self.number.value,
                    previous_grade=previous_grade,
                    new_grade=inspection.condition.cargo_grade,
                )
            )

    def correct_size_type(self, size_type: SizeType) -> None:
        """Fix a size-type that OCR or a clerk got wrong. A no-op if unchanged."""
        if size_type == self._size_type:
            return

        previous = self._size_type
        self._size_type = size_type
        self.record_event(
            ContainerSizeTypeCorrected(
                container_number=self.number.value,
                previous_code=previous.code,
                new_code=size_type.code,
            )
        )
