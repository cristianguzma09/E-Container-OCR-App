"""Pydantic schemas for the recognition endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    value: str = Field(description="The 11-character number as interpreted.")
    raw_text: str = Field(description="What the engine actually returned.")
    confidence: float
    score: float = Field(
        description="Ranking score. A valid check digit always outranks an invalid one."
    )
    check_digit_valid: bool
    expected_check_digit: int | None
    repaired: bool = Field(
        description="A confusable character was substituted to satisfy the check digit."
    )
    needs_human_confirmation: bool


class FragmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    text: str
    confidence: float


class RecognitionJobResponse(BaseModel):
    """The capture screen polls this until ``status`` leaves PENDING/PROCESSING.

    ``container_number`` is populated only when the job is conclusive. If it
    is null but ``candidates`` is not empty, something was read that a person
    has to confirm - which is exactly the case a client must not silently
    treat as an answer.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    image_ref: str
    submitted_at: datetime
    submitted_by: str | None
    completed_at: datetime | None
    failure_reason: str | None

    container_number: str | None
    confidence: float | None
    check_digit_valid: bool | None
    repaired: bool | None
    needs_review: bool

    candidates: list[CandidateResponse]
    fragments: list[FragmentResponse]
