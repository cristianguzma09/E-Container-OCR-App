"""Custom column types."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


class UtcDateTime(TypeDecorator[datetime]):
    """A timestamp that is always timezone-aware UTC, on every backend.

    Postgres keeps the offset; SQLite does not, so a value written as aware
    comes back naive and comparisons silently break. This normalises in both
    directions, which also means tests can run on in-memory SQLite and still
    prove the same behaviour the production database gives.

    Writing a naive datetime is refused rather than guessed at.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(
                "refusing to store a naive datetime; attach a timezone first"
            )
        return value.astimezone(UTC)

    def process_result_value(
        self, value: Any, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
