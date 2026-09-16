"""Translation between the storage shape and the aggregate.

Explicit both ways on purpose. Imperative SQLAlchemy mapping would let the ORM
write straight into the aggregate's private attributes, but then the domain's
invariants would be bypassed on load and lazy-loading would leak into the
application layer. Two small functions cost less than that.
"""

from __future__ import annotations

from src.context.registry.domain import (
    CargoGrade,
    Cleanliness,
    Condition,
    Container,
    ContainerNumber,
    IdentificationSource,
    Inspection,
    SizeType,
    StructuralState,
)
from src.context.registry.infrastructure.persistence.models import (
    ContainerModel,
    InspectionModel,
)


def _condition_of(model: ContainerModel | InspectionModel) -> Condition:
    return Condition(
        Cleanliness(model.cleanliness),
        StructuralState(model.structural),
        CargoGrade(model.cargo_grade),
    )


def inspection_to_domain(model: InspectionModel) -> Inspection:
    return Inspection(
        inspection_id=model.id,
        condition=_condition_of(model),
        inspected_at=model.inspected_at,
        inspected_by=model.inspected_by,
        notes=model.notes,
        evidence_image_ref=model.evidence_image_ref,
    )


def container_to_domain(model: ContainerModel) -> Container:
    """Rebuild the aggregate. Records no events - this is a load, not a change."""
    return Container(
        number=ContainerNumber(
            owner_code=model.owner_code,
            equipment_category=model.equipment_category,
            serial_number=model.serial_number,
            check_digit=model.check_digit,
        ),
        size_type=SizeType(model.size_type_code),
        condition=_condition_of(model),
        identified_at=model.identified_at,
        identified_by=IdentificationSource(model.identified_by),
        inspections=[inspection_to_domain(i) for i in model.inspections],
    )


def inspection_to_model(
    inspection: Inspection, container_number: str
) -> InspectionModel:
    return InspectionModel(
        id=inspection.id,
        container_number=container_number,
        cleanliness=str(inspection.condition.cleanliness),
        structural=str(inspection.condition.structural),
        cargo_grade=str(inspection.condition.cargo_grade),
        inspected_at=inspection.inspected_at,
        inspected_by=inspection.inspected_by,
        notes=inspection.notes,
        evidence_image_ref=inspection.evidence_image_ref,
    )


def container_to_model(container: Container) -> ContainerModel:
    number = container.number
    return ContainerModel(
        number=number.value,
        owner_code=number.owner_code,
        equipment_category=number.equipment_category,
        serial_number=number.serial_number,
        check_digit=number.check_digit,
        size_type_code=container.size_type.code,
        cleanliness=str(container.condition.cleanliness),
        structural=str(container.condition.structural),
        cargo_grade=str(container.condition.cargo_grade),
        identified_at=container.identified_at,
        identified_by=str(container.identified_by),
    )


def apply_to_model(model: ContainerModel, container: Container) -> None:
    """Copy the aggregate's mutable state onto an existing row.

    Identity fields are never touched: the number is the primary key, so a
    different number is a different container, not an update.
    """
    model.size_type_code = container.size_type.code
    model.cleanliness = str(container.condition.cleanliness)
    model.structural = str(container.condition.structural)
    model.cargo_grade = str(container.condition.cargo_grade)
