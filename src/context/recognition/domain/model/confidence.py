"""How sure the engine is about something."""

from __future__ import annotations

from dataclasses import dataclass

from src.shared_kernel.domain import ValueObject


@dataclass(frozen=True, order=True)
class Confidence(ValueObject):
    """A score between 0 and 1.

    A value object rather than a bare float so that an out-of-range score from
    a misbehaving engine adapter is caught at the boundary instead of quietly
    skewing every ranking downstream.
    """

    value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", float(self.value))
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f"confidence must be between 0 and 1, got {self.value}")

    @classmethod
    def certain(cls) -> Confidence:
        return cls(1.0)

    @classmethod
    def unknown(cls) -> Confidence:
        return cls(0.0)

    @property
    def percentage(self) -> float:
        return round(self.value * 100, 1)

    def __str__(self) -> str:
        return f"{self.percentage}%"
