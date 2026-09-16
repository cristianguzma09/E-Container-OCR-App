"""HTTP endpoints for OCR capture."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, File, Form, Query, UploadFile, status

from src.context.recognition.api.dependencies import (
    EventsDep,
    ImageStoreDep,
    OcrEngineDep,
    UnitOfWorkDep,
)
from src.context.recognition.api.schemas import RecognitionJobResponse
from src.context.recognition.application import (
    GetRecognitionResult,
    JobListQuery,
    JobQuery,
    ListRecognitionJobs,
    ProcessJobCommand,
    ProcessRecognitionJob,
    RecognitionUnitOfWork,
    SubmitImageCommand,
    SubmitImageForRecognition,
)
from src.context.recognition.domain import ImageStore, JobStatus, OcrEngine
from src.context.registry.api.schemas import ErrorResponse
from src.shared_kernel.application import EventDispatcher

router = APIRouter(prefix="/api/v1/recognitions", tags=["recognition"])

NOT_FOUND = {404: {"model": ErrorResponse, "description": "No such job"}}
UNPROCESSABLE = {422: {"model": ErrorResponse, "description": "Unusable upload"}}


def _process_in_background(
    job_id: UUID,
    uow: RecognitionUnitOfWork,
    images: ImageStore,
    engine: OcrEngine,
    events: EventDispatcher,
) -> None:
    """Run the engine after the response has gone out."""
    ProcessRecognitionJob(uow, images, engine, events=events).execute(
        ProcessJobCommand(job_id=job_id)
    )


@router.post(
    "",
    response_model=RecognitionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a container photograph for reading",
    responses={**UNPROCESSABLE},
)
async def submit_capture(
    background: BackgroundTasks,
    uow: UnitOfWorkDep,
    images: ImageStoreDep,
    engine: OcrEngineDep,
    events: EventsDep,
    image: UploadFile = File(description="A photograph of the container marking."),
    submitted_by: str | None = Form(default=None),
) -> RecognitionJobResponse:
    """Accept the image and return a job straight away.

    The response is ``202 Accepted`` with a ``PENDING`` job, not the reading
    itself: an inference takes seconds and a gate camera cannot block on it.
    Poll ``GET /api/v1/recognitions/{job_id}`` for the result.
    """
    payload = await image.read()
    view = SubmitImageForRecognition(uow, images, events=events).execute(
        SubmitImageCommand(
            image=payload,
            content_type=image.content_type or "",
            submitted_by=submitted_by,
        )
    )

    background.add_task(
        _process_in_background, view.id, uow, images, engine, events
    )
    return RecognitionJobResponse.model_validate(view)


@router.get(
    "/{job_id}",
    response_model=RecognitionJobResponse,
    summary="Poll a recognition job",
    responses={**NOT_FOUND},
)
def get_recognition(job_id: UUID, uow: UnitOfWorkDep) -> RecognitionJobResponse:
    view = GetRecognitionResult(uow).execute(JobQuery(job_id=job_id))
    return RecognitionJobResponse.model_validate(view)


@router.get(
    "",
    response_model=list[RecognitionJobResponse],
    summary="Page through jobs; filter by NEEDS_REVIEW for the review queue",
)
def list_recognitions(
    uow: UnitOfWorkDep,
    job_status: JobStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[RecognitionJobResponse]:
    views = ListRecognitionJobs(uow).execute(
        JobListQuery(status=job_status, limit=limit, offset=offset)
    )
    return [RecognitionJobResponse.model_validate(view) for view in views]
