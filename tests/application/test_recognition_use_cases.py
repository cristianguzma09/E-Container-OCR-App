"""Use case tests for the recognition context."""

from __future__ import annotations

import pytest

from src.context.recognition.application import (
    GetRecognitionResult,
    JobListQuery,
    JobQuery,
    ListRecognitionJobs,
    ProcessJobCommand,
    ProcessRecognitionJob,
    RecognitionJobNotFound,
    SubmitImageCommand,
    SubmitImageForRecognition,
)
from src.context.recognition.domain import (
    InvalidImage,
    JobStatus,
    RecognitionCompleted,
    RecognitionFailed,
    RecognitionRequested,
)
from src.context.recognition.infrastructure.ocr.stub_engine import StubOcrEngine
from tests.application.fakes import RecordingEventDispatcher
from tests.application.recognition_fakes import (
    FakeRecognitionUnitOfWork,
    InMemoryImageStore,
)

VALID = "CSQU3054383"
IMAGE = b"\xff\xd8\xff\xe0 fake jpeg bytes"


@pytest.fixture
def uow() -> FakeRecognitionUnitOfWork:
    return FakeRecognitionUnitOfWork()


@pytest.fixture
def images() -> InMemoryImageStore:
    return InMemoryImageStore()


@pytest.fixture
def events() -> RecordingEventDispatcher:
    return RecordingEventDispatcher()


def submit(
    uow: FakeRecognitionUnitOfWork,
    images: InMemoryImageStore,
    events: RecordingEventDispatcher | None = None,
    **overrides: object,
):
    command = SubmitImageCommand(
        **{
            "image": IMAGE,
            "content_type": "image/jpeg",
            "submitted_by": "gate-1",
            **overrides,
        }  # type: ignore[arg-type]
    )
    return SubmitImageForRecognition(uow, images, events=events).execute(command)


# --------------------------------------------------------------------------- #
# Submitting                                                                   #
# --------------------------------------------------------------------------- #
def test_submitting_stores_the_image_and_opens_a_pending_job(
    uow: FakeRecognitionUnitOfWork,
    images: InMemoryImageStore,
    events: RecordingEventDispatcher,
) -> None:
    view = submit(uow, images, events)

    assert view.status == "PENDING"
    assert view.container_number is None
    assert view.needs_review is False
    assert images.saved[view.image_ref] == IMAGE
    assert uow.committed is True
    assert len(events.of_type(RecognitionRequested)) == 1


def test_submitting_does_not_run_the_engine(
    uow: FakeRecognitionUnitOfWork, images: InMemoryImageStore
) -> None:
    """The upload must return before any inference happens."""
    engine = StubOcrEngine.reading(VALID)
    submit(uow, images)
    assert engine.calls == 0


@pytest.mark.parametrize(
    ("overrides", "why"),
    [
        ({"image": b""}, "empty upload"),
        ({"content_type": "application/pdf"}, "not an image"),
        ({"content_type": ""}, "no content type"),
        ({"image": b"x" * (16 * 1024 * 1024)}, "too large"),
    ],
)
def test_an_unusable_upload_is_refused(
    uow: FakeRecognitionUnitOfWork,
    images: InMemoryImageStore,
    overrides: dict[str, object],
    why: str,
) -> None:
    with pytest.raises(InvalidImage):
        submit(uow, images, **overrides)

    assert images.saved == {}
    assert uow.stored == {}


def test_a_content_type_with_parameters_is_accepted(
    uow: FakeRecognitionUnitOfWork, images: InMemoryImageStore
) -> None:
    view = submit(uow, images, content_type="image/jpeg; charset=binary")
    assert view.status == "PENDING"


# --------------------------------------------------------------------------- #
# Processing                                                                   #
# --------------------------------------------------------------------------- #
def process(uow, images, engine, events=None):
    submitted = submit(uow, images)
    return ProcessRecognitionJob(uow, images, engine, events=events).execute(
        ProcessJobCommand(job_id=submitted.id)
    )


def test_a_clean_read_completes_the_job(
    uow: FakeRecognitionUnitOfWork,
    images: InMemoryImageStore,
    events: RecordingEventDispatcher,
) -> None:
    view = process(uow, images, StubOcrEngine.reading("MAERSK", VALID, "22G1"), events)

    assert view.status == "COMPLETED"
    assert view.container_number == VALID
    assert view.check_digit_valid is True
    assert view.repaired is False
    assert view.needs_review is False

    completed = events.of_type(RecognitionCompleted)
    assert len(completed) == 1
    assert completed[0].conclusive is True


def test_a_number_split_across_lines_is_still_read(
    uow: FakeRecognitionUnitOfWork, images: InMemoryImageStore
) -> None:
    view = process(uow, images, StubOcrEngine.reading("CSQU", "305438", "3"))
    assert view.container_number == VALID


