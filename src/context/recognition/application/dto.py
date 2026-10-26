"""Data transfer objects at the recognition boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.context.recognition.domain import (
    ContainerCodeCandidate,
    JobStatus,
    RecognitionJob,
    TextFragment,
)


# --------------------------------------------------------------------------- #
# Inbound                                                                      #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, kw_only=True)
class SubmitImageCommand:
    image: bytes
    content_type: str
    submitted_by: str | None = None


@dataclass(frozen=True, kw_only=True)
class ProcessJobCommand:
    job_id: UUID


@dataclass(frozen=True, kw_only=True)
class JobQuery:
    job_id: UUID


@dataclass(frozen=True, kw_only=True)
class JobListQuery:
    status: JobStatus | None = None
    limit: int = 50
    offset: int = 0


# --------------------------------------------------------------------------- #
# Outbound                                                                     #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, kw_only=True)
class CandidateView:
    value: str
    raw_text: str
    confidence: float
    score: float
    check_digit_valid: bool
    expected_check_digit: int | None
    repaired: bool
    needs_human_confirmation: bool

    @classmethod
    def of(cls, candidate: ContainerCodeCandidate) -> CandidateView:
        return cls(
            value=candidate.value,
            raw_text=candidate.raw_text,
            confidence=candidate.confidence.value,
            score=candidate.score,
            check_digit_valid=candidate.check_digit_valid,
            expected_check_digit=candidate.expected_check_digit,
            repaired=candidate.repaired,
            needs_human_confirmation=candidate.needs_human_confirmation,
        )


@dataclass(frozen=True, kw_only=True)
class FragmentView:
    text: str
    confidence: float

    @classmethod
    def of(cls, fragment: TextFragment) -> FragmentView:
        return cls(text=fragment.text, confidence=fragment.confidence.value)


@dataclass(frozen=True, kw_only=True)
class RecognitionJobView:
    """What the capture screen polls for.

    ``container_number`` is filled in only when the job is conclusive. When it
    is not, ``candidates`` still carries everything that was read so an
    operator can pick or correct - the point is that the client cannot mistake
    a guess for an answer.
    """

    id: UUID
    status: str
    image_ref: str
    submitted_at: datetime
    submitted_by: str | None
    completed_at: datetime | None
    failure_reason: str | None

    confirmed_container_number: str | None
    confirmed_by: str | None
    confirmed_at: datetime | None

    container_number: str | None
    confidence: float | None
    check_digit_valid: bool | None
    repaired: bool | None
    needs_review: bool

    candidates: list[CandidateView]
    fragments: list[FragmentView]

    @classmethod
    def of(cls, job: RecognitionJob) -> RecognitionJobView:
        best = job.best_candidate
        return cls(
            id=job.id,
            status=str(job.status),
            image_ref=job.image_ref,
            submitted_at=job.submitted_at,
            submitted_by=job.submitted_by,
            completed_at=job.completed_at,
            failure_reason=job.failure_reason,
            confirmed_container_number=job.confirmed_container_number,
            confirmed_by=job.confirmed_by,
            confirmed_at=job.confirmed_at,
            # Once a person has signed a number off it is the answer, whatever
            # the engine made of the photo.
            container_number=(
                job.confirmed_container_number
                if job.is_confirmed
                else (best.value if job.is_conclusive and best else None)
            ),
            confidence=best.confidence.value if best else None,
            check_digit_valid=best.check_digit_valid if best else None,
            repaired=best.repaired if best else None,
            needs_review=job.status is JobStatus.NEEDS_REVIEW,
            candidates=[CandidateView.of(c) for c in job.candidates],
            fragments=[FragmentView.of(f) for f in job.fragments],
        )
