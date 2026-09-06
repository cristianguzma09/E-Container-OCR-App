"""Base domain exceptions.

The API layer maps :class:`DomainError` (and subclasses) to ``4xx`` responses;
anything else is a real bug and becomes a ``500``.
"""

from __future__ import annotations


class DomainError(Exception):
    """A domain invariant or business rule would be broken.

    Raised by value objects, entities and domain services.
    """


class BusinessRuleViolation(DomainError):
    """A named business rule was violated."""

    def __init__(self, rule: str, message: str) -> None:
        self.rule = rule
        self.message = message
        super().__init__(f"{rule}: {message}")
