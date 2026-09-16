"""The ISO 6346 container number - the identity of a container."""

from __future__ import annotations

from dataclasses import dataclass

from src.context.registry.domain.errors import InvalidContainerNumber
from src.shared_kernel.domain import ValueObject
from src.shared_kernel.iso6346 import (
    NUMBER_PATTERN as _FORMAT,
)
from src.shared_kernel.iso6346 import (
    calculate_check_digit,
    normalise,
)


@dataclass(frozen=True)
class ContainerNumber(ValueObject):
    """The 11-character mark painted on every maritime container.

    ``MSCU 123456 5``
     ^^^^ ^^^^^^ ^
     |  | |      +-- check digit ("DV"), derived from the other ten
     |  | +--------- 6-digit serial number
     |  +----------- equipment category: U freight, J equipment, Z chassis
     +-------------- 3-letter owner code (the BIC acronym / sigla)

    The check digit is never taken on trust: it is recomputed whenever an
    instance is built, so holding a ``ContainerNumber`` is itself proof that
    the number is well formed. An OCR read that fails here is a read to send
    back for review, not data to store.
    """

    owner_code: str
    equipment_category: str
    serial_number: str
    check_digit: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_code", str(self.owner_code).strip().upper())
        object.__setattr__(
            self, "equipment_category", str(self.equipment_category).strip().upper()
        )
        object.__setattr__(self, "serial_number", str(self.serial_number).strip())
        try:
            object.__setattr__(self, "check_digit", int(self.check_digit))
        except (TypeError, ValueError):
            raise InvalidContainerNumber(
                str(self.check_digit), "check digit must be a single digit"
            ) from None

        if not _FORMAT.fullmatch(self.value):
            raise InvalidContainerNumber(
                self.value,
                "expected 3 letters, then U/J/Z, then 6 digits and a check digit",
            )

        expected = calculate_check_digit(
            self.owner_code, self.equipment_category, self.serial_number
        )
        if expected != self.check_digit:
            raise InvalidContainerNumber(
                self.value, f"check digit must be {expected}, not {self.check_digit}"
            )

    @classmethod
    def parse(cls, raw: str) -> ContainerNumber:
        """Build a number from a raw string, tolerating spaces, dashes and case."""
        cleaned = normalise(raw)
        match = _FORMAT.fullmatch(cleaned)
        if match is None:
            raise InvalidContainerNumber(
                cleaned,
                "expected 3 letters, then U/J/Z, then 6 digits and a check digit",
            )
        return cls(
            owner_code=cleaned[0:3],
            equipment_category=cleaned[3],
            serial_number=cleaned[4:10],
            check_digit=int(cleaned[10]),
        )

    @classmethod
    def is_valid(cls, raw: str) -> bool:
        """True when ``raw`` parses and its check digit agrees."""
        try:
            cls.parse(raw)
        except InvalidContainerNumber:
            return False
        return True

    @property
    def value(self) -> str:
        """The canonical 11-character form, e.g. ``CSQU3054383``."""
        return (
            f"{self.owner_code}{self.equipment_category}"
            f"{self.serial_number}{self.check_digit}"
        )

    @property
    def owner_prefix(self) -> str:
        """Owner code plus category letter, as registered with the BIC."""
        return f"{self.owner_code}{self.equipment_category}"

    @property
    def formatted(self) -> str:
        """Grouped for people to read: ``CSQU 305438 3``."""
        return f"{self.owner_prefix} {self.serial_number} {self.check_digit}"

    def __str__(self) -> str:
        return self.value
