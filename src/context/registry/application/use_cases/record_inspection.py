"""Attach a new inspection to a container already on the register."""

from __future__ import annotations

from src.context.registry.application.dto import ContainerView, RecordInspectionCommand
from src.context.registry.application.errors import ContainerNotFound
from src.context.registry.application.unit_of_work import RegistryUnitOfWork
from src.context.registry.domain import (
    ConditionGradingPolicy,
    ContainerNumber,
    Inspection,
)
from src.shared_kernel.application import EventDispatcher, UseCase


class RecordInspection(UseCase[RecordInspectionCommand, ContainerView]):
    """Grade what the inspector observed and add it to the container's history."""

    def __init__(
        self,
        uow: RegistryUnitOfWork,
        *,
        grading_policy: ConditionGradingPolicy | None = None,
        events: EventDispatcher | None = None,
    ) -> None:
        self._uow = uow
        self._policy = grading_policy or ConditionGradingPolicy()
        self._events = events or EventDispatcher()

    def execute(self, request: RecordInspectionCommand) -> ContainerView:
        number = ContainerNumber.parse(request.container_number)
        condition = self._policy.assess(
            request.cleanliness,
            request.structural,
            food_certified=request.food_certified,
        )

        with self._uow as uow:
            container = uow.containers.get(number)
            if container is None:
                raise ContainerNotFound(number.value)

            container.record_inspection(
                Inspection.record(
                    condition=condition,
                    inspected_by=request.inspected_by,
                    notes=request.notes,
                    evidence_image_ref=request.evidence_image_ref,
                    inspected_at=request.inspected_at,
                )
            )

            uow.containers.save(container)
            uow.commit()

        self._events.dispatch(container.pull_events())
        return ContainerView.of(container)
