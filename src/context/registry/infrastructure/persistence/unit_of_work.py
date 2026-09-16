"""SQLAlchemy implementation of the registry's unit of work."""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType

from sqlalchemy.orm import Session

from src.context.registry.application import RegistryUnitOfWork
from src.context.registry.infrastructure.persistence.container_repository import (
    SqlAlchemyContainerRepository,
)
from src.context.registry.infrastructure.persistence.inspection_repository import (
    SqlAlchemyInspectionRepository,
)
from src.platform.database import SessionFactory


class SqlAlchemyRegistryUnitOfWork(RegistryUnitOfWork):
    """Opens one session per ``with`` block and wires both repositories to it.

    The session is opened on entry and closed on exit, so a use case never
    holds one open between calls. Because repositories hand back plain domain
    objects rather than ORM instances, the aggregate stays usable after the
    session is gone - which is what lets the use case build its view *after*
    the transaction has closed.
    """

    def __init__(self, session_factory: Callable[[], Session] = SessionFactory) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    def __enter__(self) -> SqlAlchemyRegistryUnitOfWork:
        self._session = self._session_factory()
        self.containers = SqlAlchemyContainerRepository(self._session)
        self.inspections = SqlAlchemyInspectionRepository(self._session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            self.rollback()
        finally:
            if self._session is not None:
                self._session.close()
                self._session = None

    @property
    def session(self) -> Session:
        if self._session is None:
            raise RuntimeError("the unit of work is only usable inside a with block")
        return self._session

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
