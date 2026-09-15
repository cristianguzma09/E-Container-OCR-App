"""Facts the registry publishes about containers.

Payloads carry primitives (the container number as a string, not the value
object) so subscribers in other contexts never have to import this context's
model.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from src.context.registry.domain.model.condition import CargoGrade
from src.shared_kernel.domain import DomainEvent


@dataclass(frozen=True, kw_only=True)
class ContainerIdentified(DomainEvent):
    """A container was added to the registry for the first time."""

    container_number: str
    size_type_code: str
    source: str


@dataclass(frozen=True, kw_only=True)
class InspectionRecorded(DomainEvent):
    """An inspection was attached to a container."""

    container_number: str
    inspection_id: uuid.UUID
    cargo_grade: CargoGrade
    inspected_by: str


@dataclass(frozen=True, kw_only=True)
class ContainerConditionChanged(DomainEvent):
    """The grade a container is cleared for actually moved.

    Emitted only when the current condition changes - a repeat inspection that
    confirms the same grade does not raise this.
    """

    container_number: str
    previous_grade: CargoGrade
    new_grade: CargoGrade


@dataclass(frozen=True, kw_only=True)
class ContainerSizeTypeCorrected(DomainEvent):
    """A wrong size-type code (usually a bad OCR read) was fixed."""

    container_number: str
    previous_code: str
    new_code: str
