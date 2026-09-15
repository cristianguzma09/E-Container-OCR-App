"""The ISO 6346 size-type code - where a container's size and type come from."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from src.context.registry.domain.errors import InvalidSizeTypeCode
from src.shared_kernel.domain import ValueObject


class ContainerType(StrEnum):
    """The equipment families an operator actually distinguishes."""

    GENERAL_PURPOSE = "GENERAL_PURPOSE"
    VENTILATED = "VENTILATED"
    BULK = "BULK"
    NAMED_CARGO = "NAMED_CARGO"
    REEFER = "REEFER"
    INSULATED = "INSULATED"
    OPEN_TOP = "OPEN_TOP"
    PLATFORM = "PLATFORM"
    FLAT_RACK = "FLAT_RACK"
    TANK = "TANK"
    AIR_SURFACE = "AIR_SURFACE"


_FORMAT = re.compile(r"[0-9A-Z]{4}")
_SEPARATORS = re.compile(r"[\s\-_.]")

#: Character 1 -> nominal length in feet.
LENGTH_FT: dict[str, int] = {
    "1": 10, "2": 20, "3": 30, "4": 40,
    "B": 24, "C": 24, "D": 41, "E": 43, "F": 45,
    "G": 48, "H": 49, "K": 53, "L": 45, "M": 48, "N": 49, "P": 53,
}

#: Character 2 -> (external height in mm, whether the box is over-width).
HEIGHT_MM: dict[str, tuple[int, bool]] = {
    "0": (2438, False),  # 8 ft 0 in
    "2": (2591, False),  # 8 ft 6 in - standard
    "4": (2743, False),  # 9 ft 0 in
    "5": (2896, False),  # 9 ft 6 in - high cube
    "6": (2996, False),  # over 9 ft 6 in
    "8": (1295, False),  # 4 ft 3 in - half height
    "9": (1219, False),  # under 4 ft
    "C": (2591, True),
    "D": (2743, True),
    "E": (2896, True),
    "F": (2996, True),
}

#: First character of the type code -> family.
TYPE_FAMILY: dict[str, ContainerType] = {
    "G": ContainerType.GENERAL_PURPOSE,
    "V": ContainerType.VENTILATED,
    "B": ContainerType.BULK,
    "S": ContainerType.NAMED_CARGO,
    "R": ContainerType.REEFER,
    "H": ContainerType.INSULATED,
    "U": ContainerType.OPEN_TOP,
    "P": ContainerType.PLATFORM,
    "T": ContainerType.TANK,
    "A": ContainerType.AIR_SURFACE,
}

HIGH_CUBE_THRESHOLD_MM = 2896


@dataclass(frozen=True)
class SizeType(ValueObject):
    """ISO 6346 size-type code, e.g. ``22G1`` - a 20ft general purpose box.

    ``2 2 G 1``
      | | +-+-- type code: family letter plus a detail digit
      | +------ height and width code (2 = 8ft 6in, 5 = 9ft 6in high cube)
      +-------- length code (2 = 20ft, 4 = 40ft, L = 45ft)

    Careful: ``45G1`` is a **40ft high cube**, not a 45-footer. The leading
    ``4`` is the length and the ``5`` is the height. A genuine 45ft box is
    ``L5G1``. Getting this wrong misprices a booking, which is exactly why
    size and type are *derived* from the code here instead of being stored as
    separate fields that can drift apart.
    """

    code: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code).strip().upper())
        code = self.code

        if not _FORMAT.fullmatch(code):
            raise InvalidSizeTypeCode(code, "expected 4 characters, A-Z or 0-9")
        if code[0] not in LENGTH_FT:
            raise InvalidSizeTypeCode(code, f"unknown length code '{code[0]}'")
        if code[1] not in HEIGHT_MM:
            raise InvalidSizeTypeCode(code, f"unknown height/width code '{code[1]}'")
        if code[2] not in TYPE_FAMILY:
            raise InvalidSizeTypeCode(code, f"unknown type code '{code[2:]}'")

    @classmethod
    def parse(cls, raw: str) -> SizeType:
        """Build from a raw string, tolerating spaces, dashes and case."""
        return cls(code=_SEPARATORS.sub("", raw or ""))

    @classmethod
    def is_valid(cls, raw: str) -> bool:
        try:
            cls.parse(raw)
        except InvalidSizeTypeCode:
            return False
        return True

    @property
    def length_ft(self) -> int:
        return LENGTH_FT[self.code[0]]

    @property
    def height_mm(self) -> int:
        return HEIGHT_MM[self.code[1]][0]

    @property
    def is_over_width(self) -> bool:
        """Wider than the standard 2438 mm (pallet-wide equipment)."""
        return HEIGHT_MM[self.code[1]][1]

    @property
    def is_high_cube(self) -> bool:
        return self.height_mm >= HIGH_CUBE_THRESHOLD_MM

    @property
    def container_type(self) -> ContainerType:
        family = TYPE_FAMILY[self.code[2]]
        if family is ContainerType.PLATFORM and self.code[3] != "0":
            return ContainerType.FLAT_RACK
        return family

    @property
    def size_label(self) -> str:
        """Trade shorthand for the UI: ``20ft``, ``40ft HC``, ``45ft HC``."""
        return f"{self.length_ft}ft HC" if self.is_high_cube else f"{self.length_ft}ft"

    def __str__(self) -> str:
        return self.code
