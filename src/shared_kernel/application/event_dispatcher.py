"""A minimal in-process, synchronous event bus."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable

from src.shared_kernel.domain.domain_event import DomainEvent

EventHandler = Callable[[DomainEvent], None]


class EventDispatcher:
    """Routes domain events to handlers registered for their exact type.

    Enough for a single-process application. It can be replaced by an adapter
    onto a real message broker later without any change to domain or
    application code, which only know this class.
    """

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def dispatch(self, events: Iterable[DomainEvent]) -> None:
        for event in events:
            for handler in self._handlers.get(type(event), ()):
                handler(event)
