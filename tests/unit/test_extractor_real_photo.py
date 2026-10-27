"""Regression tests built from a real container photograph.

The fragments below are exactly what PaddleOCR returned for a photo of an
HZKU box, weights panel and all. Two failures it exposed are worth keeping
pinned down, because both produce a *confidently wrong* answer rather than an
obvious error:

1. The markings panel (``PAYLOAD 27.400 60.410``) yielded ``OADZ7400604``,
   which satisfies the check digit by coincidence and outranked the real
   number.
2. The check digit is painted in its own box on the door and the detector did
   not return it at all, so the real number arrived one character short and
   the size-type code next to it got glued on in its place.
"""

from __future__ import annotations

import pytest

from src.context.recognition.domain import (
    Confidence,
    ContainerCodeExtractor,
    TextFragment,
)

#: Verbatim PaddleOCR output for the photograph.
PHOTO = [
    ("HZKU", 1.000),
    ("633031", 1.000),
    ("22G2", 1.000),
    ("30.480", 0.982),
    ("yhyhyh", 0.693),
    ("MAX. GROSS", 0.993),
    ("67.200", 0.947),
    ("TARE", 1.000),
    ("3,080", 0.988),
    ("6.790", 0.998),
    ("PAYLOAD", 1.000),
    ("27.400", 0.994),
    ("60.410", 0.997),
]


@pytest.fixture
def extractor() -> ContainerCodeExtractor:
    return ContainerCodeExtractor()


@pytest.fixture
def photo() -> list[TextFragment]:
    return [
        TextFragment(text=text, confidence=Confidence(conf)) for text, conf in PHOTO
    ]


def test_the_real_number_is_the_top_candidate(
    extractor: ContainerCodeExtractor, photo: list[TextFragment]
) -> None:
    best = extractor.extract(photo)[0]

    assert best.value == "HZKU6330318"
    assert best.check_digit_valid is True
    assert best.check_digit_inferred is True
    assert best.raw_text == "HZKU 633031"


def test_the_weights_panel_does_not_produce_a_container_number(
    extractor: ContainerCodeExtractor, photo: list[TextFragment]
) -> None:
    """``PAYLOAD 27.400 60.410`` must not become ``OADZ7400604``."""
    values = {c.value for c in extractor.extract(photo)}

    assert "OADZ7400604" not in values
    assert all(c.value.startswith("HZKU") for c in extractor.extract(photo))


def test_an_inferred_check_digit_always_goes_to_a_person(
    extractor: ContainerCodeExtractor, photo: list[TextFragment]
) -> None:
    best = extractor.extract(photo)[0]
    assert best.needs_human_confirmation is True


def test_the_size_type_code_is_not_mistaken_for_a_check_digit(
    extractor: ContainerCodeExtractor, photo: list[TextFragment]
) -> None:
    """``22G2`` sits right under the number; its first digit must not be used."""
    candidates = {c.value: c for c in extractor.extract(photo)}

    glued = candidates.get("HZKU6330312")
    assert glued is not None
    assert glued.check_digit_valid is False
    assert glued.expected_check_digit == 8
    assert glued.score < candidates["HZKU6330318"].score


# --------------------------------------------------------------------------- #
# The rules in isolation                                                       #
# --------------------------------------------------------------------------- #
def test_a_window_may_not_begin_in_the_middle_of_a_word(
    extractor: ContainerCodeExtractor,
) -> None:
    fragments = [
        TextFragment(text=t, confidence=Confidence(1.0))
        for t in ("PAYLOAD", "27.400", "60.410")
    ]
    assert extractor.extract(fragments) == []


def test_a_body_whose_check_digit_was_never_read_is_completed(
    extractor: ContainerCodeExtractor,
) -> None:
    fragments = [
        TextFragment(text=t, confidence=Confidence(1.0)) for t in ("CSQU", "305438")
    ]

    best = extractor.extract(fragments)[0]

    assert best.value == "CSQU3054383"
    assert best.check_digit_inferred is True
    assert best.needs_human_confirmation is True


def test_a_number_read_whole_outranks_the_same_number_inferred(
    extractor: ContainerCodeExtractor,
) -> None:
    whole = extractor.extract(
        [TextFragment(text="CSQU3054383", confidence=Confidence(1.0))]
    )[0]
    inferred = extractor.extract(
        [TextFragment(text="CSQU305438", confidence=Confidence(1.0))]
    )[0]

    assert whole.value == inferred.value
    assert whole.check_digit_inferred is False
    assert inferred.check_digit_inferred is True
    assert whole.score > inferred.score


def test_a_complete_read_is_not_reported_as_inferred(
    extractor: ContainerCodeExtractor,
) -> None:
    """The split-across-lines case still counts as fully read."""
    fragments = [
        TextFragment(text=t, confidence=Confidence(1.0))
        for t in ("CSQU", "305438", "3")
    ]

    best = extractor.extract(fragments)[0]

    assert best.value == "CSQU3054383"
    assert best.check_digit_inferred is False
    assert best.needs_human_confirmation is False
