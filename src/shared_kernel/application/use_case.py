"""Use case base."""

from __future__ import annotations

from abc import ABC, abstractmethod


class UseCase[TRequest, TResponse](ABC):
    """One application operation that orchestrates domain objects and ports.

    Dependencies (repositories, unit of work, ports) are injected through
    ``__init__``; the operation itself is :meth:`execute`.
    """

    @abstractmethod
    def execute(self, request: TRequest) -> TResponse: ...
