"""Use case tests for registering a container."""

from __future__ import annotations

import pytest

from src.context.registry.application import (
    ContainerAlreadyRegistered,
    RegisterContainerCommand,
    RegisterContainerFromRecognition,
)
from src.context.registry.domain import (
    CargoGrade,
    Cleanliness,
    ContainerIdentified,
    IdentificationSource,
    InspectionRecorded,
    InvalidContainerNumber,
    InvalidSizeTypeCode,
    StructuralState,
)
from tests.application.fakes import FakeRegistryUnitOfWork, RecordingEventDispatcher

NUMBER = "CSQU3054383"


@pytest.fixture
def uow() -> FakeRegistryUnitOfWork:
    return FakeRegistryUnitOfWork()


@pytest.fixture
def events() -> RecordingEventDispatcher:
    return RecordingEventDispatcher()


@pytest.fixture
def register(
    uow: FakeRegistryUnitOfWork, events: RecordingEventDispatcher
) -> RegisterContainerFromRecognition:
    return RegisterContainerFromRecognition(uow, events=events)


def command(**overrides: object) -> RegisterContainerCommand:
    defaults = {
        "container_number": NUMBER,
        "size_type_code": "22G1",
        "cleanliness": Cleanliness.CLEAN,
        "structural": StructuralState.SOUND,
    }
    return RegisterContainerCommand(**{**defaults, **overrides})  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Happy path                                                                   #
# --------------------------------------------------------------------------- #
def test_registering_returns_every_field_the_form_needs(
    register: RegisterContainerFromRecognition,
) -> None:
    view = register.execute(command(size_type_code="45R1", food_certified=True))

    assert view.number == NUMBER
    assert view.formatted_number == "CSQU 305438 3"
    assert view.owner_code == "CSQ"
    assert view.equipment_category == "U"
    assert view.serial_number == "305438"
    assert view.check_digit == 3

    assert view.size_type_code == "45R1"
    assert view.size_label == "40ft HC"
    assert view.length_ft == 40
    assert view.is_high_cube is True
    assert view.container_type == "REEFER"

    assert view.cleanliness == "CLEAN"
    assert view.structural == "SOUND"
    assert view.cargo_grade == "FOOD_GRADE"
    assert view.is_available_for_loading is True
    assert view.identified_by == "OCR"


def test_the_container_is_persisted_and_the_transaction_committed(
    register: RegisterContainerFromRecognition, uow: FakeRegistryUnitOfWork
) -> None:
    register.execute(command())

    assert uow.committed is True
    assert NUMBER in uow.stored


def test_messy_ocr_text_is_normalised_on_the_way_in(
    register: RegisterContainerFromRecognition,
) -> None:
    view = register.execute(command(container_number="csqu 305438 3", size_type_code="22g1"))
    assert view.number == NUMBER
    assert view.size_type_code == "22G1"


# --------------------------------------------------------------------------- #
# The grade is derived, never accepted                                         #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("cleanliness", "structural", "food_certified", "expected"),
    [
        (Cleanliness.CLEAN, StructuralState.SOUND, True, "FOOD_GRADE"),
        (Cleanliness.CLEAN, StructuralState.SOUND, False, "GENERAL_CARGO"),
        (Cleanliness.DIRTY, StructuralState.SOUND, True, "NOT_SUITABLE"),
        (Cleanliness.CLEAN, StructuralState.DAMAGED, True, "NOT_SUITABLE"),
    ],
)
def test_the_policy_decides_the_grade_not_the_caller(
    register: RegisterContainerFromRecognition,
    cleanliness: Cleanliness,
    structural: StructuralState,
    food_certified: bool,
    expected: str,
) -> None:
    view = register.execute(
        command(
            cleanliness=cleanliness,
            structural=structural,
            food_certified=food_certified,
        )
    )
    assert view.cargo_grade == expected


def test_a_dirty_box_cannot_be_registered_as_food_grade(
    register: RegisterContainerFromRecognition,
) -> None:
    view = register.execute(
        command(cleanliness=Cleanliness.DIRTY, food_certified=True)
    )
    assert view.cargo_grade == CargoGrade.NOT_SUITABLE
    assert view.is_available_for_loading is False


# --------------------------------------------------------------------------- #
# Provenance                                                                   #
# --------------------------------------------------------------------------- #
def test_naming_an_inspector_records_the_first_inspection(
    register: RegisterContainerFromRecognition, events: RecordingEventDispatcher
) -> None:
    view = register.execute(command(inspected_by="J. Ramirez", notes="seal intact"))

    assert view.inspection_count == 1
    assert view.last_inspected_at == view.identified_at
    assert len(events.of_type(InspectionRecorded)) == 1


def test_an_unattended_ocr_capture_records_no_inspection(
    register: RegisterContainerFromRecognition, events: RecordingEventDispatcher
) -> None:
    view = register.execute(command())

    assert view.inspection_count == 0
    assert view.last_inspected_at is None
    assert events.of_type(InspectionRecorded) == []


def test_the_source_is_carried_through(
    register: RegisterContainerFromRecognition, events: RecordingEventDispatcher
) -> None:
    view = register.execute(command(source=IdentificationSource.MANUAL))

    assert view.identified_by == "MANUAL"
    assert events.of_type(ContainerIdentified)[0].source == "MANUAL"


def test_container_identified_is_published_after_the_commit(
    register: RegisterContainerFromRecognition, events: RecordingEventDispatcher
) -> None:
    register.execute(command())

    identified = events.of_type(ContainerIdentified)
    assert len(identified) == 1
    assert identified[0].container_number == NUMBER
    assert identified[0].size_type_code == "22G1"


# --------------------------------------------------------------------------- #
# Rejections                                                                   #
# --------------------------------------------------------------------------- #
def test_registering_the_same_container_twice_is_refused(
    register: RegisterContainerFromRecognition, uow: FakeRegistryUnitOfWork
) -> None:
    register.execute(command())

    with pytest.raises(ContainerAlreadyRegistered) as excinfo:
        register.execute(command(size_type_code="42G1"))

    assert excinfo.value.container_number == NUMBER


def test_a_refused_duplicate_leaves_the_register_untouched(
    register: RegisterContainerFromRecognition, uow: FakeRegistryUnitOfWork
) -> None:
    register.execute(command())
    original = uow.stored[NUMBER]

    with pytest.raises(ContainerAlreadyRegistered):
        register.execute(command(size_type_code="42G1"))

    assert uow.stored[NUMBER] is original
    assert uow.stored[NUMBER].size_type.code == "22G1"
    assert uow.rolled_back is True


def test_a_bad_check_digit_never_reaches_the_repository(
    register: RegisterContainerFromRecognition, uow: FakeRegistryUnitOfWork
) -> None:
    with pytest.raises(InvalidContainerNumber):
        register.execute(command(container_number="CSQU3054384"))

    assert uow.stored == {}
    assert uow.committed is False


def test_an_unknown_size_type_never_reaches_the_repository(
    register: RegisterContainerFromRecognition, uow: FakeRegistryUnitOfWork
) -> None:
    with pytest.raises(InvalidSizeTypeCode):
        register.execute(command(size_type_code="ZZZZ"))

    assert uow.stored == {}
    assert uow.committed is False
