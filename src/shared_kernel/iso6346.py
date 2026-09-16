"""ISO 6346 - the published standard for marking freight containers.

This lives in the shared kernel rather than in a bounded context because it is
*external* knowledge that both contexts legitimately share. The Registry uses
it to validate an identity; Recognition uses it to tell a good OCR read from a
bad one. Neither context owns the standard, and neither should have to import
the other to get at it.

Only character-level facts live here. What a size code means in feet, or which
equipment family a type code names, is the Registry's business and stays there.
"""

from __future__ import annotations

import re

#: A = 10, then ascending, skipping every multiple of 11 (11, 22, 33).
LETTER_VALUES: dict[str, int] = dict(
    zip(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        [value for value in range(10, 39) if value % 11 != 0],
        strict=True,
    )
)

#: Owner code + equipment category + serial number, before the check digit.
BODY_LENGTH = 10
#: The complete mark, check digit included.
NUMBER_LENGTH = 11

#: Equipment category identifiers: freight container, equipment, chassis.
EQUIPMENT_CATEGORIES = frozenset("UJZ")

#: The complete 11-character mark.
NUMBER_PATTERN = re.compile(r"[A-Z]{3}[UJZ]\d{6}\d")
#: The first ten characters, from which the check digit is derived.
BODY_PATTERN = re.compile(r"[A-Z]{3}[UJZ]\d{6}")
#: Punctuation people and OCR sprinkle through a printed number.
SEPARATORS_PATTERN = re.compile(r"[\s\-_.]")


def calculate_check_digit(
    owner_code: str, equipment_category: str, serial_number: str
) -> int:
    """Return the check digit for the first ten characters of a number.

    Each character becomes a number (digits as themselves, letters via
    :data:`LETTER_VALUES`), weighted by ``2 ** position``, summed and reduced
    modulo 11. A remainder of 10 is written as ``0``.
    """
    body = f"{owner_code}{equipment_category}{serial_number}".upper()
    if len(body) != BODY_LENGTH:
        raise ValueError(
            f"expected {BODY_LENGTH} characters before the check digit, got {len(body)}"
        )

    total = 0
    for position, char in enumerate(body):
        if char.isdigit():
            value = int(char)
        elif char in LETTER_VALUES:
            value = LETTER_VALUES[char]
        else:
            raise ValueError(f"'{char}' is neither a digit nor a letter A-Z")
        total += value * (2**position)

    return (total % 11) % 10


def normalise(raw: str) -> str:
    """Strip separators and upper-case, the way a printed number is read."""
    return SEPARATORS_PATTERN.sub("", raw or "").upper()
