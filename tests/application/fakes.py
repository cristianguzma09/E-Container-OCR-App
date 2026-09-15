"""In-memory stand-ins for the registry's ports.

These are what make the application layer testable without Postgres. The fake
unit of work genuinely rolls back, so "the use case failed, therefore nothing
was written" is a real assertion rather than a hopeful one.
"""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from src.context.registry.application import RegistryUnitOfWork
from src.context.registry.domain import (
    Container,
    ContainerNumber,
    ContainerRepository,
    Inspection,
    InspectionRepository,
)
from src.shared_kernel.application import EventDispatcher
from src.shared_kernel.domain import DomainEvent


class InMemoryContainerRepository(ContainerRepository):
    def __init__(self, storage: dict[str, Container] | None = None) -> None:
        self._storage: dict[str, Container] = storage if storage is not None else {}

    def get(self, number: ContainerNumber) -> Container | None:
        return self._storage.get(number.value)

    def save(self, container: Container) -> None:
        self._storage[container.number.value] = container

    def exists(self, number: ContainerNumber) -> bool:
        return number.value in self._storage

    def list(self, *, limit: int = 50, offset: int = 0) -> list[Container]:
        ordered = sorted(
            self._storage.values(), key=lambda c: c.identified_at, reverse=True
        )
        return ordered[offset : offset + limit]

    def all(self) -> list[Container]:
        return list(self._storage.values())


class InMemoryInspectionRepository(InspectionRepository):
    def __init__(self, containers: InMemoryContainerRepository) -> None:
        self._containers = containers

    def get(self, inspection_id: UUID) -> Inspection | None:
        for container in self._containers.all():
            for inspection in container.inspections:
                if inspection.id == inspection_id:
                    return inspection
        return None

    def list_for_container(
        self, number: ContainerNumber, *, limit: int = 50, offset: int = 0
    ) -> list[Inspection]:
        container = self._containers.get(number)
        if container is None:
            return []
        return list(container.inspections)[offset : offset + limit]


class FakeRegistryUnitOfWork(RegistryUnitOfWork):
    """A unit of work whose rollback actually restores the previous state."""

    def __init__(self, containers: dict[str, Container] | None = None) -> None:
        self._storage: dict[str, Container] = dict(containers or {})
        self.containers = InMemoryContainerRepository(self._storage)
        self.inspections = InMemoryInspectionRepository(self.containers)
        self.committed = False
        self.rolled_back = False
        self._snapshot: dict[str, Container] = dict(self._storage)

    def __enter__(self) -> FakeRegistryUnitOfWork:
        self._snapshot = dict(self._storage)
        self.committed = False
        self.rolled_back = False
        return self

    def commit(self) -> None:
        self.committed = True
        self._snapshot = dict(self._storage)

    def rollback(self) -> None:
        if self.committed:
            return
        self._storage.clear()
        self._storage.update(self._snapshot)
        self.rolled_back = True

    @property
    def stored(self) -> dict[str, Container]:
        return self._storage


class RecordingEventDispatcher(EventDispatcher):
    """Remembers everything it was asked to publish, then publishes it."""

    def __init__(self) -> None:
        super().__init__()
        self.published: list[DomainEvent] = []

    def dispatch(self, events: Iterable[DomainEvent]) -> None:
        batch = list(events)
        self.published.extend(batch)
        super().dispatch(batch)

    def of_type[T: DomainEvent](self, event_type: type[T]) -> list[T]:
        return [e for e in self.published if isinstance(e, event_type)]
