"""Read-only use cases.

Grouped in one module because none of them do anything but load and map: there
is no orchestration to keep apart. Commands, which change state and emit
events, each keep their own file.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.context.registry.application.dto import (
    ContainerDetailView,
    ContainerView,
    InspectionView,
)
from src.context.registry.application.errors import ContainerNotFound
from src.context.registry.application.unit_of_work import RegistryUnitOfWork
from src.context.registry.domain import ContainerNumber
from src.shared_kernel.application import UseCase


@dataclass(frozen=True, kw_only=True)
class ContainerQuery:
    container_number: str


@dataclass(frozen=True, kw_only=True)
class PagedQuery:
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True, kw_only=True)
class InspectionHistoryQuery:
    container_number: str
    limit: int = 50
    offset: int = 0


class GetContainer(UseCase[ContainerQuery, ContainerDetailView]):
    """Fetch one container with its inspection history."""

    def __init__(self, uow: RegistryUnitOfWork) -> None:
        self._uow = uow

    def execute(self, request: ContainerQuery) -> ContainerDetailView:
        number = ContainerNumber.parse(request.container_number)
        with self._uow as uow:
            container = uow.containers.get(number)
            if container is None:
                raise ContainerNotFound(number.value)
            return ContainerDetailView.of(container)


class ListContainers(UseCase[PagedQuery, list[ContainerView]]):
    """Page through the register."""

    def __init__(self, uow: RegistryUnitOfWork) -> None:
        self._uow = uow

    def execute(self, request: PagedQuery) -> list[ContainerView]:
        with self._uow as uow:
            containers = uow.containers.list(
                limit=request.limit, offset=request.offset
            )
            return [ContainerView.of(c) for c in containers]


class GetInspectionHistory(UseCase[InspectionHistoryQuery, list[InspectionView]]):
    """Page through one container's inspections without loading the aggregate."""

    def __init__(self, uow: RegistryUnitOfWork) -> None:
        self._uow = uow

    def execute(self, request: InspectionHistoryQuery) -> list[InspectionView]:
        number = ContainerNumber.parse(request.container_number)
        with self._uow as uow:
            if not uow.containers.exists(number):
                raise ContainerNotFound(number.value)
            inspections = uow.inspections.list_for_container(
                number, limit=request.limit, offset=request.offset
            )
            return [InspectionView.of(i) for i in inspections]
