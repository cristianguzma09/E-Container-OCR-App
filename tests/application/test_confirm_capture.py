"""Tests for the cross-context confirm-capture workflow."""

from __future__ import annotations

import uuid

import pytest

from src.context.recognition.application import (
    ProcessJobCommand,
    ProcessRecognitionJob,
    RecognitionJobNotFound,
    SubmitImageCommand,
    SubmitImageForRecognition,
)
from src.context.recognition.domain import JobStatus, RecognitionConfirmed
from src.context.recognition.infrastructure.ocr.stub_engine import StubOcrEngine
from src.context.registry.domain import (
    Cleanliness,
    ContainerIdentified,
    InspectionRecorded,
    InvalidSizeTypeCode,
    StructuralState,
)
from src.workflows import (
    CaptureNotConfirmable,
    ConfirmCapture,
    ConfirmCaptureCommand,
)
from tests.application.fakes import FakeRegistryUnitOfWork, RecordingEventDispatcher
from tests.application.recognition_fakes import (
    FakeRecognitionUnitOfWork,
    InMemoryImageStore,
)

VALID = "CSQU3054383"
OTHER = "MSCU1234566"
IMAGE = b"\xff\xd8\xff\xe0 fake jpeg"


@pytest.fixture
def recognition() -> FakeRecognitionUnitOfWork:
    return FakeRecognitionUnitOfWork()


@pytest.fixture
def registry() -> FakeRegistryUnitOfWork:
    return FakeRegistryUnitOfWork()


@pytest.fixture
def images() -> InMemoryImageStore:
    return InMemoryImageStore()


@pytest.fixture
def events() -> RecordingEventDispatcher:
    return RecordingEventDispatcher()


def capture(
    recognition: FakeRecognitionUnitOfWork,
    images: InMemoryImageStore,
    *reading: str,
) -> uuid.UUID:
    """Upload and process one photo, returning the job id."""
    job = SubmitImageForRecognition(recognition, images).execute(
        SubmitImageCommand(image=IMAGE, content_type="image/jpeg")
    )
    ProcessRecognitionJob(
        recognition, images, StubOcrEngine.reading(*(reading or (VALID,)))
    ).execute(ProcessJobCommand(job_id=job.id))
    return job.id


def confirm(
    recognition, registry, events=None, **overrides
):
    workflow = ConfirmCapture(recognition, registry, events=events)
    command = ConfirmCaptureCommand(
        **{
            "confirmed_by": "J. Ramirez",
            "size_type_code": "22G1",
            "cleanliness": Cleanliness.CLEAN,
            "structural": StructuralState.SOUND,
            **overrides,
        }  # type: ignore[arg-type]
    )
    return workflow.execute(command)


# --------------------------------------------------------------------------- #
# The happy path: one call closes the loop                                     #
# --------------------------------------------------------------------------- #
def test_confirming_registers_the_container_and_closes_the_job(
    recognition, registry, images, events
) -> None:
    job_id = capture(recognition, images)

    view = confirm(recognition, registry, events, job_id=job_id)

    assert view.newly_registered is True
    assert view.corrected is False
    assert view.container.number == VALID
    assert view.container.size_type_code == "22G1"
    assert view.container.cargo_grade == "GENERAL_CARGO"
    assert view.job.status == "CONFIRMED"
    assert registry.stored[VALID].number.value == VALID


def test_confirming_publishes_events_from_both_contexts(
    recognition, registry, images, events
) -> None:
    job_id = capture(recognition, images)

    confirm(recognition, registry, events, job_id=job_id)

    assert len(events.of_type(ContainerIdentified)) == 1
    confirmed = events.of_type(RecognitionConfirmed)
    assert len(confirmed) == 1
    assert confirmed[0].container_number == VALID
    assert confirmed[0].was_corrected is False


def test_the_photograph_is_kept_as_evidence(
    recognition, registry, images
) -> None:
    job_id = capture(recognition, images)

    confirm(recognition, registry, job_id=job_id)

    container = registry.stored[VALID]
    assert container.inspections[0].evidence_image_ref is not None


def test_the_operator_is_recorded_as_the_inspector(
    recognition, registry, images
) -> None:
    job_id = capture(recognition, images)

    view = confirm(recognition, registry, job_id=job_id, confirmed_by="A. Silva")

    assert view.container.inspection_count == 1
    assert registry.stored[VALID].inspections[0].inspected_by == "A. Silva"


# --------------------------------------------------------------------------- #
# Correcting a bad read                                                        #
# --------------------------------------------------------------------------- #
def test_an_operator_can_override_what_the_engine_read(
    recognition, registry, images, events
) -> None:
    job_id = capture(recognition, images, VALID)

    view = confirm(
        recognition, registry, events, job_id=job_id, container_number=OTHER
    )

    assert view.corrected is True
    assert view.container.number == OTHER
    assert OTHER in registry.stored
    assert VALID not in registry.stored
    assert events.of_type(RecognitionConfirmed)[0].was_corrected is True


def test_a_corrected_capture_is_identified_as_manual_not_ocr(
    recognition, registry, images
) -> None:
    """A number a person typed is not an OCR identification."""
    job_id = capture(recognition, images, VALID)

    view = confirm(
        recognition, registry, job_id=job_id, container_number=OTHER
    )

    assert view.container.identified_by == "MANUAL"


