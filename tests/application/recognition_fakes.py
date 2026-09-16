"""In-memory stand-ins for the recognition ports."""

from __future__ import annotations

import uuid
from uuid import UUID

from src.context.recognition.application import RecognitionUnitOfWork
from src.context.recognition.domain import (
    ImageStore,
    InvalidImage,
    JobStatus,
    RecognitionJob,
    RecognitionJobRepository,
)


class InMemoryImageStore(ImageStore):
    def __init__(self) -> None:
        self.saved: dict[str, bytes] = {}

    def save(self, image: bytes, *, content_type: str) -> str:
        reference = f"memory/{uuid.uuid4().hex}"
        self.saved[reference] = image
        return reference

    def load(self, reference: str) -> bytes:
        try:
            return self.saved[reference]
        except KeyError as error:
            raise InvalidImage(f"stored image '{reference}' is missing") from error

    def delete(self, reference: str) -> None:
        self.saved.pop(reference, None)


class InMemoryRecognitionJobRepository(RecognitionJobRepository):
    def __init__(self, storage: dict[UUID, RecognitionJob] | None = None) -> None:
        self._storage = storage if storage is not None else {}

    def get(self, job_id: UUID) -> RecognitionJob | None:
        return self._storage.get(job_id)

    def save(self, job: RecognitionJob) -> None:
        self._storage[job.id] = job

    def list(
        self,
        *,
        status: JobStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RecognitionJob]:
        jobs = sorted(
            self._storage.values(), key=lambda j: j.submitted_at, reverse=True
        )
        if status is not None:
            jobs = [j for j in jobs if j.status is status]
        return jobs[offset : offset + limit]


class FakeRecognitionUnitOfWork(RecognitionUnitOfWork):
    """Rolls back for real, so "it failed, nothing was written" is testable."""

    def __init__(self) -> None:
        self._storage: dict[UUID, RecognitionJob] = {}
        self.jobs = InMemoryRecognitionJobRepository(self._storage)
        self.committed = False
        self.rolled_back = False
        self._snapshot: dict[UUID, RecognitionJob] = {}

    def __enter__(self) -> FakeRecognitionUnitOfWork:
        self._snapshot = dict(self._storage)
        self.committed = False
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
    def stored(self) -> dict[UUID, RecognitionJob]:
        return self._storage
