"""create recognition jobs

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recognition_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("image_ref", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_by", sa.String(length=120), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        # Denormalised from the best candidate so the review queue can be
        # filtered without unpacking JSON on every row.
        sa.Column("best_container_number", sa.String(length=11), nullable=True),
        sa.Column("best_confidence", sa.Float(), nullable=True),
        sa.Column("fragments", sa.JSON(), nullable=False),
        sa.Column("candidates", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recognition_jobs_status", "recognition_jobs", ["status"])
    op.create_index(
        "ix_recognition_jobs_submitted_at", "recognition_jobs", ["submitted_at"]
    )
    op.create_index(
        "ix_recognition_jobs_best_container_number",
        "recognition_jobs",
        ["best_container_number"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_recognition_jobs_best_container_number", table_name="recognition_jobs"
    )
    op.drop_index("ix_recognition_jobs_submitted_at", table_name="recognition_jobs")
    op.drop_index("ix_recognition_jobs_status", table_name="recognition_jobs")
    op.drop_table("recognition_jobs")
