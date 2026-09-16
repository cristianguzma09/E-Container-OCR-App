"""Read-only recognition use cases."""

from __future__ import annotations

from src.context.recognition.application.dto import (
    JobListQuery,
    JobQuery,
    RecognitionJobView,
)
from src.context.recognition.application.errors import RecognitionJobNotFound
from src.context.recognition.application.unit_of_work import RecognitionUnitOfWork
from src.shared_kernel.application import UseCase


class GetRecognitionResult(UseCase[JobQuery, RecognitionJobView]):
    """What the capture screen polls after uploading."""

    def __init__(self, uow: RecognitionUnitOfWork) -> None:
        self._uow = uow

    def execute(self, request: JobQuery) -> RecognitionJobView:
        with self._uow as uow:
            job = uow.jobs.get(request.job_id)
            if job is None:
                raise RecognitionJobNotFound(request.job_id)
            return RecognitionJobView.of(job)


class ListRecognitionJobs(UseCase[JobListQuery, list[RecognitionJobView]]):
    """Page through jobs; filtering by NEEDS_REVIEW gives the review queue."""

    def __init__(self, uow: RecognitionUnitOfWork) -> None:
        self._uow = uow

    def execute(self, request: JobListQuery) -> list[RecognitionJobView]:
        with self._uow as uow:
            jobs = uow.jobs.list(
                status=request.status, limit=request.limit, offset=request.offset
            )
            return [RecognitionJobView.of(job) for job in jobs]
