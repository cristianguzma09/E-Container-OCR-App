"""Tests for the read-only use cases."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.context.registry.application import (
    ContainerNotFound,
    ContainerQuery,
    GetContainer,
    GetInspectionHistory,
    InspectionHistoryQuery,
    ListContainers,
    PagedQuery,
    RecordInspection,
    RecordInspectionCommand,
    RegisterContainerCommand,
    RegisterContainerFromRecognition,
)
from src.context.registry.domain import Cleanliness, StructuralState
from tests.application.fakes import FakeRegistryUnitOfWork

NUMBERS = ["CSQU3054383", "MSCU1234566", "TGHU7654320"]
MISSING = "HLXU1111119"
BASE = datetime(2026, 9, 15, 8, 0, tzinfo=UTC)


@pytest.fixture
def uow() -> FakeRegistryUnitOfWork:
    return FakeRegistryUnitOfWork()


@pytest.fixture
def populated(uow: FakeRegistryUnitOfWork) -> FakeRegistryUnitOfWork:
    register = RegisterContainerFromRecognition(uow)
    for number in NUMBERS:
        register.execute(
            RegisterContainerCommand(
                container_number=number,
                size_type_code="22G1",
                cleanliness=Cleanliness.CLEAN,
                structural=StructuralState.SOUND,
            )
        )
    return uow


# --------------------------------------------------------------------------- #
# GetContainer                                                                 #
# --------------------------------------------------------------------------- #
def test_get_container_returns_the_container_and_its_history(
    populated: FakeRegistryUnitOfWork,
) -> None:
    record = RecordInspection(populated)
    for index, cleanliness in enumerate([Cleanliness.DIRTY, Cleanliness.CLEAN]):
        record.execute(
            RecordInspectionCommand(
                container_number=NUMBERS[0],
                inspected_by=f"inspector-{index}",
                cleanliness=cleanliness,
                structural=StructuralState.SOUND,
                inspected_at=BASE + timedelta(hours=index),
            )
        )

    detail = GetContainer(populated).execute(ContainerQuery(container_number=NUMBERS[0]))

    assert detail.container.number == NUMBERS[0]
    assert detail.container.inspection_count == 2
    # newest first
    assert [i.inspected_by for i in detail.inspections] == ["inspector-1", "inspector-0"]
    assert detail.inspections[0].cleanliness == "CLEAN"
    assert detail.inspections[1].cleanliness == "DIRTY"


def test_get_container_accepts_a_messy_number(
    populated: FakeRegistryUnitOfWork,
) -> None:
    detail = GetContainer(populated).execute(
        ContainerQuery(container_number="csqu 305438 3")
    )
    assert detail.container.number == "CSQU3054383"


def test_get_container_reports_a_missing_container(
    populated: FakeRegistryUnitOfWork,
) -> None:
    with pytest.raises(ContainerNotFound):
        GetContainer(populated).execute(ContainerQuery(container_number=MISSING))


# --------------------------------------------------------------------------- #
# ListContainers                                                               #
# --------------------------------------------------------------------------- #
def test_list_returns_every_container(populated: FakeRegistryUnitOfWork) -> None:
    views = ListContainers(populated).execute(PagedQuery())
    assert {v.number for v in views} == set(NUMBERS)


def test_list_pages(populated: FakeRegistryUnitOfWork) -> None:
    use_case = ListContainers(populated)

    first = use_case.execute(PagedQuery(limit=2, offset=0))
    second = use_case.execute(PagedQuery(limit=2, offset=2))

    assert len(first) == 2
    assert len(second) == 1
    assert {v.number for v in first}.isdisjoint({v.number for v in second})


def test_list_on_an_empty_register(uow: FakeRegistryUnitOfWork) -> None:
    assert ListContainers(uow).execute(PagedQuery()) == []


# --------------------------------------------------------------------------- #
# GetInspectionHistory                                                         #
# --------------------------------------------------------------------------- #
def test_inspection_history_is_returned_newest_first(
    populated: FakeRegistryUnitOfWork,
) -> None:
    record = RecordInspection(populated)
    for index in range(3):
        record.execute(
            RecordInspectionCommand(
                container_number=NUMBERS[0],
                inspected_by=f"inspector-{index}",
                cleanliness=Cleanliness.CLEAN,
                structural=StructuralState.SOUND,
                inspected_at=BASE + timedelta(hours=index),
            )
        )

    history = GetInspectionHistory(populated).execute(
        InspectionHistoryQuery(container_number=NUMBERS[0])
    )

    assert [i.inspected_by for i in history] == [
        "inspector-2",
        "inspector-1",
        "inspector-0",
    ]


def test_inspection_history_pages(populated: FakeRegistryUnitOfWork) -> None:
    record = RecordInspection(populated)
    for index in range(3):
        record.execute(
            RecordInspectionCommand(
                container_number=NUMBERS[0],
                inspected_by=f"inspector-{index}",
                cleanliness=Cleanliness.CLEAN,
                structural=StructuralState.SOUND,
                inspected_at=BASE + timedelta(hours=index),
            )
        )

    page = GetInspectionHistory(populated).execute(
        InspectionHistoryQuery(container_number=NUMBERS[0], limit=2, offset=1)
    )

    assert [i.inspected_by for i in page] == ["inspector-1", "inspector-0"]


def test_inspection_history_of_a_container_never_inspected_is_empty(
    populated: FakeRegistryUnitOfWork,
) -> None:
    assert (
        GetInspectionHistory(populated).execute(
            InspectionHistoryQuery(container_number=NUMBERS[1])
        )
        == []
    )


def test_inspection_history_of_an_unknown_container_is_refused(
    populated: FakeRegistryUnitOfWork,
) -> None:
    with pytest.raises(ContainerNotFound):
        GetInspectionHistory(populated).execute(
            InspectionHistoryQuery(container_number=MISSING)
        )
