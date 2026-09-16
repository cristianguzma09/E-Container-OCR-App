"""Unit tests for the RecognitionJob aggregate."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.context.recognition.domain import (
    Confidence,
    ContainerCodeCandidate,
    JobStatus,
    RecognitionCompleted,
    RecognitionFailed,
    RecognitionJob,
    RecognitionRequested,
    TextFragment,
)
from src.shared_kernel.domain import BusinessRuleViolation

AT = datetime(2026, 9, 16, 9, 0, tzinfo=UTC)
VALID = "CSQU3054383"


def job() -> RecognitionJob:
    return RecognitionJob.submit(
        image_ref="2026/09/16/abc.jpg", submitted_by="gate-1", submitted_at=AT
    )


def candidate(
    value: str = VALID,
    *,
    valid: bool = True,
    repaired: bool = False,
    confidence: float = 0.95,
) -> ContainerCodeCandidate:
    return ContainerCodeCandidate(
        raw_text=value,
        value=value,
        confidence=Confidence(confidence),
        check_digit_valid=valid,
        expected_check_digit=3,
        repaired=repaired,
    )


def fragments() -> list[TextFragment]:
    return [TextFragment(text=VALID, confidence=Confidence(0.95))]


# --------------------------------------------------------------------------- #
# Submitting                                                                   #
# --------------------------------------------------------------------------- #
def test_a_submitted_job_starts_pending_and_announces_itself() -> None:
    recognition = job()

    assert recognition.status is JobStatus.PENDING
    assert recognition.is_finished is False
    assert recognition.best_candidate is None

    events = recognition.pull_events()
    assert len(events) == 1
    assert isinstance(events[0], RecognitionRequested)
    assert events[0].image_ref == "2026/09/16/abc.jpg"


def test_a_job_cannot_exist_without_a_stored_image() -> None:
    with pytest.raises(BusinessRuleViolation) as excinfo:
        RecognitionJob.submit(image_ref="   ")
    assert excinfo.value.rule == "recognition_needs_an_image"


# --------------------------------------------------------------------------- #
# The three ways a job ends                                                    #
# --------------------------------------------------------------------------- #
def test_a_trustworthy_reading_completes_the_job() -> None:
    recognition = job()
    recognition.start()
    recognition.pull_events()

    recognition.complete(fragments(), [candidate()])

    assert recognition.status is JobStatus.COMPLETED
    assert recognition.is_conclusive is True
    assert recognition.best_candidate.value == VALID

    event = recognition.pull_events()[0]
    assert isinstance(event, RecognitionCompleted)
    assert event.container_number == VALID
    assert event.conclusive is True
    assert event.check_digit_valid is True


def test_a_failing_check_digit_sends_the_job_to_review() -> None:
    recognition = job()
    recognition.start()
    recognition.pull_events()

    recognition.complete(fragments(), [candidate(valid=False)])

    assert recognition.status is JobStatus.NEEDS_REVIEW
    assert recognition.is_conclusive is False
    assert recognition.pull_events()[0].conclusive is False


def test_a_repaired_reading_also_goes_to_review() -> None:
    """Repaired means "a guess that checks out" - a person still confirms."""
    recognition = job()
    recognition.start()

    recognition.complete(fragments(), [candidate(repaired=True)])

    assert recognition.status is JobStatus.NEEDS_REVIEW


def test_reading_nothing_is_review_not_failure() -> None:
    """An unreadable photo is an ordinary outcome, not an error."""
    recognition = job()
    recognition.start()
    recognition.pull_events()

    recognition.complete([], [])

    assert recognition.status is JobStatus.NEEDS_REVIEW
    assert recognition.best_candidate is None
    event = recognition.pull_events()[0]
    assert event.container_number is None
    assert event.conclusive is False


def test_a_broken_engine_fails_the_job() -> None:
    recognition = job()
    recognition.start()
    recognition.pull_events()

    recognition.fail("paddleocr failed: out of memory")

    assert recognition.status is JobStatus.FAILED
    assert recognition.is_finished is True
    assert "out of memory" in recognition.failure_reason

    event = recognition.pull_events()[0]
    assert isinstance(event, RecognitionFailed)


# --------------------------------------------------------------------------- #
# Transitions                                                                  #
# --------------------------------------------------------------------------- #
def test_starting_twice_is_harmless() -> None:
    recognition = job()
    recognition.start()
    recognition.start()
    assert recognition.status is JobStatus.PROCESSING


@pytest.mark.parametrize("finish", ["complete", "fail"])
def test_a_finished_job_cannot_be_reopened(finish: str) -> None:
    recognition = job()
    recognition.start()
    if finish == "complete":
        recognition.complete(fragments(), [candidate()])
    else:
        recognition.fail("boom")

    for action in (
        lambda: recognition.start(),
        lambda: recognition.complete(fragments(), [candidate()]),
        lambda: recognition.fail("again"),
    ):
        with pytest.raises(BusinessRuleViolation) as excinfo:
            action()
        assert excinfo.value.rule == "recognition_job_already_finished"


def test_completion_records_the_timestamp_and_everything_read() -> None:
    recognition = job()
    recognition.start()

    recognition.complete(fragments(), [candidate(), candidate("MSCU1234566")])

    assert recognition.completed_at is not None
    assert len(recognition.candidates) == 2
    assert len(recognition.fragments) == 1


def test_a_job_is_identified_by_its_id() -> None:
    first = job()
    assert first == RecognitionJob(
        job_id=first.id, image_ref="other.jpg", submitted_at=AT
    )
