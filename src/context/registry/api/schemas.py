"""Pydantic schemas - the only place Pydantic appears in the registry.

Responses are built from the application layer's plain dataclass views with
``from_attributes``, so the wire format can change without the use cases
noticing. The condition enums are reused from the domain rather than
redeclared: one source of truth, and OpenAPI documents the real options.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.context.registry.domain import (
    Cleanliness,
    IdentificationSource,
    StructuralState,
)


# --------------------------------------------------------------------------- #
# Requests                                                                     #
# --------------------------------------------------------------------------- #
class RegisterContainerRequest(BaseModel):
    container_number: str = Field(
        description="ISO 6346 number. Spaces, dashes and lower case are tolerated.",
        examples=["CSQU3054383", "csqu 305438 3"],
    )
    size_type_code: str = Field(
        description="ISO 6346 size-type code. 45G1 is a 40ft high cube; L5G1 is a 45ft.",
        examples=["22G1", "45R1", "L5G1"],
    )
    cleanliness: Cleanliness
    structural: StructuralState
    food_certified: bool = Field(
        default=False,
        description="Whether a food-grade certificate was presented at inspection.",
    )
    source: IdentificationSource = IdentificationSource.OCR
    inspected_by: str | None = Field(
        default=None,
        description="Name the capture; when given, it is recorded as the first inspection.",
    )
    notes: str | None = None
    evidence_image_ref: str | None = None


class RecordInspectionRequest(BaseModel):
    inspected_by: str = Field(min_length=1)
    cleanliness: Cleanliness
    structural: StructuralState
    food_certified: bool = False
    notes: str | None = None
    evidence_image_ref: str | None = None
    inspected_at: datetime | None = Field(
        default=None,
        description="Defaults to now. A value without an offset is read as UTC.",
    )

    @field_validator("inspected_at")
    @classmethod
    def _assume_utc(cls, value: datetime | None) -> datetime | None:
        """Storage refuses naive timestamps, so settle the timezone here."""
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class AmendContainerRequest(BaseModel):
    size_type_code: str = Field(examples=["L5G1"])


class ValidateContainerNumberRequest(BaseModel):
    container_number: str = Field(
        description="Raw OCR text to check before anything is stored.",
        examples=["CSQU3054383"],
    )


# --------------------------------------------------------------------------- #
# Responses                                                                    #
# --------------------------------------------------------------------------- #
class ContainerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    number: str
    formatted_number: str
    owner_code: str
    equipment_category: str
    serial_number: str
    check_digit: int

    size_type_code: str
    size_label: str
    length_ft: int
    height_mm: int
    is_high_cube: bool
    container_type: str

    cleanliness: str
    structural: str
    cargo_grade: str
    is_available_for_loading: bool

    identified_at: datetime
    identified_by: str
    inspection_count: int
    last_inspected_at: datetime | None


class InspectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    inspected_at: datetime
    inspected_by: str
    cleanliness: str
    structural: str
    cargo_grade: str
    notes: str | None
    evidence_image_ref: str | None


class ContainerDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    container: ContainerResponse
    inspections: list[InspectionResponse]


class ContainerNumberValidationResponse(BaseModel):
    """Lets the capture screen check a read before committing to it."""

    input: str
    is_valid: bool
    number: str | None = None
    formatted_number: str | None = None
    owner_code: str | None = None
    equipment_category: str | None = None
    serial_number: str | None = None
    check_digit: int | None = None
    expected_check_digit: int | None = Field(
        default=None,
        description=(
            "What the check digit should be for the first ten characters. "
            "When this differs from the digit that was read, OCR most likely "
            "misread the last character."
        ),
    )
    error: str | None = None


class ErrorResponse(BaseModel):
    code: str
    detail: str
    rule: str | None = None
