"""Run OCR over a queued image and interpret the result."""

from __future__ import annotations

import logging

from src.context.recognition.application.dto import (
    ProcessJobCommand,
    RecognitionJobView,
)
from src.context.recognition.application.errors import RecognitionJobNotFound
from src.context.recognition.application.unit_of_work import RecognitionUnitOfWork
from src.context.recognition.domain import (
    ContainerCodeExtractor,
    ImageStore,
    OcrEngine,
    OcrEngineFailure,
)
from src.shared_kernel.application import EventDispatcher, UseCase

logger = logging.getLogger(__name__)


class ProcessRecognitionJob(UseCase[ProcessJobCommand, RecognitionJobView]):
    """Read the image, rank the candidates, and close the job.

    The engine runs *between* two short transactions rather than inside one.
    A Paddle inference takes seconds; holding a database transaction open for
    that long would tie up a connection and lock the row for no benefit.

    Re-running a finished job is a no-op rather than an error, so a retried
    background task cannot overwrite a result an operator has already acted
    on.
    """

    def __init__(
        self,
        uow: RecognitionUnitOfWork,
        image_store: ImageStore,
        engine: OcrEngine,
        *,
        extractor: ContainerCodeExtractor | None = None,
        events: EventDispatcher | None = None,
    ) -> None:
        self._uow = uow
        self._images = image_store
        self._engine = engine
        self._extractor = extractor or ContainerCodeExtractor()
        self._events = events or EventDispatcher()

    def execute(self, request: ProcessJobCommand) -> RecognitionJobView:
        with self._uow as uow:
            job = uow.jobs.get(request.job_id)
            if job is None:
                raise RecognitionJobNotFound(request.job_id)
            if job.is_finished:
                return RecognitionJobView.of(job)

            job.start()
            uow.jobs.save(job)
            uow.commit()

        # Outside the transaction on purpose - this is the slow part.
        try:
            image = self._images.load(job.image_ref)
            fragments = self._engine.read_text(image)
            candidates = self._extractor.extract(fragments)
        except OcrEngineFailure as error:
            logger.warning("job %s: engine failed: %s", job.id, error)
            job.fail(str(error))
        except Exception as error:  # noqa: BLE001 - a job must always settle
            logger.exception("job %s: unexpected failure", job.id)
            job.fail(f"{type(error).__name__}: {error}")
        else:
            job.complete(fragments, candidates)

        with self._uow as uow:
            uow.jobs.save(job)
            uow.commit()

        self._events.dispatch(job.pull_events())
        return RecognitionJobView.of(job)
