"""SQLAlchemy implementation of the recognition job repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.context.recognition.domain import (
    JobStatus,
    RecognitionJob,
    RecognitionJobRepository,
)
from src.context.recognition.infrastructure.persistence.mappers import (
    apply_to_model,
    job_to_domain,
    job_to_model,
)
from src.context.recognition.infrastructure.persistence.models import (
    RecognitionJobModel,
)


class SqlAlchemyRecognitionJobRepository(RecognitionJobRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, job_id: UUID) -> RecognitionJob | None:
        model = self._session.get(RecognitionJobModel, job_id)
        return job_to_domain(model) if model is not None else None

    def save(self, job: RecognitionJob) -> None:
        model = self._session.get(RecognitionJobModel, job.id)
        if model is None:
            self._session.add(job_to_model(job))
        else:
            apply_to_model(model, job)

    def list(
        self,
        *,
        status: JobStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RecognitionJob]:
        statement = select(RecognitionJobModel)
        if status is not None:
            statement = statement.where(RecognitionJobModel.status == str(status))
        statement = (
            statement.order_by(
                RecognitionJobModel.submitted_at.desc(), RecognitionJobModel.id
            )
            .limit(limit)
            .offset(offset)
        )
        return [job_to_domain(m) for m in self._session.scalars(statement)]
