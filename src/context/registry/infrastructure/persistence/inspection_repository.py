"""SQLAlchemy implementation of the read-only inspection query port."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.context.registry.domain import (
    ContainerNumber,
    Inspection,
    InspectionRepository,
)
from src.context.registry.infrastructure.persistence.mappers import inspection_to_domain
from src.context.registry.infrastructure.persistence.models import InspectionModel


class SqlAlchemyInspectionRepository(InspectionRepository):
    """Serves history screens without loading whole aggregates.

    Read-only by design - inspections are written through the Container
    aggregate, which is what keeps the current condition and the history from
    disagreeing.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, inspection_id: UUID) -> Inspection | None:
        model = self._session.get(InspectionModel, inspection_id)
        return inspection_to_domain(model) if model is not None else None

    def list_for_container(
        self, number: ContainerNumber, *, limit: int = 50, offset: int = 0
    ) -> list[Inspection]:
        statement = (
            select(InspectionModel)
            .where(InspectionModel.container_number == number.value)
            .order_by(InspectionModel.inspected_at.desc(), InspectionModel.id)
            .limit(limit)
            .offset(offset)
        )
        return [inspection_to_domain(m) for m in self._session.scalars(statement)]