def test_a_review_job_with_a_repaired_read_can_be_signed_off(
    recognition, registry, images
) -> None:
    job_id = capture(recognition, images, "C5QU3054383")
    assert recognition.stored[job_id].status is JobStatus.NEEDS_REVIEW

    view = confirm(recognition, registry, job_id=job_id)

    assert view.job.status == "CONFIRMED"
    assert view.container.number == VALID
    assert view.corrected is False  # the repair already produced this number


def test_an_unreadable_photo_can_still_be_confirmed_by_typing_the_number(
    recognition, registry, images
) -> None:
    job_id = capture(recognition, images, "HAMBURG SUD", "TARE 3700 KG")

    view = confirm(
        recognition, registry, job_id=job_id, container_number=VALID
    )

    assert view.container.number == VALID
    assert view.corrected is True


def test_an_unreadable_photo_with_no_override_cannot_be_confirmed(
    recognition, registry, images
) -> None:
    job_id = capture(recognition, images, "HAMBURG SUD")

    with pytest.raises(CaptureNotConfirmable) as excinfo:
        confirm(recognition, registry, job_id=job_id)

    assert "no container number" in str(excinfo.value)
    assert registry.stored == {}


# --------------------------------------------------------------------------- #
# A box seen more than once                                                    #
# --------------------------------------------------------------------------- #
def test_a_second_capture_of_the_same_box_is_an_inspection_not_an_error(
    recognition, registry, images, events
) -> None:
    """Containers come through the gate repeatedly. That is normal."""
    first = capture(recognition, images)
    confirm(recognition, registry, job_id=first)

    second = capture(recognition, images)
    view = confirm(
        recognition,
        registry,
        events,
        job_id=second,
        cleanliness=Cleanliness.DIRTY,
        confirmed_by="A. Silva",
    )

    assert view.newly_registered is False
    assert view.container.number == VALID
    assert view.container.cargo_grade == "NOT_SUITABLE"  # the new condition wins
    assert view.container.inspection_count == 2
    assert len(registry.stored) == 1
    assert events.of_type(InspectionRecorded)


def test_re_registering_is_never_reported_as_a_conflict(
    recognition, registry, images
) -> None:
    first = capture(recognition, images)
    confirm(recognition, registry, job_id=first)

    second = capture(recognition, images)
    view = confirm(recognition, registry, job_id=second)  # must not raise

    assert view.job.status == "CONFIRMED"


# --------------------------------------------------------------------------- #
# Guards                                                                       #
# --------------------------------------------------------------------------- #
def test_confirming_an_unknown_job(recognition, registry) -> None:
    with pytest.raises(RecognitionJobNotFound):
        confirm(recognition, registry, job_id=uuid.uuid4())


def test_a_job_still_processing_cannot_be_confirmed(
    recognition, registry, images
) -> None:
    job = SubmitImageForRecognition(recognition, images).execute(
        SubmitImageCommand(image=IMAGE, content_type="image/jpeg")
    )

    with pytest.raises(CaptureNotConfirmable) as excinfo:
        confirm(recognition, registry, job_id=job.id)

    assert "PENDING" in str(excinfo.value)


def test_a_failed_job_cannot_be_confirmed(recognition, registry, images) -> None:
    job = SubmitImageForRecognition(recognition, images).execute(
        SubmitImageCommand(image=IMAGE, content_type="image/jpeg")
    )
    ProcessRecognitionJob(
        recognition, images, StubOcrEngine(fail_with="engine died")
    ).execute(ProcessJobCommand(job_id=job.id))

    with pytest.raises(CaptureNotConfirmable):
        confirm(recognition, registry, job_id=job.id)


def test_a_job_cannot_be_confirmed_twice(recognition, registry, images) -> None:
    job_id = capture(recognition, images)
    confirm(recognition, registry, job_id=job_id)

    with pytest.raises(CaptureNotConfirmable):
        confirm(recognition, registry, job_id=job_id)


def test_an_override_that_fails_its_check_digit_is_refused(
    recognition, registry, images
) -> None:
    job_id = capture(recognition, images)

    with pytest.raises(CaptureNotConfirmable) as excinfo:
        confirm(
            recognition, registry, job_id=job_id, container_number="CSQU3054384"
        )

    assert "check digit" in str(excinfo.value)
    assert registry.stored == {}
    assert recognition.stored[job_id].status is not JobStatus.CONFIRMED


def test_an_unknown_size_type_is_refused(recognition, registry, images) -> None:
    job_id = capture(recognition, images)

    with pytest.raises((CaptureNotConfirmable, InvalidSizeTypeCode)):
        confirm(recognition, registry, job_id=job_id, size_type_code="ZZZZ")

    assert registry.stored == {}


def test_a_low_confidence_read_is_still_confirmable_by_a_person(
    recognition, registry, images
) -> None:
    """The translator's confidence gate is for unattended reads only.

    Once an operator puts their name to a number, a shaky engine score is no
    longer the authority - but the check digit still is.
    """
    job = SubmitImageForRecognition(recognition, images).execute(
        SubmitImageCommand(image=IMAGE, content_type="image/jpeg")
    )
    ProcessRecognitionJob(
        recognition, images, StubOcrEngine.reading(VALID, confidence=0.35)
    ).execute(ProcessJobCommand(job_id=job.id))

    view = confirm(recognition, registry, job_id=job.id)

    assert view.container.number == VALID
