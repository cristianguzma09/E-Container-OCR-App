"""Unit tests for the ISO 6346 container number."""

from __future__ import annotations

import pytest

from src.context.registry.domain import (
    ContainerNumber,
    InvalidContainerNumber,
    calculate_check_digit,
)

# The worked example from the ISO 6346 standard itself.
CANONICAL = "CSQU3054383"
VALID = ["CSQU3054383", "MSCU1234566", "TGHU7654320", "HLXU1111119", "MSKU0000006"]


# --------------------------------------------------------------------------- #
# Check digit                                                                  #
# --------------------------------------------------------------------------- #
def test_check_digit_matches_the_standards_worked_example() -> None:
    assert calculate_check_digit("CSQ", "U", "305438") == 3


@pytest.mark.parametrize("number", VALID)
def test_check_digit_agrees_for_every_known_good_number(number: str) -> None:
    assert calculate_check_digit(number[0:3], number[3], number[4:10]) == int(number[10])


def test_a_remainder_of_ten_is_written_as_zero() -> None:
    # MSCU000006 is the awkward case: the weighted sum leaves 10 modulo 11,
    # and ISO 6346 says that is recorded as 0, never as "10".
    assert calculate_check_digit("MSC", "U", "000006") == 0
    assert ContainerNumber.parse("MSCU0000060").check_digit == 0


def test_check_digit_rejects_a_body_of_the_wrong_length() -> None:
    with pytest.raises(ValueError):
        calculate_check_digit("MSC", "U", "12345")


# --------------------------------------------------------------------------- #
# Parsing                                                                      #
# --------------------------------------------------------------------------- #
def test_parse_splits_the_number_into_its_four_parts() -> None:
    number = ContainerNumber.parse(CANONICAL)
    assert number.owner_code == "CSQ"
    assert number.equipment_category == "U"
    assert number.serial_number == "305438"
    assert number.check_digit == 3


@pytest.mark.parametrize(
    "raw",
    ["csqu3054383", "CSQU 305438 3", "CSQU-305438-3", " csqu 3054383 ", "CSQU.305438.3"],
)
def test_parse_tolerates_case_spaces_and_separators(raw: str) -> None:
    assert ContainerNumber.parse(raw).value == CANONICAL


def test_parse_rejects_a_wrong_check_digit() -> None:
    with pytest.raises(InvalidContainerNumber) as excinfo:
        ContainerNumber.parse("CSQU3054384")
    assert "check digit must be 3" in str(excinfo.value)


@pytest.mark.parametrize(
    ("raw", "why"),
    [
        ("CSQU305438", "too short"),
        ("CSQU30543833", "too long"),
        ("CSQX3054383", "X is not a valid equipment category"),
        ("CS1U3054383", "owner code must be letters"),
        ("CSQU30543A3", "serial must be digits"),
        ("", "empty"),
    ],
)
def test_parse_rejects_malformed_input(raw: str, why: str) -> None:
    with pytest.raises(InvalidContainerNumber):
        ContainerNumber.parse(raw)


def test_is_valid_reports_instead_of_raising() -> None:
    assert ContainerNumber.is_valid(CANONICAL) is True
    assert ContainerNumber.is_valid("CSQU3054384") is False
    assert ContainerNumber.is_valid("not a container") is False


# --------------------------------------------------------------------------- #
# Construction guards                                                          #
# --------------------------------------------------------------------------- #
def test_direct_construction_still_verifies_the_check_digit() -> None:
    with pytest.raises(InvalidContainerNumber):
        ContainerNumber(
            owner_code="CSQ",
            equipment_category="U",
            serial_number="305438",
            check_digit=9,
        )


def test_direct_construction_normalises_case() -> None:
    number = ContainerNumber(
        owner_code="csq", equipment_category="u", serial_number="305438", check_digit=3
    )
    assert number.value == CANONICAL


def test_a_non_numeric_check_digit_is_rejected() -> None:
    with pytest.raises(InvalidContainerNumber):
        ContainerNumber(
            owner_code="CSQ",
            equipment_category="U",
            serial_number="305438",
            check_digit="x",  # type: ignore[arg-type]
        )


# --------------------------------------------------------------------------- #
# Presentation and value semantics                                             #
# --------------------------------------------------------------------------- #
def test_presentation_helpers() -> None:
    number = ContainerNumber.parse(CANONICAL)
    assert number.value == CANONICAL
    assert str(number) == CANONICAL
    assert number.owner_prefix == "CSQU"
    assert number.formatted == "CSQU 305438 3"


def test_numbers_are_compared_by_value_and_are_hashable() -> None:
    a = ContainerNumber.parse(CANONICAL)
    b = ContainerNumber.parse("csqu 305438 3")
    assert a == b
    assert hash(a) == hash(b)
    assert len({a, b}) == 1
    assert a != ContainerNumber.parse("MSCU1234566")
