"""record operator confirmation on recognition jobs

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "recognition_jobs",
        sa.Column("confirmed_container_number", sa.String(length=11), nullable=True),
    )
    op.add_column(
        "recognition_jobs",
        sa.Column("confirmed_by", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "recognition_jobs",
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_recognition_jobs_confirmed_container_number",
        "recognition_jobs",
        ["confirmed_container_number"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_recognition_jobs_confirmed_container_number",
        table_name="recognition_jobs",
    )
    op.drop_column("recognition_jobs", "confirmed_at")
    op.drop_column("recognition_jobs", "confirmed_by")
    op.drop_column("recognition_jobs", "confirmed_container_number")
