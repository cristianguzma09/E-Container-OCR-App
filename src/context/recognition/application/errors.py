"""Errors raised by the recognition use cases."""

from __future__ import annotations

from uuid import UUID


class RecognitionApplicationError(Exception):
    """Base class for failures a recognition use case reports to its caller."""


class RecognitionJobNotFound(RecognitionApplicationError):
    """No job exists under that id."""

    def __init__(self, job_id: UUID | str) -> None:
        self.job_id = str(job_id)
        super().__init__(f"recognition job {job_id} does not exist")
