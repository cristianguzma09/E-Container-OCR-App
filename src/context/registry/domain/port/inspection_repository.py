"""Port: read-only queries over inspection history."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from src.context.registry.domain.model.container_number import ContainerNumber
from src.context.registry.domain.model.inspection import Inspection


class InspectionRepository(ABC):
    """Read-only access to inspections.

    Deliberately has no ``save``. Inspections are written through the
    :class:`~...model.container.Container` aggregate and never on their own -
    that is what keeps a container's current condition and its history in
    step. This port exists only so history screens can be served without
    loading whole aggregates.
    """

    @abstractmethod
    def get(self, inspection_id: UUID) -> Inspection | None:
        """Return one inspection, or ``None`` if it does not exist."""

    @abstractmethod
    def list_for_container(
        self, number: ContainerNumber, *, limit: int = 50, offset: int = 0
    ) -> list[Inspection]:
        """Page through a container's inspections, newest first."""
