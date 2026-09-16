"""Port: keeping the captured images."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ImageStore(ABC):
    """Holds capture images and hands back an opaque reference.

    The reference is a string the store itself understands - a path today, an
    object key on S3 or MinIO tomorrow. Nothing outside the adapter may parse
    it or build one, which is what keeps local disk and object storage
    interchangeable.
    """

    @abstractmethod
    def save(self, image: bytes, *, content_type: str) -> str:
        """Store the bytes and return a reference to them."""

    @abstractmethod
    def load(self, reference: str) -> bytes:
        """Fetch previously stored bytes."""

    @abstractmethod
    def delete(self, reference: str) -> None:
        """Remove the image. Deleting something already gone is not an error."""
