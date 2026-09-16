"""Composition root for the registry's HTTP layer.

The only module that knows both a use case and a concrete adapter. Overriding
``get_unit_of_work`` in a test swaps the whole persistence stack for an
in-memory one without touching a router.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from src.context.registry.application import RegistryUnitOfWork
from src.context.registry.domain import ConditionGradingPolicy
from src.context.registry.infrastructure.persistence.unit_of_work import (
    SqlAlchemyRegistryUnitOfWork,
)
from src.shared_kernel.application import EventDispatcher


def get_unit_of_work() -> RegistryUnitOfWork:
    """A fresh unit of work per request; it opens its session on ``with``."""
    return SqlAlchemyRegistryUnitOfWork()


@lru_cache
def get_event_dispatcher() -> EventDispatcher:
    """One dispatcher for the process. Subscribers register at start-up."""
    return EventDispatcher()


@lru_cache
def get_grading_policy() -> ConditionGradingPolicy:
    return ConditionGradingPolicy()


UnitOfWorkDep = Annotated[RegistryUnitOfWork, Depends(get_unit_of_work)]
EventsDep = Annotated[EventDispatcher, Depends(get_event_dispatcher)]
PolicyDep = Annotated[ConditionGradingPolicy, Depends(get_grading_policy)]
