"""Unit of Work: a transactional boundary around repositories."""

from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType
from typing import Self


class UnitOfWork(ABC):
    """Groups repository changes into one atomic transaction.

    Concrete implementations live in infrastructure and bind their
    repositories to a single database session::

        with uow:
            container = uow.containers.get(number)
            container.record_inspection(...)
            uow.containers.save(container)
            uow.commit()

    Leaving the ``with`` block without calling :meth:`commit` rolls back.
    """

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.rollback()

    @abstractmethod
    def commit(self) -> None: ...

    @abstractmethod
    def rollback(self) -> None: ...
