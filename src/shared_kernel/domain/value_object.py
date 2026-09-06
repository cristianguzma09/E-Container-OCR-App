"""Value object base."""

from __future__ import annotations


class ValueObject:
    """Immutable, compared by the value of its attributes rather than identity.

    Declare subclasses as frozen dataclasses; the decorator then supplies
    value-based equality and hashing::

        @dataclass(frozen=True)
        class ContainerNumber(ValueObject):
            owner_code: str
            category: str
            serial: str
            check_digit: int

    The ``__eq__`` / ``__hash__`` here are only a fallback for subclasses that
    are not dataclasses, plus a common type to check against.
    """

    def __eq__(self, other: object) -> bool:
        if other.__class__ is not self.__class__:
            return NotImplemented
        return vars(self) == vars(other)

    def __hash__(self) -> int:
        return hash((self.__class__, tuple(sorted(vars(self).items()))))
