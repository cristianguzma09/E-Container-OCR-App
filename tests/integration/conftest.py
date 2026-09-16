"""Integration fixtures.

These run against in-memory SQLite rather than Postgres, so the suite stays
fast and needs no Docker. The one thing SQLite gets wrong - dropping timezone
information - is handled by the ``UtcDateTime`` column type, which is itself
what these tests exercise.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Importing the models registers the tables on Base.metadata.
import src.context.recognition.infrastructure.persistence.models  # noqa: F401
import src.context.registry.infrastructure.persistence.models  # noqa: F401
from src.context.recognition.api.dependencies import (
    get_image_store,
    get_ocr_engine,
)
from src.context.recognition.api.dependencies import (
    get_unit_of_work as get_recognition_uow,
)
from src.context.recognition.infrastructure.ocr.stub_engine import StubOcrEngine
from src.context.recognition.infrastructure.persistence.unit_of_work import (
    SqlAlchemyRecognitionUnitOfWork,
)
from src.context.recognition.infrastructure.storage.local_image_store import (
    LocalImageStore,
)
from src.context.registry.api.dependencies import get_unit_of_work
from src.context.registry.infrastructure.persistence.unit_of_work import (
    SqlAlchemyRegistryUnitOfWork,
)
from src.platform.app_factory import create_app
from src.platform.database import Base


@pytest.fixture
def session_factory() -> Callable[[], Session]:
    """A fresh in-memory database per test.

    ``StaticPool`` keeps every connection pointed at the same in-memory
    database; without it each new connection would get an empty one.
    """
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


@pytest.fixture
def uow(session_factory: Callable[[], Session]) -> SqlAlchemyRegistryUnitOfWork:
    return SqlAlchemyRegistryUnitOfWork(session_factory)


@pytest.fixture
def ocr_engine() -> StubOcrEngine:
    """The engine the app will use. Tests reshape it with ``set_reading``."""
    return StubOcrEngine.reading("CSQU3054383")


@pytest.fixture
def image_store(tmp_path) -> LocalImageStore:
    return LocalImageStore(tmp_path / "captures")


@pytest.fixture
def client(
    session_factory: Callable[[], Session],
    ocr_engine: StubOcrEngine,
    image_store: LocalImageStore,
) -> Iterator[TestClient]:
    """The real app, with only the outermost adapters swapped.

    Routers, schemas, use cases, mappers and the domain are all the production
    ones; only the database, the image directory and the OCR engine change.
    """
    app = create_app()
    app.dependency_overrides[get_unit_of_work] = lambda: SqlAlchemyRegistryUnitOfWork(
        session_factory
    )
    app.dependency_overrides[get_recognition_uow] = (
        lambda: SqlAlchemyRecognitionUnitOfWork(session_factory)
    )
    app.dependency_overrides[get_image_store] = lambda: image_store
    app.dependency_overrides[get_ocr_engine] = lambda: ocr_engine
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
