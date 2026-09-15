"""ISO 6346 check-digit ("DV" / digito verificador) arithmetic.

Stateless domain knowledge, deliberately kept outside the value object so it
can also be used on its own - for example to rebuild the last digit of an OCR
read that came back smudged, or to score how likely a candidate read is.
"""

from __future__ import annotations

# A = 10, then ascending, skipping every multiple of 11 (11, 22, 33).
LETTER_VALUES: dict[str, int] = dict(
    zip(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        [value for value in range(10, 39) if value % 11 != 0],
        strict=True,
    )
)

BODY_LENGTH = 10


def calculate_check_digit(
    owner_code: str, equipment_category: str, serial_number: str
) -> int:
    """Return the check digit for the first 10 characters of a container number.

    Each character is converted to a number (digits as themselves, letters via
    :data:`LETTER_VALUES`), weighted by ``2 ** position``, summed, and reduced
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
