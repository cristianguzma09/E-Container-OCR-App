"""HTTP endpoint for confirming a capture.

Mounted on the recognition job's path because that is the resource an operator
is acting on, but kept in its own router so the recognition context's API
module never has to import the registry.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field

from src.context.recognition.api.dependencies import (
    EventsDep,
    UnitOfWorkDep as RecognitionUowDep,
)
from src.context.recognition.api.schemas import RecognitionJobResponse
from src.context.registry.api.dependencies import PolicyDep
from src.context.registry.api.dependencies import UnitOfWorkDep as RegistryUowDep
from src.context.registry.api.schemas import ContainerResponse, ErrorResponse
from src.context.registry.application import RecognitionTranslator
from src.context.registry.domain import Cleanliness, StructuralState
from src.workflows.confirm_capture import ConfirmCapture, ConfirmCaptureCommand

router = APIRouter(prefix="/api/v1/recognitions", tags=["capture"])


def get_translator() -> RecognitionTranslator:
    return RecognitionTranslator()


TranslatorDep = Annotated[RecognitionTranslator, Depends(get_translator)]


class ConfirmCaptureRequest(BaseModel):
    confirmed_by: str = Field(
        min_length=1, description="Who is signing the reading off."
    )
    size_type_code: str = Field(
        description="ISO 6346 size-type. 45G1 is a 40ft high cube; L5G1 is a 45ft.",
        examples=["22G1", "45R1", "L5G1"],
    )
    cleanliness: Cleanliness
    structural: StructuralState
    food_certified: bool = False
    container_number: str | None = Field(
        default=None,
        description=(
            "Override the engine's reading. Leave null to accept what was "
            "read; supply a number to correct it."
        ),
    )
    notes: str | None = None


class ConfirmedCaptureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job: RecognitionJobResponse
    container: ContainerResponse
    newly_registered: bool = Field(
        description="False when the container was already on the register and "
        "this capture was recorded as a further inspection."
    )
    corrected: bool = Field(
        description="True when the operator overrode what the engine read."
    )


@router.post(
    "/{job_id}/confirm",
    response_model=ConfirmedCaptureResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Sign off a reading and put the container on the register",
    responses={
        404: {"model": ErrorResponse, "description": "No such job"},
        409: {"model": ErrorResponse, "description": "Job cannot be confirmed"},
        422: {"model": ErrorResponse, "description": "Rejected by the domain"},
    },
)
def confirm_capture(
    job_id: UUID,
    payload: ConfirmCaptureRequest,
    recognition: RecognitionUowDep,
    registry: RegistryUowDep,
    policy: PolicyDep,
    events: EventsDep,
    translator: TranslatorDep,
) -> ConfirmedCaptureResponse:
    """Accept (or correct) the reading, then register or re-inspect the box.

    One call closes the loop: the job leaves the review queue as CONFIRMED and
    the container is on the register, linked to the photograph it came from.
    """
    view = ConfirmCapture(
        recognition,
        registry,
        translator=translator,
        grading_policy=policy,
        events=events,
    ).execute(
        ConfirmCaptureCommand(
            job_id=job_id,
            confirmed_by=payload.confirmed_by,
            size_type_code=payload.size_type_code,
            cleanliness=payload.cleanliness,
            structural=payload.structural,
            container_number=payload.container_number,
            food_certified=payload.food_certified,
            notes=payload.notes,
        )
    )
    return ConfirmedCaptureResponse.model_validate(view)
