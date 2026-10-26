"""The RecognitionJob aggregate root."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum

from src.context.recognition.domain.events import (
    RecognitionCompleted,
    RecognitionConfirmed,
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
    CONFIRMED = "CONFIRMED"


#: No further engine work may touch a job in one of these states.
TERMINAL = frozenset(
    {
        JobStatus.COMPLETED,
        JobStatus.NEEDS_REVIEW,
        JobStatus.FAILED,
        JobStatus.CONFIRMED,
    }
)

#: A person may only sign off a job that actually produced a reading.
#: A failed or still-running job has nothing to confirm.
CONFIRMABLE = frozenset({JobStatus.COMPLETED, JobStatus.NEEDS_REVIEW})


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
        confirmed_container_number: str | None = None,
        confirmed_by: str | None = None,
        confirmed_at: datetime | None = None,
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
        self._confirmed_container_number = confirmed_container_number
        self._confirmed_by = confirmed_by
        self._confirmed_at = confirmed_at

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
    def confirmed_container_number(self) -> str | None:
        """The number a person signed off, once they have."""
        return self._confirmed_container_number

    @property
    def confirmed_by(self) -> str | None:
        return self._confirmed_by

    @property
    def confirmed_at(self) -> datetime | None:
        return self._confirmed_at

    @property
    def is_confirmed(self) -> bool:
        return self._status is JobStatus.CONFIRMED

    @property
    def can_be_confirmed(self) -> bool:
        return self._status in CONFIRMABLE

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

    def confirm(
        self,
        container_number: str,
        *,
        confirmed_by: str,
        confirmed_at: datetime | None = None,
    ) -> None:
        """Record that a person signed off this reading.

        ``container_number`` is what the operator actually accepted, which is
        not always what the engine read - correcting a bad read is the whole
        point of the review queue. The difference between the two is kept as
        ``was_corrected`` on the event, because the rate at which operators
        override the engine is the only honest measure of how well it works.
        """
        if self._status not in CONFIRMABLE:
            raise BusinessRuleViolation(
                "recognition_job_not_confirmable",
                f"cannot confirm job {self.id}: it is {self._status}, "
                f"and only a job that produced a reading can be signed off",
            )

        number = (container_number or "").strip().upper()
        if not number:
            raise BusinessRuleViolation(
                "confirmation_needs_a_number",
                "a confirmation must name the container number being accepted",
            )
        if not confirmed_by or not confirmed_by.strip():
            raise BusinessRuleViolation(
                "confirmation_needs_an_operator",
                "a confirmation must name who signed it off",
            )

        read = self.best_candidate.value if self.best_candidate else None

        self._confirmed_container_number = number
        self._confirmed_by = confirmed_by.strip()
        self._confirmed_at = confirmed_at or datetime.now(UTC)
        self._status = JobStatus.CONFIRMED

        self.record_event(
            RecognitionConfirmed(
                job_id=self.id,
                image_ref=self._image_ref,
                container_number=number,
                confirmed_by=self._confirmed_by,
                was_corrected=read != number,
                was_read=read,
            )
        )

    def _guard_not_finished(self, action: str) -> None:
        if self.is_finished:
            raise BusinessRuleViolation(
                "recognition_job_already_finished",
                f"cannot {action} job {self.id}: it is already {self._status}",
            )
