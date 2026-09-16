"""Unit tests for finding container numbers in OCR output."""

from __future__ import annotations

import pytest

from src.context.recognition.domain import (
    Confidence,
    ContainerCodeExtractor,
    TextFragment,
)

VALID = "CSQU3054383"


def frag(text: str, confidence: float = 0.9) -> TextFragment:
    return TextFragment(text=text, confidence=Confidence(confidence))


@pytest.fixture
def extractor() -> ContainerCodeExtractor:
    return ContainerCodeExtractor()


def best(extractor: ContainerCodeExtractor, *texts: str) -> object:
    results = extractor.extract([frag(t) for t in texts])
    return results[0] if results else None


# --------------------------------------------------------------------------- #
# Finding the number                                                           #
# --------------------------------------------------------------------------- #
def test_a_clean_single_line_read(extractor: ContainerCodeExtractor) -> None:
    candidate = best(extractor, VALID)
    assert candidate is not None
    assert candidate.value == VALID
    assert candidate.check_digit_valid is True
    assert candidate.repaired is False


def test_a_number_painted_across_three_lines_is_joined(
    extractor: ContainerCodeExtractor,
) -> None:
    """The usual case: the engine returns prefix, serial and check digit apart."""
    candidate = best(extractor, "CSQU", "305438", "3")
    assert candidate is not None
    assert candidate.value == VALID
    assert candidate.check_digit_valid is True


def test_surrounding_markings_are_ignored(
    extractor: ContainerCodeExtractor,
) -> None:
    candidate = best(extractor, "MAERSK", "CSQU 305438 3", "22G1", "MAX GROSS 30480KG")
    assert candidate is not None
    assert candidate.value == VALID


def test_spaces_and_dashes_inside_the_read_are_tolerated(
    extractor: ContainerCodeExtractor,
) -> None:
    assert best(extractor, "CSQU-305438-3").value == VALID
    assert best(extractor, "csqu 305438 3").value == VALID


def test_a_photo_with_no_container_number_yields_nothing(
    extractor: ContainerCodeExtractor,
) -> None:
    results = extractor.extract(
        [frag("HAMBURG SUD"), frag("MAX GROSS 30480 KG"), frag("TARE 3700 KG")]
    )
    assert results == []


def test_no_fragments_at_all(extractor: ContainerCodeExtractor) -> None:
    assert extractor.extract([]) == []


# --------------------------------------------------------------------------- #
# Repairing confusable characters                                              #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("misread", "why"),
    [
        ("C5QU3054383", "S read as 5 in the owner code"),
        ("CSQU30543B3", "8 read as B in the serial"),
        ("CSQU3O54383", "0 read as O in the serial"),
        ("C5QU3O54383", "two confusable characters, one substitution still fixes it"),
    ],
)
def test_a_confusable_character_is_repaired_using_the_check_digit(
    extractor: ContainerCodeExtractor, misread: str, why: str
) -> None:
    candidate = best(extractor, misread)
    assert candidate is not None
    assert candidate.value == VALID
    assert candidate.check_digit_valid is True
    assert candidate.repaired is True


def test_a_repaired_read_always_asks_for_confirmation(
    extractor: ContainerCodeExtractor,
) -> None:
    """A repair is a guess that happens to check out - never accept it silently."""
    candidate = best(extractor, "C5QU3054383")
    assert candidate.repaired is True
    assert candidate.needs_human_confirmation is True


def test_a_genuinely_wrong_number_is_not_invented_into_a_valid_one(
    extractor: ContainerCodeExtractor,
) -> None:
    """The safety property: repair may correct a character, never fabricate."""
    candidate = best(extractor, "CSQU3054387")
    assert candidate is not None
    assert candidate.value == "CSQU3054387"
    assert candidate.check_digit_valid is False
    assert candidate.expected_check_digit == 3
    assert candidate.needs_human_confirmation is True


def test_an_invalid_read_still_reports_the_expected_check_digit(
    extractor: ContainerCodeExtractor,
) -> None:
    candidate = best(extractor, "CSQU3054380")
    assert candidate.check_digit_valid is False
    assert candidate.expected_check_digit == 3


def test_a_garbled_check_digit_is_never_synthesised_from_the_body(
    extractor: ContainerCodeExtractor,
) -> None:
    """Repair works on the body only, deliberately.

    Recomputing the check digit from whatever body was read would make every
    reading "valid" and destroy the only independent check there is. So a
    number whose last character came back as a letter is reported as failing,
    with the digit it should have been, and a person decides.
    """
    candidate = best(extractor, "CSQU305438B")

    assert candidate.value == "CSQU3054388"  # B coerced to 8 by position
    assert candidate.check_digit_valid is False
    assert candidate.expected_check_digit == 3
    assert candidate.needs_human_confirmation is True


# --------------------------------------------------------------------------- #
# Ranking                                                                      #
# --------------------------------------------------------------------------- #
def test_a_valid_check_digit_outranks_a_more_confident_invalid_read(
    extractor: ContainerCodeExtractor,
) -> None:
    """Arithmetic beats the engine's own opinion of itself."""
    results = extractor.extract(
        [frag("CSQU3054387", confidence=0.99), frag(VALID, confidence=0.55)]
    )

    assert results[0].value == VALID
    assert results[0].check_digit_valid is True
    assert results[0].score > results[1].score


def test_among_valid_reads_the_more_confident_one_wins(
    extractor: ContainerCodeExtractor,
) -> None:
    results = extractor.extract(
        [frag(VALID, confidence=0.6), frag("MSCU1234566", confidence=0.95)]
    )
    assert results[0].value == "MSCU1234566"


def test_an_unrepaired_valid_read_outranks_a_repaired_one(
    extractor: ContainerCodeExtractor,
) -> None:
    clean = extractor.extract([frag(VALID, confidence=0.9)])[0]
    repaired = extractor.extract([frag("C5QU3054383", confidence=0.9)])[0]

    assert clean.value == repaired.value
    assert clean.score > repaired.score


def test_the_weakest_fragment_caps_a_joined_reads_confidence(
    extractor: ContainerCodeExtractor,
) -> None:
    results = extractor.extract(
        [frag("CSQU", 0.99), frag("305438", 0.40), frag("3", 0.99)]
    )
    assert results[0].confidence.value == pytest.approx(0.40)


def test_the_same_number_read_twice_appears_once(
    extractor: ContainerCodeExtractor,
) -> None:
    results = extractor.extract([frag(VALID), frag(VALID), frag("CSQU 305438 3")])
    assert [c.value for c in results] == [VALID]


def test_the_raw_text_is_preserved_for_review(
    extractor: ContainerCodeExtractor,
) -> None:
    candidate = best(extractor, "C5QU3054383")
    assert candidate.value == VALID
    assert candidate.raw_text == "C5QU3054383"
