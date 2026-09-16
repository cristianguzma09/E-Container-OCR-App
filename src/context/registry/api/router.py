"""HTTP endpoints for the container registry."""

from __future__ import annotations

import re

from fastapi import APIRouter, Query, status

from src.context.registry.api.dependencies import EventsDep, PolicyDep, UnitOfWorkDep
from src.context.registry.api.schemas import (
    AmendContainerRequest,
    ContainerDetailResponse,
    ContainerNumberValidationResponse,
    ContainerResponse,
    ErrorResponse,
    InspectionResponse,
    RecordInspectionRequest,
    RegisterContainerRequest,
    ValidateContainerNumberRequest,
)
from src.context.registry.application import (
    AmendContainerDetails,
    AmendContainerDetailsCommand,
    ContainerQuery,
    GetContainer,
    GetInspectionHistory,
    InspectionHistoryQuery,
    ListContainers,
    PagedQuery,
    RecordInspection,
    RecordInspectionCommand,
    RegisterContainerCommand,
    RegisterContainerFromRecognition,
)
from src.context.registry.domain import (
    ContainerNumber,
    InvalidContainerNumber,
    calculate_check_digit,
)

router = APIRouter(prefix="/api/v1", tags=["registry"])

NOT_FOUND = {404: {"model": ErrorResponse, "description": "Container not registered"}}
CONFLICT = {409: {"model": ErrorResponse, "description": "Already registered"}}
UNPROCESSABLE = {422: {"model": ErrorResponse, "description": "Rejected by the domain"}}

_SEPARATORS = re.compile(r"[\s\-_.]")
_FIRST_TEN = re.compile(r"[A-Z]{3}[UJZ]\d{6}")


# --------------------------------------------------------------------------- #
# Containers                                                                   #
# --------------------------------------------------------------------------- #
@router.post(
    "/containers",
    response_model=ContainerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a container read from a capture",
    responses={**CONFLICT, **UNPROCESSABLE},
)
def register_container(
    payload: RegisterContainerRequest,
    uow: UnitOfWorkDep,
    events: EventsDep,
    policy: PolicyDep,
) -> ContainerResponse:
    """Validate the read, grade the observed condition and store the container.

    The cargo grade is never accepted from the caller - it is derived here from
    the observations, so a dirty box cannot be filed as food grade.
    """
    view = RegisterContainerFromRecognition(
        uow, grading_policy=policy, events=events
    ).execute(
        RegisterContainerCommand(
            container_number=payload.container_number,
            size_type_code=payload.size_type_code,
            cleanliness=payload.cleanliness,
            structural=payload.structural,
            food_certified=payload.food_certified,
            source=payload.source,
            inspected_by=payload.inspected_by,
            notes=payload.notes,
            evidence_image_ref=payload.evidence_image_ref,
        )
    )
    return ContainerResponse.model_validate(view)


@router.get(
    "/containers",
    response_model=list[ContainerResponse],
    summary="Page through the register, newest first",
)
def list_containers(
    uow: UnitOfWorkDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ContainerResponse]:
    views = ListContainers(uow).execute(PagedQuery(limit=limit, offset=offset))
    return [ContainerResponse.model_validate(view) for view in views]


@router.get(
    "/containers/{number}",
    response_model=ContainerDetailResponse,
    summary="One container with its inspection history",
    responses={**NOT_FOUND, **UNPROCESSABLE},
)
def get_container(number: str, uow: UnitOfWorkDep) -> ContainerDetailResponse:
    detail = GetContainer(uow).execute(ContainerQuery(container_number=number))
    return ContainerDetailResponse.model_validate(detail)


@router.patch(
    "/containers/{number}",
    response_model=ContainerResponse,
    summary="Correct a misread size-type code",
    responses={**NOT_FOUND, **UNPROCESSABLE},
)
def amend_container(
    number: str,
    payload: AmendContainerRequest,
    uow: UnitOfWorkDep,
    events: EventsDep,
) -> ContainerResponse:
    """The number itself is never amended - it is the container's identity."""
    view = AmendContainerDetails(uow, events=events).execute(
        AmendContainerDetailsCommand(
            container_number=number, size_type_code=payload.size_type_code
        )
    )
    return ContainerResponse.model_validate(view)


# --------------------------------------------------------------------------- #
# Inspections                                                                  #
# --------------------------------------------------------------------------- #
@router.post(
    "/containers/{number}/inspections",
    response_model=ContainerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record an inspection against a container",
    responses={**NOT_FOUND, **UNPROCESSABLE},
)
def record_inspection(
    number: str,
    payload: RecordInspectionRequest,
    uow: UnitOfWorkDep,
    events: EventsDep,
    policy: PolicyDep,
) -> ContainerResponse:
    view = RecordInspection(uow, grading_policy=policy, events=events).execute(
        RecordInspectionCommand(
            container_number=number,
            inspected_by=payload.inspected_by,
            cleanliness=payload.cleanliness,
            structural=payload.structural,
            food_certified=payload.food_certified,
            notes=payload.notes,
            evidence_image_ref=payload.evidence_image_ref,
            inspected_at=payload.inspected_at,
        )
    )
    return ContainerResponse.model_validate(view)


@router.get(
    "/containers/{number}/inspections",
    response_model=list[InspectionResponse],
    summary="A container's inspection history, newest first",
    responses={**NOT_FOUND, **UNPROCESSABLE},
)
def inspection_history(
    number: str,
    uow: UnitOfWorkDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[InspectionResponse]:
    views = GetInspectionHistory(uow).execute(
        InspectionHistoryQuery(container_number=number, limit=limit, offset=offset)
    )
    return [InspectionResponse.model_validate(view) for view in views]


# --------------------------------------------------------------------------- #
# Read validation                                                              #
# --------------------------------------------------------------------------- #
@router.post(
    "/container-numbers/validate",
    response_model=ContainerNumberValidationResponse,
    summary="Check an OCR read before storing anything",
)
def validate_container_number(
    payload: ValidateContainerNumberRequest,
) -> ContainerNumberValidationResponse:
    """Parse a raw read and report what is wrong with it, without touching the DB.

    When the first ten characters are well formed the correct check digit is
    returned too, so the capture screen can point at the character OCR most
    likely got wrong instead of just rejecting the whole read.
    """
    raw = payload.container_number
    cleaned = _SEPARATORS.sub("", raw or "").upper()

    expected: int | None = None
    if len(cleaned) >= 10 and _FIRST_TEN.fullmatch(cleaned[:10]):
        expected = calculate_check_digit(cleaned[0:3], cleaned[3], cleaned[4:10])

    try:
        number = ContainerNumber.parse(raw)
    except InvalidContainerNumber as error:
        return ContainerNumberValidationResponse(
            input=raw,
            is_valid=False,
            expected_check_digit=expected,
            error=str(error),
        )

    return ContainerNumberValidationResponse(
        input=raw,
        is_valid=True,
        number=number.value,
        formatted_number=number.formatted,
        owner_code=number.owner_code,
        equipment_category=number.equipment_category,
        serial_number=number.serial_number,
        check_digit=number.check_digit,
        expected_check_digit=expected,
    )
