"""SQLAlchemy table for recognition jobs.

Fragments and candidates are stored as JSON rather than as child tables: they
are an immutable snapshot of one engine run, never queried field by field and
never edited. Giving them tables would buy nothing and cost two joins.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.context.registry.infrastructure.persistence.types import UtcDateTime
from src.platform.database import Base


class RecognitionJobModel(Base):
    __tablename__ = "recognition_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    image_ref: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(16), index=True)

    submitted_at: Mapped[datetime] = mapped_column(UtcDateTime, index=True)
    submitted_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Denormalised from the best candidate so the review queue can be filtered
    # and searched without unpacking JSON on every row.
    best_container_number: Mapped[str | None] = mapped_column(
        String(11), nullable=True, index=True
    )
    best_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    fragments: Mapped[list[Any]] = mapped_column(JSON, default=list)
    candidates: Mapped[list[Any]] = mapped_column(JSON, default=list)
