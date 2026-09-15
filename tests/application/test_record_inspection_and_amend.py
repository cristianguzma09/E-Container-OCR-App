"""Use case tests for recording inspections and correcting details."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.context.registry.application import (
    AmendContainerDetails,
    AmendContainerDetailsCommand,
    ContainerNotFound,
    RecordInspection,
    RecordInspectionCommand,
    RegisterContainerCommand,
    RegisterContainerFromRecognition,
)
from src.context.registry.domain import (
    Cleanliness,
    ContainerConditionChanged,
    ContainerSizeTypeCorrected,
    InspectionRecorded,
    StructuralState,
)
from tests.application.fakes import FakeRegistryUnitOfWork, RecordingEventDispatcher

NUMBER = "CSQU3054383"
MISSING = "MSCU1234566"


@pytest.fixture
def uow() -> FakeRegistryUnitOfWork:
    return FakeRegistryUnitOfWork()


@pytest.fixture
def events() -> RecordingEventDispatcher:
    return RecordingEventDispatcher()


@pytest.fixture
def registered(uow: FakeRegistryUnitOfWork) -> None:
    """A clean, sound, general-cargo container already on the register."""
    RegisterContainerFromRecognition(uow).execute(
        RegisterContainerCommand(
            container_number=NUMBER,
            size_type_code="22G1",
            cleanliness=Cleanliness.CLEAN,
            structural=StructuralState.SOUND,
        )
    )


# --------------------------------------------------------------------------- #
# Recording an inspection                                                      #
# --------------------------------------------------------------------------- #
def test_an_inspection_updates_the_current_condition(
    uow: FakeRegistryUnitOfWork, registered: None
) -> None:
    view = RecordInspection(uow).execute(
        RecordInspectionCommand(
            container_number=NUMBER,
            inspected_by="J. Ramirez",
            cleanliness=Cleanliness.DIRTY,
            structural=StructuralState.SOUND,
            notes="floor needs washing",
        )
    )

    assert view.cleanliness == "DIRTY"
    assert view.cargo_grade == "NOT_SUITABLE"
    assert view.is_available_for_loading is False
    assert view.inspection_count == 1
    assert uow.committed is True


def test_a_change_of_grade_publishes_both_events(
    uow: FakeRegistryUnitOfWork, events: RecordingEventDispatcher, registered: None
) -> None:
    RecordInspection(uow, events=events).execute(
        RecordInspectionCommand(
            container_number=NUMBER,
            inspected_by="J. Ramirez",
            cleanliness=Cleanliness.CLEAN,
            structural=StructuralState.DAMAGED,
        )
    )

    assert len(events.of_type(InspectionRecorded)) == 1
    changed = events.of_type(ContainerConditionChanged)
    assert len(changed) == 1
    assert changed[0].previous_grade == "GENERAL_CARGO"
    assert changed[0].new_grade == "NOT_SUITABLE"


def test_confirming_the_same_grade_publishes_no_change_event(
    uow: FakeRegistryUnitOfWork, events: RecordingEventDispatcher, registered: None
) -> None:
    RecordInspection(uow, events=events).execute(
        RecordInspectionCommand(
            container_number=NUMBER,
            inspected_by="J. Ramirez",
            cleanliness=Cleanliness.CLEAN,
            structural=StructuralState.SOUND,
        )
    )

    assert len(events.of_type(InspectionRecorded)) == 1
    assert events.of_type(ContainerConditionChanged) == []


def test_successive_inspections_accumulate(
    uow: FakeRegistryUnitOfWork, registered: None
) -> None:
    use_case = RecordInspection(uow)
    base = datetime(2026, 9, 15, 8, 0, tzinfo=UTC)

    for index, cleanliness in enumerate([Cleanliness.DIRTY, Cleanliness.CLEAN]):
        view = use_case.execute(
            RecordInspectionCommand(
                container_number=NUMBER,
                inspected_by="J. Ramirez",
                cleanliness=cleanliness,
                structural=StructuralState.SOUND,
                inspected_at=base + timedelta(hours=index),
            )
        )

    assert view.inspection_count == 2
    assert view.cargo_grade == "GENERAL_CARGO"


def test_inspecting_an_unknown_container_is_refused(
    uow: FakeRegistryUnitOfWork,
) -> None:
    with pytest.raises(ContainerNotFound) as excinfo:
        RecordInspection(uow).execute(
            RecordInspectionCommand(
                container_number=MISSING,
                inspected_by="J. Ramirez",
                cleanliness=Cleanliness.CLEAN,
                structural=StructuralState.SOUND,
            )
        )

    assert excinfo.value.container_number == MISSING
    assert uow.committed is False


# --------------------------------------------------------------------------- #
# Amending details                                                             #
# --------------------------------------------------------------------------- #
def test_correcting_a_misread_size_type(
    uow: FakeRegistryUnitOfWork, events: RecordingEventDispatcher, registered: None
) -> None:
    view = AmendContainerDetails(uow, events=events).execute(
        AmendContainerDetailsCommand(container_number=NUMBER, size_type_code="L5G1")
    )

    assert view.size_type_code == "L5G1"
    assert view.size_label == "45ft HC"
    assert view.length_ft == 45

    corrected = events.of_type(ContainerSizeTypeCorrected)
    assert len(corrected) == 1
    assert corrected[0].previous_code == "22G1"
    assert corrected[0].new_code == "L5G1"


def test_amending_to_the_same_value_publishes_nothing(
    uow: FakeRegistryUnitOfWork, events: RecordingEventDispatcher, registered: None
) -> None:
    AmendContainerDetails(uow, events=events).execute(
        AmendContainerDetailsCommand(container_number=NUMBER, size_type_code="22G1")
    )

    assert events.published == []
    assert uow.committed is True


def test_amending_an_unknown_container_is_refused(
    uow: FakeRegistryUnitOfWork,
) -> None:
    with pytest.raises(ContainerNotFound):
        AmendContainerDetails(uow).execute(
            AmendContainerDetailsCommand(
                container_number=MISSING, size_type_code="22G1"
            )
        )

    assert uow.committed is False
