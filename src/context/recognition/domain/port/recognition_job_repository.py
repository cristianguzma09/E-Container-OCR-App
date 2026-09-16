"""Port: persistence for the RecognitionJob aggregate."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from src.context.recognition.domain.model.recognition_job import (
    JobStatus,
    RecognitionJob,
)


class RecognitionJobRepository(ABC):
    """Collection-like access to recognition jobs."""

    @abstractmethod
    def get(self, job_id: UUID) -> RecognitionJob | None:
        """Return the job, or ``None`` if there is no such job."""

    @abstractmethod
    def save(self, job: RecognitionJob) -> None:
        """Insert or update the aggregate."""

    @abstractmethod
    def list(
        self,
        *,
        status: JobStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RecognitionJob]:
        """Page through jobs, newest first; optionally filtered by status.

        Filtering by ``NEEDS_REVIEW`` is what drives the review queue.
        """
