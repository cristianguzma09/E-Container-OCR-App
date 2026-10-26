"""Unit tests for signing off a recognition job."""

from __future__ import annotations

import pytest

from src.context.recognition.domain import (
    Confidence,
    ContainerCodeCandidate,
    JobStatus,
    RecognitionConfirmed,
    RecognitionJob,
)
from src.shared_kernel.domain import BusinessRuleViolation

VALID = "CSQU3054383"
OTHER = "MSCU1234566"


def candidate(value: str = VALID, *, valid: bool = True, repaired: bool = False):
    return ContainerCodeCandidate(
        raw_text=value,
        value=value,
        confidence=Confidence(0.95),
        check_digit_valid=valid,
        expected_check_digit=3,
        repaired=repaired,
    )


def job(status: str = "completed") -> RecognitionJob:
    recognition = RecognitionJob.submit(image_ref="2026/10/26/a.jpg")
    recognition.start()
    if status == "completed":
        recognition.complete([], [candidate()])
    elif status == "review":
        recognition.complete([], [candidate(repaired=True)])
    elif status == "empty":
        recognition.complete([], [])
    elif status == "failed":
        recognition.fail("engine died")
    recognition.pull_events()
    return recognition


# --------------------------------------------------------------------------- #
# Accepting a reading                                                          #
# --------------------------------------------------------------------------- #
def test_confirming_a_clean_read() -> None:
    recognition = job()

    recognition.confirm(VALID, confirmed_by="J. Ramirez")

    assert recognition.status is JobStatus.CONFIRMED
    assert recognition.is_confirmed is True
    assert recognition.confirmed_container_number == VALID
    assert recognition.confirmed_by == "J. Ramirez"
    assert recognition.confirmed_at is not None


def test_confirming_publishes_the_event() -> None:
    recognition = job()

    recognition.confirm(VALID, confirmed_by="J. Ramirez")
    event = recognition.pull_events()[0]

    assert isinstance(event, RecognitionConfirmed)
    assert event.container_number == VALID
    assert event.confirmed_by == "J. Ramirez"
    assert event.was_corrected is False
    assert event.was_read == VALID


def test_a_job_in_review_can_be_confirmed() -> None:
    """That is the whole purpose of the review queue."""
    recognition = job("review")
    assert recognition.status is JobStatus.NEEDS_REVIEW

    recognition.confirm(VALID, confirmed_by="J. Ramirez")

    assert recognition.status is JobStatus.CONFIRMED


def test_an_operator_can_confirm_a_job_that_read_nothing() -> None:
    """A photo OCR could not read is still a container the operator can type in."""
    recognition = job("empty")

    recognition.confirm(OTHER, confirmed_by="J. Ramirez")

    assert recognition.confirmed_container_number == OTHER
    event = recognition.pull_events()[0]
    assert event.was_read is None
    assert event.was_corrected is True


# --------------------------------------------------------------------------- #
# Corrections                                                                  #
# --------------------------------------------------------------------------- #
def test_overriding_the_reading_is_flagged_as_a_correction() -> None:
    """The override rate is the honest measure of how well OCR is doing."""
    recognition = job()

    recognition.confirm(OTHER, confirmed_by="J. Ramirez")
    event = recognition.pull_events()[0]

    assert event.was_read == VALID
    assert event.container_number == OTHER
    assert event.was_corrected is True


def test_the_confirmed_number_is_normalised() -> None:
    recognition = job()
    recognition.confirm("  csqu3054383 ", confirmed_by="J. Ramirez")
    assert recognition.confirmed_container_number == VALID


# --------------------------------------------------------------------------- #
# Guards                                                                       #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("state", ["pending", "processing", "failed"])
def test_a_job_with_no_reading_cannot_be_confirmed(state: str) -> None:
    recognition = RecognitionJob.submit(image_ref="a.jpg")
    if state == "processing":
        recognition.start()
    elif state == "failed":
        recognition.start()
        recognition.fail("engine died")

    assert recognition.can_be_confirmed is False
    with pytest.raises(BusinessRuleViolation) as excinfo:
        recognition.confirm(VALID, confirmed_by="J. Ramirez")
    assert excinfo.value.rule == "recognition_job_not_confirmable"


def test_a_job_cannot_be_confirmed_twice() -> None:
    recognition = job()
    recognition.confirm(VALID, confirmed_by="J. Ramirez")

    with pytest.raises(BusinessRuleViolation) as excinfo:
        recognition.confirm(OTHER, confirmed_by="someone else")
    assert excinfo.value.rule == "recognition_job_not_confirmable"
    assert recognition.confirmed_container_number == VALID


def test_a_confirmation_must_name_a_number() -> None:
    with pytest.raises(BusinessRuleViolation) as excinfo:
        job().confirm("   ", confirmed_by="J. Ramirez")
    assert excinfo.value.rule == "confirmation_needs_a_number"


def test_a_confirmation_must_name_an_operator() -> None:
    with pytest.raises(BusinessRuleViolation) as excinfo:
        job().confirm(VALID, confirmed_by="  ")
    assert excinfo.value.rule == "confirmation_needs_an_operator"


def test_a_confirmed_job_accepts_no_further_engine_work() -> None:
    recognition = job()
    recognition.confirm(VALID, confirmed_by="J. Ramirez")

    for action in (
        lambda: recognition.start(),
        lambda: recognition.complete([], [candidate()]),
        lambda: recognition.fail("late failure"),
    ):
        with pytest.raises(BusinessRuleViolation) as excinfo:
            action()
        assert excinfo.value.rule == "recognition_job_already_finished"
