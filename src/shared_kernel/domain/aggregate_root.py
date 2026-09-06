"""Aggregate root base."""

from __future__ import annotations

from src.shared_kernel.domain.domain_event import DomainEvent
from src.shared_kernel.domain.entity import Entity


class AggregateRoot[TId](Entity[TId]):
    """The single entry point to a cluster of objects treated as one unit.

    External code only ever touches the root. State changes record domain
    events; the application layer calls :meth:`pull_events` after the
    transaction commits and hands them to the event dispatcher.
    """

    def __init__(self, entity_id: TId) -> None:
        super().__init__(entity_id)
        self._pending_events: list[DomainEvent] = []

    def record_event(self, event: DomainEvent) -> None:
        self._pending_events.append(event)

    def pull_events(self) -> list[DomainEvent]:
        """Return the recorded events and clear the buffer."""
        events = list(self._pending_events)
        self._pending_events.clear()
        return events

    @property
    def has_pending_events(self) -> bool:
        return bool(self._pending_events)
