"""Integration tests for the local image store."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.context.recognition.domain import InvalidImage
from src.context.recognition.infrastructure.storage.local_image_store import (
    LocalImageStore,
)

JPEG = b"\xff\xd8\xff\xe0 pretend this is a container photo"


@pytest.fixture
def store(tmp_path: Path) -> LocalImageStore:
    return LocalImageStore(tmp_path / "captures")


def test_saving_then_loading_returns_the_same_bytes(store: LocalImageStore) -> None:
    reference = store.save(JPEG, content_type="image/jpeg")
    assert store.load(reference) == JPEG


def test_the_root_directory_is_created(tmp_path: Path) -> None:
    root = tmp_path / "nested" / "captures"
    LocalImageStore(root)
    assert root.is_dir()


@pytest.mark.parametrize(
    ("content_type", "suffix"),
    [
        ("image/jpeg", ".jpg"),
        ("image/png", ".png"),
        ("image/webp", ".webp"),
        ("image/jpeg; charset=binary", ".jpg"),
        ("application/octet-stream", ".bin"),
    ],
)
def test_the_extension_follows_the_content_type(
    store: LocalImageStore, content_type: str, suffix: str
) -> None:
    assert store.save(JPEG, content_type=content_type).endswith(suffix)


def test_images_are_filed_by_day(store: LocalImageStore) -> None:
    reference = store.save(JPEG, content_type="image/jpeg")
    year, month, day, filename = reference.split("/")
    assert len(year) == 4 and len(month) == 2 and len(day) == 2
    assert filename


def test_two_saves_never_collide(store: LocalImageStore) -> None:
    first = store.save(JPEG, content_type="image/jpeg")
    second = store.save(JPEG, content_type="image/jpeg")
    assert first != second


def test_loading_something_that_was_never_stored(store: LocalImageStore) -> None:
    with pytest.raises(InvalidImage):
        store.load("2026/01/01/nope.jpg")


def test_deleting_is_idempotent(store: LocalImageStore) -> None:
    reference = store.save(JPEG, content_type="image/jpeg")
    store.delete(reference)
    store.delete(reference)  # already gone, still fine

    with pytest.raises(InvalidImage):
        store.load(reference)


@pytest.mark.parametrize(
    "reference",
    ["../secrets.env", "../../etc/passwd", "2026/../../outside.jpg"],
)
def test_a_reference_cannot_escape_the_store(
    store: LocalImageStore, reference: str
) -> None:
    """References come from the database; they must not become path traversal."""
    with pytest.raises(InvalidImage):
        store.load(reference)
