"""The registry's transactional boundary."""

from __future__ import annotations

from src.context.registry.domain import ContainerRepository, InspectionRepository
from src.shared_kernel.application import UnitOfWork


class RegistryUnitOfWork(UnitOfWork):
    """Binds the registry's repositories to one transaction.

    Implementations (a SQLAlchemy one in infrastructure, a fake one in tests)
    assign the two attributes before the ``with`` block body runs, so a use
    case never builds a repository itself and never sees a session.
    """

    containers: ContainerRepository
    inspections: InspectionRepository
