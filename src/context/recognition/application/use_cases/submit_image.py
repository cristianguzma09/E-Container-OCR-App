"""Accept a captured image and queue it for reading."""

from __future__ import annotations

from src.context.recognition.application.dto import (
    RecognitionJobView,
    SubmitImageCommand,
)
from src.context.recognition.application.unit_of_work import RecognitionUnitOfWork
from src.context.recognition.domain import ImageStore, InvalidImage, RecognitionJob
from src.shared_kernel.application import EventDispatcher, UseCase

#: Formats a phone or gate camera actually produces.
ALLOWED_CONTENT_TYPES = frozenset(
    {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/bmp"}
)

#: Generous enough for a 12 MP photo, small enough to reject a video upload.
MAX_IMAGE_BYTES = 15 * 1024 * 1024


class SubmitImageForRecognition(UseCase[SubmitImageCommand, RecognitionJobView]):
    """Store the image, open a job, and return immediately.

    Reading the image is deliberately *not* done here. OCR takes seconds, and
    a gate camera cannot wait on it, so this use case does only what must
    happen before the caller gets an answer: keep the bytes and record that a
    job exists.
    """

    def __init__(
        self,
        uow: RecognitionUnitOfWork,
        image_store: ImageStore,
        *,
        events: EventDispatcher | None = None,
    ) -> None:
        self._uow = uow
        self._images = image_store
        self._events = events or EventDispatcher()

    def execute(self, request: SubmitImageCommand) -> RecognitionJobView:
        self._validate(request)

        reference = self._images.save(
            request.image, content_type=request.content_type
        )
        job = RecognitionJob.submit(
            image_ref=reference, submitted_by=request.submitted_by
        )

        with self._uow as uow:
            uow.jobs.save(job)
            uow.commit()

        self._events.dispatch(job.pull_events())
        return RecognitionJobView.of(job)

    @staticmethod
    def _validate(request: SubmitImageCommand) -> None:
        if not request.image:
            raise InvalidImage("the upload is empty")
        if len(request.image) > MAX_IMAGE_BYTES:
            raise InvalidImage(
                f"the image is larger than {MAX_IMAGE_BYTES // (1024 * 1024)} MB"
            )
        content_type = (request.content_type or "").split(";")[0].strip().lower()
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise InvalidImage(
                f"'{request.content_type}' is not a supported image type"
            )
