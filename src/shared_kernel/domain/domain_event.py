"""Domain event base."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    """A fact that has already happened in the domain, named in the past tense.

    Subclass with the payload the subscribers need::

        @dataclass(frozen=True, kw_only=True)
        class ContainerIdentified(DomainEvent):
            container_number: str
            size_type_code: str
    """

    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
