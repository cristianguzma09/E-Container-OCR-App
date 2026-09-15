"""Put a newly identified container on the register."""

from __future__ import annotations

from src.context.registry.application.dto import (
    ContainerView,
    RegisterContainerCommand,
)
from src.context.registry.application.errors import ContainerAlreadyRegistered
from src.context.registry.application.unit_of_work import RegistryUnitOfWork
from src.context.registry.domain import (
    ConditionGradingPolicy,
    Container,
    ContainerNumber,
    Inspection,
    SizeType,
)
from src.shared_kernel.application import EventDispatcher, UseCase


class RegisterContainerFromRecognition(
    UseCase[RegisterContainerCommand, ContainerView]
):
    """Validate a read, grade what was observed, and store the container.

    Note what this use case does *not* do: it never accepts a cargo grade from
    the caller. The grade is always derived here by the grading policy, so no
    client can register a dirty box as food grade.
    """

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

    def execute(self, request: RegisterContainerCommand) -> ContainerView:
        number = ContainerNumber.parse(request.container_number)
        size_type = SizeType.parse(request.size_type_code)
        condition = self._policy.assess(
            request.cleanliness,
            request.structural,
            food_certified=request.food_certified,
        )

        with self._uow as uow:
            if uow.containers.exists(number):
                raise ContainerAlreadyRegistered(number.value)

            container = Container.identify(
                number=number,
                size_type=size_type,
                condition=condition,
                source=request.source,
            )

            # When a person signed for the capture, the first look counts as
            # an inspection so the condition has provenance from day one.
            if request.inspected_by:
                container.record_inspection(
                    Inspection.record(
                        condition=condition,
                        inspected_by=request.inspected_by,
                        notes=request.notes,
                        evidence_image_ref=request.evidence_image_ref,
                        inspected_at=container.identified_at,
                    )
                )

            uow.containers.save(container)
            uow.commit()

        self._events.dispatch(container.pull_events())
        return ContainerView.of(container)
