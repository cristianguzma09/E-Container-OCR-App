"""SQLAlchemy tables for the registry.

These are *not* the domain model. They are a storage shape, translated to and
from the aggregate by the mappers, which is why the domain never imports
SQLAlchemy and why a loaded ``Container`` keeps working after its session is
closed.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, SmallInteger, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.context.registry.infrastructure.persistence.types import UtcDateTime
from src.platform.database import Base


class ContainerModel(Base):
    __tablename__ = "containers"

    # The ISO 6346 number is the natural key - there is no surrogate id.
    number: Mapped[str] = mapped_column(String(11), primary_key=True)

    # The parts are stored alongside the whole so the register can be searched
    # by owner prefix or serial without parsing every row.
    owner_code: Mapped[str] = mapped_column(String(3), index=True)
    equipment_category: Mapped[str] = mapped_column(String(1))
    serial_number: Mapped[str] = mapped_column(String(6), index=True)
    check_digit: Mapped[int] = mapped_column(SmallInteger)

    size_type_code: Mapped[str] = mapped_column(String(4), index=True)

    cleanliness: Mapped[str] = mapped_column(String(16))
    structural: Mapped[str] = mapped_column(String(16))
    cargo_grade: Mapped[str] = mapped_column(String(32), index=True)

    identified_at: Mapped[datetime] = mapped_column(UtcDateTime, index=True)
    identified_by: Mapped[str] = mapped_column(String(16))

    inspections: Mapped[list[InspectionModel]] = relationship(
        back_populates="container",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="InspectionModel.inspected_at.desc()",
    )


class InspectionModel(Base):
    __tablename__ = "inspections"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    container_number: Mapped[str] = mapped_column(
        String(11),
        ForeignKey("containers.number", ondelete="CASCADE"),
        index=True,
    )

    cleanliness: Mapped[str] = mapped_column(String(16))
    structural: Mapped[str] = mapped_column(String(16))
    cargo_grade: Mapped[str] = mapped_column(String(32))

    inspected_at: Mapped[datetime] = mapped_column(UtcDateTime, index=True)
    inspected_by: Mapped[str] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_image_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)

    container: Mapped[ContainerModel] = relationship(back_populates="inspections")
