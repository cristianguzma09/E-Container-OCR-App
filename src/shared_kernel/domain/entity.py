"""Entity base."""

from __future__ import annotations


class Entity[TId]:
    """Something with a distinct identity that persists over time.

    Two entities are equal iff they have the exact same type and the same id,
    no matter how their other attributes differ.
    """

    def __init__(self, entity_id: TId) -> None:
        self._id = entity_id

    @property
    def id(self) -> TId:
        return self._id

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return type(self) is type(other) and self._id == other._id

    def __hash__(self) -> int:
        return hash((type(self).__name__, self._id))

    def __repr__(self) -> str:
        return f"{type(self).__name__}(id={self._id!r})"
