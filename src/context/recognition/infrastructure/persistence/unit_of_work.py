"""SQLAlchemy implementation of the recognition unit of work."""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType

from sqlalchemy.orm import Session

from src.context.recognition.application import RecognitionUnitOfWork
from src.context.recognition.infrastructure.persistence.job_repository import (
    SqlAlchemyRecognitionJobRepository,
)
from src.platform.database import SessionFactory


class SqlAlchemyRecognitionUnitOfWork(RecognitionUnitOfWork):
    """Opens one session per ``with`` block and wires the job repository to it."""

    def __init__(self, session_factory: Callable[[], Session] = SessionFactory) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    def __enter__(self) -> SqlAlchemyRecognitionUnitOfWork:
        self._session = self._session_factory()
        self.jobs = SqlAlchemyRecognitionJobRepository(self._session)
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
