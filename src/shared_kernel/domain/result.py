"""A lightweight success/failure wrapper for expected outcomes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Result[T]:
    """Explicit success or failure without raising.

    Use in the application layer for outcomes that are expected and meaningful
    to the caller (e.g. OCR returned a code whose check digit does not match).
    Keep exceptions for genuinely exceptional situations.
    """

    _value: T | None
    _error: str | None
    is_success: bool

    @classmethod
    def ok(cls, value: T) -> Result[T]:
        return cls(_value=value, _error=None, is_success=True)

    @classmethod
    def fail(cls, error: str) -> Result[T]:
        return cls(_value=None, _error=error, is_success=False)

    @property
    def is_failure(self) -> bool:
        return not self.is_success

    def unwrap(self) -> T:
        if self.is_failure:
            raise ValueError(f"unwrap() on a failed Result: {self._error}")
        return self._value  # type: ignore[return-value]

    @property
    def error(self) -> str:
        if self.is_success:
            raise ValueError("error accessed on a successful Result")
        return self._error  # type: ignore[return-value]
