"""Capture images on the local filesystem."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from src.context.recognition.domain import ImageStore, InvalidImage

_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
}


class LocalImageStore(ImageStore):
    """Writes images under a root directory, one folder per day.

    Good enough for a single box and for development. Swapping in MinIO or S3
    is a new class behind the same port - which is why the reference it hands
    back is opaque: nothing outside this class may assume it is a path.
    """

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def save(self, image: bytes, *, content_type: str) -> str:
        extension = _EXTENSIONS.get(
            (content_type or "").split(";")[0].strip().lower(), ".bin"
        )
        folder = datetime.now(UTC).strftime("%Y/%m/%d")
        relative = f"{folder}/{uuid.uuid4().hex}{extension}"

        destination = self._root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(image)
        return relative

    def load(self, reference: str) -> bytes:
        path = self._resolve(reference)
        try:
            return path.read_bytes()
        except FileNotFoundError as error:
            raise InvalidImage(f"stored image '{reference}' is missing") from error

    def delete(self, reference: str) -> None:
        self._resolve(reference).unlink(missing_ok=True)

    def _resolve(self, reference: str) -> Path:
        """Resolve a reference, refusing anything that escapes the root."""
        path = (self._root / reference).resolve()
        root = self._root.resolve()
        if not path.is_relative_to(root):
            raise InvalidImage(f"'{reference}' points outside the image store")
        return path
