"""Tests for the anti-corruption layer between Recognition and the Registry."""

from __future__ import annotations

import pytest

from src.context.registry.application import (
    ConditionObservation,
    RecognitionOutcome,
    RecognitionTranslator,
)
from src.context.registry.domain import Cleanliness, IdentificationSource, StructuralState

NUMBER = "CSQU3054383"


@pytest.fixture
def translator() -> RecognitionTranslator:
    return RecognitionTranslator()


@pytest.fixture
def observation() -> ConditionObservation:
    return ConditionObservation(
        cleanliness=Cleanliness.CLEAN,
        structural=StructuralState.SOUND,
        inspected_by="J. Ramirez",
    )


def outcome(**overrides: object) -> RecognitionOutcome:
    defaults = {
        "job_id": "job-1",
        "container_number": NUMBER,
        "size_type_code": "22G1",
        "confidence": 0.97,
    }
    return RecognitionOutcome(**{**defaults, **overrides})  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Accepted reads                                                               #
# --------------------------------------------------------------------------- #
def test_a_confident_valid_read_becomes_a_command(
    translator: RecognitionTranslator, observation: ConditionObservation
) -> None:
    result = translator.translate(outcome(), observation)

    assert result.is_success
    command = result.unwrap()
    assert command.container_number == NUMBER
    assert command.size_type_code == "22G1"
    assert command.source is IdentificationSource.OCR
    assert command.inspected_by == "J. Ramirez"


def test_messy_ocr_text_is_normalised(
    translator: RecognitionTranslator, observation: ConditionObservation
) -> None:
    result = translator.translate(
        outcome(container_number="csqu-305438-3", size_type_code=" 22 g1 "), observation
    )

    command = result.unwrap()
    assert command.container_number == NUMBER
    assert command.size_type_code == "22G1"


def test_an_operator_override_beats_what_ocr_read(
    translator: RecognitionTranslator, observation: ConditionObservation
) -> None:
    result = translator.translate(
        outcome(size_type_code="45G1"), observation, size_type_code="L5G1"
    )
    assert result.unwrap().size_type_code == "L5G1"


def test_the_capture_image_is_carried_over_as_evidence(
    translator: RecognitionTranslator,
) -> None:
    observation = ConditionObservation(
        cleanliness=Cleanliness.CLEAN, structural=StructuralState.SOUND
    )
    result = translator.translate(outcome(image_ref="s3://captures/job-1.jpg"), observation)
    assert result.unwrap().evidence_image_ref == "s3://captures/job-1.jpg"


def test_an_explicit_evidence_reference_wins_over_the_capture(
    translator: RecognitionTranslator,
) -> None:
    observation = ConditionObservation(
        cleanliness=Cleanliness.CLEAN,
        structural=StructuralState.SOUND,
        evidence_image_ref="s3://inspections/close-up.jpg",
    )
    result = translator.translate(outcome(image_ref="s3://captures/job-1.jpg"), observation)
    assert result.unwrap().evidence_image_ref == "s3://inspections/close-up.jpg"


def test_the_observation_is_passed_through_ungraded(
    translator: RecognitionTranslator,
) -> None:
    """The ACL never decides a grade - that is the policy's job downstream."""
    observation = ConditionObservation(
        cleanliness=Cleanliness.DIRTY,
        structural=StructuralState.DAMAGED,
        food_certified=True,
    )
    command = translator.translate(outcome(), observation).unwrap()

    assert command.cleanliness is Cleanliness.DIRTY
    assert command.structural is StructuralState.DAMAGED
    assert command.food_certified is True
    assert not hasattr(command, "cargo_grade")


# --------------------------------------------------------------------------- #
# Rejected reads - failures, not exceptions                                    #
# --------------------------------------------------------------------------- #
def test_a_low_confidence_read_is_rejected(
    translator: RecognitionTranslator, observation: ConditionObservation
) -> None:
    result = translator.translate(outcome(confidence=0.42), observation)

    assert result.is_failure
    assert "confidence 0.42" in result.error
    assert "0.80" in result.error


def test_the_confidence_threshold_is_configurable(
    observation: ConditionObservation,
) -> None:
    lenient = RecognitionTranslator(minimum_confidence=0.30)
    assert lenient.translate(outcome(confidence=0.42), observation).is_success


def test_a_read_whose_check_digit_fails_is_rejected(
    translator: RecognitionTranslator, observation: ConditionObservation
) -> None:
    result = translator.translate(outcome(container_number="CSQU3054384"), observation)

    assert result.is_failure
    assert "check digit must be 3" in result.error


def test_an_unreadable_number_is_rejected(
    translator: RecognitionTranslator, observation: ConditionObservation
) -> None:
    result = translator.translate(outcome(container_number="CS?U30543"), observation)
    assert result.is_failure


def test_a_missing_size_type_is_rejected(
    translator: RecognitionTranslator, observation: ConditionObservation
) -> None:
    result = translator.translate(outcome(size_type_code=None), observation)

    assert result.is_failure
    assert "size-type" in result.error


def test_an_unrecognised_size_type_is_rejected(
    translator: RecognitionTranslator, observation: ConditionObservation
) -> None:
    result = translator.translate(outcome(size_type_code="ZZZZ"), observation)

    assert result.is_failure
    assert "size-type code" in result.error


def test_a_rejected_read_refuses_to_unwrap(
    translator: RecognitionTranslator, observation: ConditionObservation
) -> None:
    result = translator.translate(outcome(confidence=0.1), observation)
    with pytest.raises(ValueError):
        result.unwrap()
