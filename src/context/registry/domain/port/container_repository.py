"""Port: persistence for the Container aggregate."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.context.registry.domain.model.container import Container
from src.context.registry.domain.model.container_number import ContainerNumber


class ContainerRepository(ABC):
    """Collection-like access to Container aggregates.

    Declared in the domain, implemented in infrastructure with SQLAlchemy.
    Use cases only ever see this interface, so they can be tested against an
    in-memory fake with no database in sight.
    """

    @abstractmethod
    def get(self, number: ContainerNumber) -> Container | None:
        """Return the container, or ``None`` if it was never registered."""

    @abstractmethod
    def save(self, container: Container) -> None:
        """Insert or update the aggregate, inspections included."""

    @abstractmethod
    def exists(self, number: ContainerNumber) -> bool:
        """Cheap existence check that avoids loading the whole aggregate."""

    @abstractmethod
    def list(self, *, limit: int = 50, offset: int = 0) -> list[Container]:
        """Page through registered containers, newest identification first."""
