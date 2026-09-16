"""SQLAlchemy implementation of the Container repository port."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.context.registry.domain import Container, ContainerNumber, ContainerRepository
from src.context.registry.infrastructure.persistence.mappers import (
    apply_to_model,
    container_to_domain,
    container_to_model,
    inspection_to_model,
)
from src.context.registry.infrastructure.persistence.models import ContainerModel


class SqlAlchemyContainerRepository(ContainerRepository):
    """Persists the aggregate through a session owned by the unit of work."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, number: ContainerNumber) -> Container | None:
        model = self._session.get(ContainerModel, number.value)
        return container_to_domain(model) if model is not None else None

    def save(self, container: Container) -> None:
        """Insert or update the container, then append any new inspections.

        Existing inspections are never rewritten: an inspection is a record of
        what someone saw at a moment in time, so it is append-only.
        """
        model = self._session.get(ContainerModel, container.number.value)

        if model is None:
            model = container_to_model(container)
            self._session.add(model)
        else:
            apply_to_model(model, container)

        stored_ids = {inspection.id for inspection in model.inspections}
        for inspection in container.inspections:
            if inspection.id not in stored_ids:
                model.inspections.append(
                    inspection_to_model(inspection, container.number.value)
                )

    def exists(self, number: ContainerNumber) -> bool:
        statement = (
            select(func.count())
            .select_from(ContainerModel)
            .where(ContainerModel.number == number.value)
        )
        return bool(self._session.scalar(statement))

    def list(self, *, limit: int = 50, offset: int = 0) -> list[Container]:
        statement = (
            select(ContainerModel)
            .order_by(ContainerModel.identified_at.desc(), ContainerModel.number)
            .limit(limit)
            .offset(offset)
        )
        return [container_to_domain(m) for m in self._session.scalars(statement)]
