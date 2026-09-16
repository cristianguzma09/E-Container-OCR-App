"""Where on the image something was found."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.shared_kernel.domain import ValueObject


@dataclass(frozen=True)
class BoundingBox(ValueObject):
    """An axis-aligned rectangle in pixels, origin top-left.

    Detection engines hand back a four-point polygon because painted text on a
    container is rarely square to the camera. The polygon is reduced to its
    enclosing rectangle here: the extra precision buys nothing for cropping a
    review thumbnail, which is all this is for.
    """

    left: int
    top: int
    width: int
    height: int

    def __post_init__(self) -> None:
        for name in ("left", "top", "width", "height"):
            object.__setattr__(self, name, int(getattr(self, name)))
        if self.width <= 0 or self.height <= 0:
            raise ValueError("a bounding box must have positive width and height")
        if self.left < 0 or self.top < 0:
            raise ValueError("a bounding box cannot start off the image")

    @classmethod
    def around(cls, polygon: Sequence[Sequence[float]]) -> BoundingBox:
        """Enclose a polygon of ``(x, y)`` points."""
        if len(polygon) < 2:
            raise ValueError("need at least two points to build a box")
        xs = [float(point[0]) for point in polygon]
        ys = [float(point[1]) for point in polygon]
        left, top = min(xs), min(ys)
        return cls(
            left=int(left),
            top=int(top),
            width=max(1, int(max(xs) - left)),
            height=max(1, int(max(ys) - top)),
        )

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    @property
    def area(self) -> int:
        return self.width * self.height
