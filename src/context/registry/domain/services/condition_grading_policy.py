"""How raw observations become a cargo grade."""

from __future__ import annotations

from src.context.registry.domain.model.condition import (
    CargoGrade,
    Cleanliness,
    Condition,
    StructuralState,
)


class ConditionGradingPolicy:
    """Decides what a container is fit to carry.

    This is its own domain service rather than a method on ``Condition`` for
    two reasons: it is the rule most likely to vary by depot or customer, and
    it takes several facts to reach one conclusion. Swap the implementation
    and nothing in the aggregate has to change.

    Rules applied in order:

    1. Damaged                            -> NOT_SUITABLE (repair first)
    2. Dirty                              -> NOT_SUITABLE (wash first)
    3. Clean + sound + food certificate   -> FOOD_GRADE
    4. Clean + sound                      -> GENERAL_CARGO
    """

    def grade(
        self,
        cleanliness: Cleanliness,
        structural: StructuralState,
        *,
        food_certified: bool = False,
    ) -> CargoGrade:
        if structural is StructuralState.DAMAGED:
            return CargoGrade.NOT_SUITABLE
        if cleanliness is Cleanliness.DIRTY:
            return CargoGrade.NOT_SUITABLE
        return CargoGrade.FOOD_GRADE if food_certified else CargoGrade.GENERAL_CARGO

    def assess(
        self,
        cleanliness: Cleanliness,
        structural: StructuralState,
        *,
        food_certified: bool = False,
    ) -> Condition:
        """Build the :class:`Condition` this policy awards for the observations."""
        return Condition(
            cleanliness=cleanliness,
            structural=structural,
            cargo_grade=self.grade(
                cleanliness, structural, food_certified=food_certified
            ),
        )
