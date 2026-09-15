"""Correct details that OCR or a clerk got wrong."""

from __future__ import annotations

from src.context.registry.application.dto import (
    AmendContainerDetailsCommand,
    ContainerView,
)
from src.context.registry.application.errors import ContainerNotFound
from src.context.registry.application.unit_of_work import RegistryUnitOfWork
from src.context.registry.domain import ContainerNumber, SizeType
from src.shared_kernel.application import EventDispatcher, UseCase


class AmendContainerDetails(UseCase[AmendContainerDetailsCommand, ContainerView]):
    """Fix a container's size-type code.

    The number itself is never amended: it is the container's identity, so a
    wrong number means the wrong container was registered. That is a delete
    and a fresh capture, not an edit.
    """

    def __init__(
        self,
        uow: RegistryUnitOfWork,
        *,
        events: EventDispatcher | None = None,
    ) -> None:
        self._uow = uow
        self._events = events or EventDispatcher()

    def execute(self, request: AmendContainerDetailsCommand) -> ContainerView:
        number = ContainerNumber.parse(request.container_number)
        size_type = SizeType.parse(request.size_type_code)

        with self._uow as uow:
            container = uow.containers.get(number)
            if container is None:
                raise ContainerNotFound(number.value)

            container.correct_size_type(size_type)
            uow.containers.save(container)
            uow.commit()

        self._events.dispatch(container.pull_events())
        return ContainerView.of(container)
