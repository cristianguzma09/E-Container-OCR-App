"""Container condition: what an inspector sees, and what the box may carry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from src.shared_kernel.domain import BusinessRuleViolation, ValueObject


class Cleanliness(StrEnum):
    CLEAN = "CLEAN"
    DIRTY = "DIRTY"


class StructuralState(StrEnum):
    SOUND = "SOUND"
    DAMAGED = "DAMAGED"


class CargoGrade(StrEnum):
    """What the container has been cleared to be loaded with."""

    NOT_SUITABLE = "NOT_SUITABLE"
    GENERAL_CARGO = "GENERAL_CARGO"
    FOOD_GRADE = "FOOD_GRADE"


@dataclass(frozen=True)
class Condition(ValueObject):
    """Two observed facts plus the grade they justify.

    "Dirty", "damaged", "good for general cargo" and "good for food cargo" are
    not four points on one scale: the first two are observations, the last two
    are conclusions drawn from them. Keeping them apart means the conclusion
    can never contradict the observation.

    Only the non-negotiable rules are enforced here:

    * ``FOOD_GRADE`` requires the box to be CLEAN **and** SOUND.
    * A DAMAGED box can only be ``NOT_SUITABLE``.

    Whether a merely *dirty* box is downgraded is a commercial decision, so it
    lives in :class:`ConditionGradingPolicy` where it can be changed per depot
    without touching the model.
    """

    cleanliness: Cleanliness
    structural: StructuralState
    cargo_grade: CargoGrade

    def __post_init__(self) -> None:
        if self.cargo_grade is CargoGrade.FOOD_GRADE and (
            self.cleanliness is not Cleanliness.CLEAN
            or self.structural is not StructuralState.SOUND
        ):
            raise BusinessRuleViolation(
                "food_grade_requires_clean_and_sound",
                f"a {self.cleanliness}/{self.structural} container cannot be food grade",
            )

        if (
            self.structural is StructuralState.DAMAGED
            and self.cargo_grade is not CargoGrade.NOT_SUITABLE
        ):
            raise BusinessRuleViolation(
                "damaged_container_carries_nothing",
                f"a damaged container cannot be graded {self.cargo_grade}",
            )

    # -- constructors for the four states the business talks about ----------
    @classmethod
    def good_for_food_cargo(cls) -> Condition:
        return cls(Cleanliness.CLEAN, StructuralState.SOUND, CargoGrade.FOOD_GRADE)

    @classmethod
    def good_for_general_cargo(cls) -> Condition:
        return cls(Cleanliness.CLEAN, StructuralState.SOUND, CargoGrade.GENERAL_CARGO)

    @classmethod
    def dirty(cls) -> Condition:
        return cls(Cleanliness.DIRTY, StructuralState.SOUND, CargoGrade.NOT_SUITABLE)

    @classmethod
    def damaged(cls, *, dirty: bool = False) -> Condition:
        return cls(
            Cleanliness.DIRTY if dirty else Cleanliness.CLEAN,
            StructuralState.DAMAGED,
            CargoGrade.NOT_SUITABLE,
        )

    @property
    def is_dirty(self) -> bool:
        return self.cleanliness is Cleanliness.DIRTY

    @property
    def is_damaged(self) -> bool:
        return self.structural is StructuralState.DAMAGED

    @property
    def is_available_for_loading(self) -> bool:
        return self.cargo_grade is not CargoGrade.NOT_SUITABLE

    def __str__(self) -> str:
        return f"{self.cleanliness}/{self.structural} -> {self.cargo_grade}"
