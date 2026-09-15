"""A single condition assessment of a container."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from src.context.registry.domain.model.condition import Condition
from src.shared_kernel.domain import BusinessRuleViolation, Entity


class Inspection(Entity[uuid.UUID]):
    """What one inspector found, and when.

    Lives inside the :class:`Container` aggregate: inspections are created and
    read through the container, never persisted on their own. That is what
    keeps a container's current condition and its history from disagreeing.
    """

    def __init__(
        self,
        *,
        inspection_id: uuid.UUID,
        condition: Condition,
        inspected_at: datetime,
        inspected_by: str,
        notes: str | None = None,
        evidence_image_ref: str | None = None,
    ) -> None:
        if not inspected_by or not inspected_by.strip():
            raise BusinessRuleViolation(
                "inspection_needs_an_inspector",
                "every inspection must name who carried it out",
            )

        super().__init__(inspection_id)
        self.condition = condition
        self.inspected_at = inspected_at
        self.inspected_by = inspected_by.strip()
        self.notes = notes
        self.evidence_image_ref = evidence_image_ref

    @classmethod
    def record(
        cls,
        *,
        condition: Condition,
        inspected_by: str,
        notes: str | None = None,
        evidence_image_ref: str | None = None,
        inspected_at: datetime | None = None,
    ) -> Inspection:
        """Create a new inspection, stamped now unless a time is given."""
        return cls(
            inspection_id=uuid.uuid4(),
            condition=condition,
            inspected_at=inspected_at or datetime.now(UTC),
            inspected_by=inspected_by,
            notes=notes,
            evidence_image_ref=evidence_image_ref,
        )