def test_a_repaired_read_is_held_for_review(
    uow: FakeRecognitionUnitOfWork, images: InMemoryImageStore
) -> None:
    view = process(uow, images, StubOcrEngine.reading("C5QU3054383"))

    assert view.status == "NEEDS_REVIEW"
    assert view.needs_review is True
    # The reading is still offered - it is just not presented as the answer.
    assert view.container_number is None
    assert view.candidates[0].value == VALID
    assert view.candidates[0].repaired is True
    assert view.candidates[0].needs_human_confirmation is True


def test_an_unreadable_photo_needs_review_rather_than_failing(
    uow: FakeRecognitionUnitOfWork, images: InMemoryImageStore
) -> None:
    view = process(uow, images, StubOcrEngine.reading("HAMBURG SUD", "TARE 3700 KG"))

    assert view.status == "NEEDS_REVIEW"
    assert view.candidates == []
    assert view.failure_reason is None


def test_a_broken_engine_fails_the_job(
    uow: FakeRecognitionUnitOfWork,
    images: InMemoryImageStore,
    events: RecordingEventDispatcher,
) -> None:
    view = process(uow, images, StubOcrEngine(fail_with="model not found"), events)

    assert view.status == "FAILED"
    assert "model not found" in view.failure_reason
    assert len(events.of_type(RecognitionFailed)) == 1


def test_an_unexpected_crash_still_settles_the_job(
    uow: FakeRecognitionUnitOfWork, images: InMemoryImageStore
) -> None:
    """A job must never be left stuck in PROCESSING."""

    class ExplodingEngine(StubOcrEngine):
        def read_text(self, image: bytes):
            raise RuntimeError("segfault in native code")

    view = process(uow, images, ExplodingEngine())

    assert view.status == "FAILED"
    assert "RuntimeError" in view.failure_reason


def test_reprocessing_a_finished_job_is_a_no_op(
    uow: FakeRecognitionUnitOfWork, images: InMemoryImageStore
) -> None:
    """A retried background task must not overwrite a settled result."""
    submitted = submit(uow, images)
    engine = StubOcrEngine.reading(VALID)
    use_case = ProcessRecognitionJob(uow, images, engine)

    first = use_case.execute(ProcessJobCommand(job_id=submitted.id))
    second = use_case.execute(ProcessJobCommand(job_id=submitted.id))

    assert first.status == second.status == "COMPLETED"
    assert engine.calls == 1


def test_processing_an_unknown_job_is_refused(
    uow: FakeRecognitionUnitOfWork, images: InMemoryImageStore
) -> None:
    import uuid

    with pytest.raises(RecognitionJobNotFound):
        ProcessRecognitionJob(uow, images, StubOcrEngine()).execute(
            ProcessJobCommand(job_id=uuid.uuid4())
        )


def test_a_missing_image_fails_the_job_rather_than_crashing(
    uow: FakeRecognitionUnitOfWork, images: InMemoryImageStore
) -> None:
    submitted = submit(uow, images)
    images.saved.clear()

    view = ProcessRecognitionJob(uow, images, StubOcrEngine.reading(VALID)).execute(
        ProcessJobCommand(job_id=submitted.id)
    )

    assert view.status == "FAILED"
    assert "missing" in view.failure_reason


# --------------------------------------------------------------------------- #
# Queries                                                                      #
# --------------------------------------------------------------------------- #
def test_polling_a_job(
    uow: FakeRecognitionUnitOfWork, images: InMemoryImageStore
) -> None:
    submitted = submit(uow, images)

    view = GetRecognitionResult(uow).execute(JobQuery(job_id=submitted.id))

    assert view.id == submitted.id
    assert view.status == "PENDING"


def test_polling_an_unknown_job_is_refused(uow: FakeRecognitionUnitOfWork) -> None:
    import uuid

    with pytest.raises(RecognitionJobNotFound):
        GetRecognitionResult(uow).execute(JobQuery(job_id=uuid.uuid4()))


def test_the_review_queue_filters_by_status(
    uow: FakeRecognitionUnitOfWork, images: InMemoryImageStore
) -> None:
    process(uow, images, StubOcrEngine.reading(VALID))
    process(uow, images, StubOcrEngine.reading("C5QU3054383"))
    process(uow, images, StubOcrEngine.reading("nothing legible here"))

    queue = ListRecognitionJobs(uow).execute(
        JobListQuery(status=JobStatus.NEEDS_REVIEW)
    )
    done = ListRecognitionJobs(uow).execute(JobListQuery(status=JobStatus.COMPLETED))
    everything = ListRecognitionJobs(uow).execute(JobListQuery())

    assert len(queue) == 2
    assert len(done) == 1
    assert len(everything) == 3
