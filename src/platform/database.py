"""Database engine, session factory and the declarative base.

Infrastructure only. Domain and application layers must never import from here;
they depend on repository *interfaces* defined in each context's domain layer.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.platform.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,
    future=True,
)

SessionFactory = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base for every ORM model (infrastructure layer)."""


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yields one session per request and closes it."""
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()
