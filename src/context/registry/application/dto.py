"""Data transfer objects at the application boundary.

Plain dataclasses on purpose. Pydantic belongs to the API layer, so keeping it
out here means the whole application can be driven from a test, a CLI or a
background worker without a web framework anywhere in sight.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.context.registry.domain import (
    Cleanliness,
    Container,
    IdentificationSource,
    Inspection,
    StructuralState,
)


# --------------------------------------------------------------------------- #
# Inbound - commands                                                           #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, kw_only=True)
class ConditionObservation:
    """What an inspector ticks on the capture form, before any grading.

    Carries observations only. The grade is never sent in from outside - it is
    derived by :class:`ConditionGradingPolicy`, so the client cannot claim a
    dirty box is food grade.
    """

    cleanliness: Cleanliness
    structural: StructuralState
    food_certified: bool = False
    inspected_by: str | None = None
    notes: str | None = None
    evidence_image_ref: str | None = None


@dataclass(frozen=True, kw_only=True)
class RegisterContainerCommand:
    container_number: str
    size_type_code: str
    cleanliness: Cleanliness
    structural: StructuralState
    food_certified: bool = False
    source: IdentificationSource = IdentificationSource.OCR
    inspected_by: str | None = None
    notes: str | None = None
    evidence_image_ref: str | None = None


@dataclass(frozen=True, kw_only=True)
class RecordInspectionCommand:
    container_number: str
    inspected_by: str
    cleanliness: Cleanliness
    structural: StructuralState
    food_certified: bool = False
    notes: str | None = None
    evidence_image_ref: str | None = None
    inspected_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class AmendContainerDetailsCommand:
    container_number: str
    size_type_code: str


# --------------------------------------------------------------------------- #
# Outbound - views                                                             #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, kw_only=True)
class InspectionView:
    id: UUID
    inspected_at: datetime
    inspected_by: str
    cleanliness: str
    structural: str
    cargo_grade: str
    notes: str | None
    evidence_image_ref: str | None

    @classmethod
    def of(cls, inspection: Inspection) -> InspectionView:
        return cls(
            id=inspection.id,
            inspected_at=inspection.inspected_at,
            inspected_by=inspection.inspected_by,
            cleanliness=str(inspection.condition.cleanliness),
            structural=str(inspection.condition.structural),
            cargo_grade=str(inspection.condition.cargo_grade),
            notes=inspection.notes,
            evidence_image_ref=inspection.evidence_image_ref,
        )


@dataclass(frozen=True, kw_only=True)
class ContainerView:
    """The container flattened into the text fields the Angular form shows.

    The identity is broken out into its four parts (acronym, category, serial,
    check digit) as well as the joined form, so the UI can render them in
    separate boxes without re-parsing anything.
    """

    number: str
    formatted_number: str
    owner_code: str
    equipment_category: str
    serial_number: str
    check_digit: int

    size_type_code: str
    size_label: str
    length_ft: int
    height_mm: int
    is_high_cube: bool
    container_type: str

    cleanliness: str
    structural: str
    cargo_grade: str
    is_available_for_loading: bool

    identified_at: datetime
    identified_by: str
    inspection_count: int
    last_inspected_at: datetime | None

    @classmethod
    def of(cls, container: Container) -> ContainerView:
        number = container.number
        size_type = container.size_type
        condition = container.condition
        latest = container.latest_inspection

        return cls(
            number=number.value,
            formatted_number=number.formatted,
            owner_code=number.owner_code,
            equipment_category=number.equipment_category,
            serial_number=number.serial_number,
            check_digit=number.check_digit,
            size_type_code=size_type.code,
            size_label=size_type.size_label,
            length_ft=size_type.length_ft,
            height_mm=size_type.height_mm,
            is_high_cube=size_type.is_high_cube,
            container_type=str(size_type.container_type),
            cleanliness=str(condition.cleanliness),
            structural=str(condition.structural),
            cargo_grade=str(condition.cargo_grade),
            is_available_for_loading=condition.is_available_for_loading,
            identified_at=container.identified_at,
            identified_by=str(container.identified_by),
            inspection_count=len(container.inspections),
            last_inspected_at=latest.inspected_at if latest else None,
        )


@dataclass(frozen=True, kw_only=True)
class ContainerDetailView:
    """A container together with its inspection history, newest first.

    The aggregate already holds the inspections once it is loaded, so a detail
    screen costs no extra query.
    """

    container: ContainerView
    inspections: list[InspectionView]

    @classmethod
    def of(cls, container: Container) -> ContainerDetailView:
        return cls(
            container=ContainerView.of(container),
            inspections=[InspectionView.of(i) for i in container.inspections],
        )
