"""The RecognitionJob aggregate root."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum

from src.context.recognition.domain.events import (
    RecognitionCompleted,
    RecognitionFailed,
    RecognitionRequested,
)
from src.context.recognition.domain.model.container_code_candidate import (
    ContainerCodeCandidate,
)
from src.context.recognition.domain.model.text_fragment import TextFragment
from src.shared_kernel.domain import AggregateRoot, BusinessRuleViolation


class JobStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAILED = "FAILED"


TERMINAL = frozenset({JobStatus.COMPLETED, JobStatus.NEEDS_REVIEW, JobStatus.FAILED})


class RecognitionJob(AggregateRoot[uuid.UUID]):
    """One captured image, from upload to a readable answer.

    The three ways a job can end are deliberately distinct:

    * ``COMPLETED`` - a number was read and its check digit proves it out.
    * ``NEEDS_REVIEW`` - something was read but cannot be trusted on its own,
      or nothing was read at all. A person decides.
    * ``FAILED`` - the engine itself broke. An operational fault, not a
      judgement about the photo.

    Collapsing the middle case into either of the others is what makes OCR
    systems quietly wrong: an unreadable photo is not an error, and it is not
    an answer either.
    """

    def __init__(
        self,
        *,
        job_id: uuid.UUID,
        image_ref: str,
        submitted_at: datetime,
        submitted_by: str | None = None,
        status: JobStatus = JobStatus.PENDING,
        fragments: Sequence[TextFragment] = (),
        candidates: Sequence[ContainerCodeCandidate] = (),
        failure_reason: str | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        super().__init__(job_id)
        self._image_ref = image_ref
        self._submitted_at = submitted_at
        self._submitted_by = submitted_by
        self._status = status
        self._fragments = tuple(fragments)
        self._candidates = tuple(candidates)
        self._failure_reason = failure_reason
        self._completed_at = completed_at

    @classmethod
    def submit(
        cls,
        *,
        image_ref: str,
        submitted_by: str | None = None,
        job_id: uuid.UUID | None = None,
        submitted_at: datetime | None = None,
    ) -> RecognitionJob:
        if not image_ref or not image_ref.strip():
            raise BusinessRuleViolation(
                "recognition_needs_an_image",
                "a job cannot be submitted without a stored image",
            )

        job = cls(
            job_id=job_id or uuid.uuid4(),
            image_ref=image_ref.strip(),
            submitted_at=submitted_at or datetime.now(UTC),
            submitted_by=submitted_by,
        )
        job.record_event(
            RecognitionRequested(job_id=job.id, image_ref=job.image_ref)
        )
        return job

    # -- state -------------------------------------------------------------
    @property
    def image_ref(self) -> str:
        return self._image_ref

    @property
    def submitted_at(self) -> datetime:
        return self._submitted_at

    @property
    def submitted_by(self) -> str | None:
        return self._submitted_by

    @property
    def status(self) -> JobStatus:
        return self._status

    @property
    def fragments(self) -> tuple[TextFragment, ...]:
        return self._fragments

    @property
    def candidates(self) -> tuple[ContainerCodeCandidate, ...]:
        """Every reading considered, best first."""
        return self._candidates

    @property
    def best_candidate(self) -> ContainerCodeCandidate | None:
        return self._candidates[0] if self._candidates else None

    @property
    def failure_reason(self) -> str | None:
        return self._failure_reason

    @property
    def completed_at(self) -> datetime | None:
        return self._completed_at

    @property
    def is_finished(self) -> bool:
        return self._status in TERMINAL

    @property
    def is_conclusive(self) -> bool:
        """True only when the answer can be used without a person checking."""
        return self._status is JobStatus.COMPLETED

    # -- behaviour ---------------------------------------------------------
    def start(self) -> None:
        self._guard_not_finished("start")
        if self._status is JobStatus.PROCESSING:
            return
        self._status = JobStatus.PROCESSING

    def complete(
        self,
        fragments: Sequence[TextFragment],
        candidates: Sequence[ContainerCodeCandidate],
        *,
        completed_at: datetime | None = None,
    ) -> None:
        """Record what the engine read and decide whether it can be trusted."""
        self._guard_not_finished("complete")

        self._fragments = tuple(fragments)
        self._candidates = tuple(candidates)
        self._completed_at = completed_at or datetime.now(UTC)

        best = self.best_candidate
        trustworthy = best is not None and not best.needs_human_confirmation
        self._status = JobStatus.COMPLETED if trustworthy else JobStatus.NEEDS_REVIEW

        self.record_event(
            RecognitionCompleted(
                job_id=self.id,
                image_ref=self._image_ref,
                container_number=best.value if best else None,
                confidence=best.confidence.value if best else 0.0,
                check_digit_valid=bool(best and best.check_digit_valid),
                repaired=bool(best and best.repaired),
                conclusive=trustworthy,
            )
        )

    def fail(self, reason: str, *, completed_at: datetime | None = None) -> None:
        self._guard_not_finished("fail")
        self._status = JobStatus.FAILED
        self._failure_reason = reason
        self._completed_at = completed_at or datetime.now(UTC)
        self.record_event(
            RecognitionFailed(
                job_id=self.id, image_ref=self._image_ref, reason=reason
            )
        )

    def _guard_not_finished(self, action: str) -> None:
        if self.is_finished:
            raise BusinessRuleViolation(
                "recognition_job_already_finished",
                f"cannot {action} job {self.id}: it is already {self._status}",
            )
