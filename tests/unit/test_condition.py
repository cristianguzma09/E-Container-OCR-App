"""Unit tests for container condition and the grading policy."""

from __future__ import annotations

import pytest

from src.context.registry.domain import (
    CargoGrade,
    Cleanliness,
    Condition,
    ConditionGradingPolicy,
    StructuralState,
)
from src.shared_kernel.domain import BusinessRuleViolation


# --------------------------------------------------------------------------- #
# Invariants                                                                   #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("cleanliness", "structural"),
    [
        (Cleanliness.DIRTY, StructuralState.SOUND),
        (Cleanliness.CLEAN, StructuralState.DAMAGED),
        (Cleanliness.DIRTY, StructuralState.DAMAGED),
    ],
)
def test_food_grade_requires_a_clean_and_sound_box(
    cleanliness: Cleanliness, structural: StructuralState
) -> None:
    with pytest.raises(BusinessRuleViolation) as excinfo:
        Condition(cleanliness, structural, CargoGrade.FOOD_GRADE)
    assert excinfo.value.rule in {
        "food_grade_requires_clean_and_sound",
        "damaged_container_carries_nothing",
    }


def test_a_damaged_container_cannot_be_graded_for_any_cargo() -> None:
    with pytest.raises(BusinessRuleViolation) as excinfo:
        Condition(
            Cleanliness.CLEAN, StructuralState.DAMAGED, CargoGrade.GENERAL_CARGO
        )
    assert excinfo.value.rule == "damaged_container_carries_nothing"


def test_a_damaged_container_may_be_not_suitable() -> None:
    condition = Condition(
        Cleanliness.CLEAN, StructuralState.DAMAGED, CargoGrade.NOT_SUITABLE
    )
    assert condition.is_damaged is True
    assert condition.is_available_for_loading is False


def test_a_dirty_but_sound_box_may_still_be_graded_for_general_cargo() -> None:
    """The model allows it; the *policy* is what decides to downgrade."""
    condition = Condition(
        Cleanliness.DIRTY, StructuralState.SOUND, CargoGrade.GENERAL_CARGO
    )
    assert condition.is_dirty is True


# --------------------------------------------------------------------------- #
# The four states the business talks about                                     #
# --------------------------------------------------------------------------- #
def test_named_constructors_build_the_expected_states() -> None:
    food = Condition.good_for_food_cargo()
    assert food.cargo_grade is CargoGrade.FOOD_GRADE
    assert food.is_available_for_loading is True

    general = Condition.good_for_general_cargo()
    assert general.cargo_grade is CargoGrade.GENERAL_CARGO
    assert general.is_available_for_loading is True

    dirty = Condition.dirty()
    assert dirty.is_dirty is True
    assert dirty.is_damaged is False
    assert dirty.is_available_for_loading is False

    damaged = Condition.damaged()
    assert damaged.is_damaged is True
    assert damaged.is_dirty is False
    assert damaged.is_available_for_loading is False


def test_a_container_can_be_both_dirty_and_damaged() -> None:
    condition = Condition.damaged(dirty=True)
    assert condition.is_dirty is True
    assert condition.is_damaged is True


def test_conditions_are_compared_by_value() -> None:
    assert Condition.good_for_food_cargo() == Condition.good_for_food_cargo()
    assert Condition.good_for_food_cargo() != Condition.good_for_general_cargo()
    assert len({Condition.dirty(), Condition.dirty()}) == 1


# --------------------------------------------------------------------------- #
# Grading policy                                                               #
# --------------------------------------------------------------------------- #
@pytest.fixture
def policy() -> ConditionGradingPolicy:
    return ConditionGradingPolicy()


@pytest.mark.parametrize(
    ("cleanliness", "structural", "food_certified", "expected"),
    [
        (Cleanliness.CLEAN, StructuralState.SOUND, True, CargoGrade.FOOD_GRADE),
        (Cleanliness.CLEAN, StructuralState.SOUND, False, CargoGrade.GENERAL_CARGO),
        (Cleanliness.DIRTY, StructuralState.SOUND, False, CargoGrade.NOT_SUITABLE),
        (Cleanliness.DIRTY, StructuralState.SOUND, True, CargoGrade.NOT_SUITABLE),
        (Cleanliness.CLEAN, StructuralState.DAMAGED, False, CargoGrade.NOT_SUITABLE),
        (Cleanliness.CLEAN, StructuralState.DAMAGED, True, CargoGrade.NOT_SUITABLE),
        (Cleanliness.DIRTY, StructuralState.DAMAGED, True, CargoGrade.NOT_SUITABLE),
    ],
)
def test_policy_grades_every_combination(
    policy: ConditionGradingPolicy,
    cleanliness: Cleanliness,
    structural: StructuralState,
    food_certified: bool,
    expected: CargoGrade,
) -> None:
    assert policy.grade(cleanliness, structural, food_certified=food_certified) is expected


def test_damage_outranks_a_food_certificate(policy: ConditionGradingPolicy) -> None:
    assert (
        policy.grade(Cleanliness.CLEAN, StructuralState.DAMAGED, food_certified=True)
        is CargoGrade.NOT_SUITABLE
    )


def test_assess_always_returns_a_condition_that_satisfies_its_invariants(
    policy: ConditionGradingPolicy,
) -> None:
    for cleanliness in Cleanliness:
        for structural in StructuralState:
            for certified in (True, False):
                condition = policy.assess(
                    cleanliness, structural, food_certified=certified
                )
                assert condition.cleanliness is cleanliness
                assert condition.structural is structural


def test_assess_matches_grade(policy: ConditionGradingPolicy) -> None:
    condition = policy.assess(
        Cleanliness.CLEAN, StructuralState.SOUND, food_certified=True
    )
    assert condition == Condition.good_for_food_cargo()
