"""Unit tests for the shared kernel base classes."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.shared_kernel.application import EventDispatcher, UnitOfWork, UseCase
from src.shared_kernel.domain import (
    AggregateRoot,
    DomainEvent,
    Entity,
    Result,
    ValueObject,
)


# --------------------------------------------------------------------------- #
# Entity                                                                       #
# --------------------------------------------------------------------------- #
class _Container(Entity[str]):
    def __init__(self, number: str, condition: str) -> None:
        super().__init__(number)
        self.condition = condition


class _Booking(Entity[str]):
    pass


def test_entities_are_equal_by_id_regardless_of_other_state() -> None:
    a = _Container("MSCU1234565", condition="dirty")
    b = _Container("MSCU1234565", condition="good")
    assert a == b
    assert hash(a) == hash(b)


def test_entities_of_different_type_with_same_id_are_not_equal() -> None:
    assert _Container("X", condition="good") != _Booking("X")


def test_entity_exposes_read_only_id() -> None:
    assert _Container("MSCU1234565", condition="good").id == "MSCU1234565"


# --------------------------------------------------------------------------- #
# ValueObject                                                                  #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class _Size(ValueObject):
    length_ft: int
    height_ft: float


def test_value_objects_are_equal_by_value() -> None:
    assert _Size(40, 9.5) == _Size(40, 9.5)
    assert _Size(40, 9.5) != _Size(20, 8.5)


def test_value_objects_are_hashable_by_value() -> None:
    assert len({_Size(40, 9.5), _Size(40, 9.5)}) == 1


def test_value_object_fallback_equality_without_dataclass() -> None:
    class _Raw(ValueObject):
        def __init__(self, code: str) -> None:
            self.code = code

    assert _Raw("22G1") == _Raw("22G1")
    assert _Raw("22G1") != _Raw("45R1")


# --------------------------------------------------------------------------- #
# DomainEvent / AggregateRoot                                                  #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, kw_only=True)
class _ContainerIdentified(DomainEvent):
    container_number: str


class _Yard(AggregateRoot[str]):
    def identify(self, number: str) -> None:
        self.record_event(_ContainerIdentified(container_number=number))


def test_domain_event_gets_id_and_utc_timestamp() -> None:
    event = _ContainerIdentified(container_number="MSCU1234565")
    assert event.event_id is not None
    assert event.occurred_at.tzinfo is not None


def test_pull_events_returns_and_clears_the_buffer() -> None:
    yard = _Yard("YARD-1")
    assert yard.has_pending_events is False

    yard.identify("MSCU1234565")
    assert yard.has_pending_events is True

    events = yard.pull_events()
    assert [type(e) for e in events] == [_ContainerIdentified]
    assert yard.pull_events() == []
    assert yard.has_pending_events is False


# --------------------------------------------------------------------------- #
# Result                                                                       #
# --------------------------------------------------------------------------- #
def test_successful_result_unwraps_to_its_value() -> None:
    result: Result[int] = Result.ok(42)
    assert result.is_success and not result.is_failure
    assert result.unwrap() == 42


def test_failed_result_exposes_error_and_refuses_to_unwrap() -> None:
    result: Result[int] = Result.fail("invalid check digit")
    assert result.is_failure
    assert result.error == "invalid check digit"
    with pytest.raises(ValueError):
        result.unwrap()


def test_successful_result_has_no_error() -> None:
    with pytest.raises(ValueError):
        _ = Result.ok("x").error


# --------------------------------------------------------------------------- #
# EventDispatcher                                                              #
# --------------------------------------------------------------------------- #
def test_dispatcher_routes_events_to_handlers_of_matching_type() -> None:
    seen: list[str] = []
    dispatcher = EventDispatcher()
    dispatcher.subscribe(
        _ContainerIdentified,
        lambda e: seen.append(e.container_number),  # type: ignore[attr-defined]
    )

    dispatcher.dispatch([_ContainerIdentified(container_number="MSCU1234565")])
    assert seen == ["MSCU1234565"]


def test_dispatcher_ignores_events_without_subscribers() -> None:
    EventDispatcher().dispatch([_ContainerIdentified(container_number="X")])


# --------------------------------------------------------------------------- #
# Abstract bases stay abstract                                                 #
# --------------------------------------------------------------------------- #
def test_unit_of_work_and_use_case_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        UnitOfWork()  # type: ignore[abstract]
    with pytest.raises(TypeError):
        UseCase()  # type: ignore[abstract]
