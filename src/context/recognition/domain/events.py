"""Facts the recognition context publishes.

Payloads carry primitives so the Registry - or anything else that subscribes -
never has to import this context's model.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from src.shared_kernel.domain import DomainEvent


@dataclass(frozen=True, kw_only=True)
class RecognitionRequested(DomainEvent):
    """An image was accepted and queued for reading."""

    job_id: uuid.UUID
    image_ref: str


@dataclass(frozen=True, kw_only=True)
class RecognitionCompleted(DomainEvent):
    """The engine finished. ``conclusive`` is false when a human must look."""

    job_id: uuid.UUID
    image_ref: str
    container_number: str | None
    confidence: float
    check_digit_valid: bool
    repaired: bool
    conclusive: bool


@dataclass(frozen=True, kw_only=True)
class RecognitionFailed(DomainEvent):
    """The engine broke. Distinct from reading nothing useful."""

    job_id: uuid.UUID
    image_ref: str
    reason: str
