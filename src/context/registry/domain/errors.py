"""Domain errors specific to the container registry."""

from __future__ import annotations

from src.shared_kernel.domain import DomainError


class InvalidContainerNumber(DomainError):
    """The string is not a well-formed ISO 6346 container number."""

    def __init__(self, raw: str, reason: str) -> None:
        self.raw = raw
        self.reason = reason
        super().__init__(f"'{raw}' is not a valid ISO 6346 container number: {reason}")


class InvalidSizeTypeCode(DomainError):
    """The string is not a recognised ISO 6346 size-type code."""

    def __init__(self, raw: str, reason: str) -> None:
        self.raw = raw
        self.reason = reason
        super().__init__(f"'{raw}' is not a valid ISO 6346 size-type code: {reason}")
