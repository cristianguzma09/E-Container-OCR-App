"""Unit tests for the ISO 6346 size-type code."""

from __future__ import annotations

import pytest

from src.context.registry.domain import ContainerType, InvalidSizeTypeCode, SizeType


# --------------------------------------------------------------------------- #
# Size                                                                         #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("code", "length_ft", "high_cube", "label"),
    [
        ("22G1", 20, False, "20ft"),
        ("25G1", 20, True, "20ft HC"),
        ("42G1", 40, False, "40ft"),
        ("45G1", 40, True, "40ft HC"),
        ("L5G1", 45, True, "45ft HC"),
        ("L2G1", 45, False, "45ft"),
        ("20G1", 20, False, "20ft"),
    ],
)
def test_size_is_derived_from_the_code(
    code: str, length_ft: int, high_cube: bool, label: str
) -> None:
    size_type = SizeType(code)
    assert size_type.length_ft == length_ft
    assert size_type.is_high_cube is high_cube
    assert size_type.size_label == label


def test_45g1_is_a_forty_foot_high_cube_not_a_forty_five_footer() -> None:
    """The classic misread: the leading 4 is length, the 5 is height."""
    forty_hc = SizeType("45G1")
    forty_five = SizeType("L5G1")

    assert forty_hc.length_ft == 40
    assert forty_hc.is_high_cube is True
    assert forty_five.length_ft == 45
    assert forty_hc != forty_five


def test_height_in_millimetres() -> None:
    assert SizeType("20G1").height_mm == 2438
    assert SizeType("22G1").height_mm == 2591
    assert SizeType("25G1").height_mm == 2896
    assert SizeType("28G1").height_mm == 1295


def test_over_width_equipment_is_flagged() -> None:
    assert SizeType("22G1").is_over_width is False
    assert SizeType("2EG1").is_over_width is True
    assert SizeType("2EG1").is_high_cube is True


# --------------------------------------------------------------------------- #
# Type                                                                         #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("22G1", ContainerType.GENERAL_PURPOSE),
        ("22V0", ContainerType.VENTILATED),
        ("22B0", ContainerType.BULK),
        ("22S1", ContainerType.NAMED_CARGO),
        ("45R1", ContainerType.REEFER),
        ("22H0", ContainerType.INSULATED),
        ("22U1", ContainerType.OPEN_TOP),
        ("22T1", ContainerType.TANK),
        ("22A0", ContainerType.AIR_SURFACE),
    ],
)
def test_type_family_is_read_from_the_third_character(
    code: str, expected: ContainerType
) -> None:
    assert SizeType(code).container_type is expected


def test_platform_and_flat_rack_are_told_apart_by_the_fourth_character() -> None:
    assert SizeType("22P0").container_type is ContainerType.PLATFORM
    assert SizeType("22P1").container_type is ContainerType.FLAT_RACK
    assert SizeType("22P3").container_type is ContainerType.FLAT_RACK


# --------------------------------------------------------------------------- #
# Parsing and validation                                                       #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("raw", ["22g1", " 22G1 ", "22-G1", "22 G1", "22_G1"])
def test_parse_tolerates_case_spaces_and_separators(raw: str) -> None:
    assert SizeType.parse(raw).code == "22G1"


@pytest.mark.parametrize(
    ("raw", "why"),
    [
        ("22G", "too short"),
        ("22G11", "too long"),
        ("XXG1", "unknown length code"),
        ("2XG1", "unknown height code"),
        ("22Z1", "unknown type family"),
        ("22g!", "illegal character"),
        ("", "empty"),
    ],
)
def test_unrecognised_codes_are_rejected(raw: str, why: str) -> None:
    with pytest.raises(InvalidSizeTypeCode):
        SizeType.parse(raw)


def test_is_valid_reports_instead_of_raising() -> None:
    assert SizeType.is_valid("22G1") is True
    assert SizeType.is_valid("ZZZZ") is False


def test_size_types_are_compared_by_value_and_are_hashable() -> None:
    assert SizeType("22G1") == SizeType.parse("22g1")
    assert len({SizeType("22G1"), SizeType("22G1")}) == 1
    assert str(SizeType("22G1")) == "22G1"
