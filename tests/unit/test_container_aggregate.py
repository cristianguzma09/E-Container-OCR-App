"""Unit tests for the Container aggregate root."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.context.registry.domain import (
    CargoGrade,
    Condition,
    Container,
    ContainerConditionChanged,
    ContainerIdentified,
    ContainerSizeTypeCorrected,
    ContainerNumber,
    ContainerType,
    IdentificationSource,
    Inspection,
    InspectionRecorded,
    SizeType,
)
from src.shared_kernel.domain import BusinessRuleViolation

NUMBER = "CSQU3054383"
OTHER_NUMBER = "MSCU1234566"
NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)


def build_container(
    *,
    number: str = NUMBER,
    code: str = "22G1",
    condition: Condition | None = None,
    source: IdentificationSource = IdentificationSource.OCR,
) -> Container:
    return Container.identify(
        number=ContainerNumber.parse(number),
        size_type=SizeType(code),
        condition=condition or Condition.good_for_general_cargo(),
        source=source,
        identified_at=NOW,
    )


def build_inspection(
    condition: Condition, *, at: datetime = NOW, by: str = "J. Ramirez"
) -> Inspection:
    return Inspection.record(condition=condition, inspected_by=by, inspected_at=at)


# --------------------------------------------------------------------------- #
# Identification                                                               #
# --------------------------------------------------------------------------- #
def test_identify_records_the_container_identified_event() -> None:
    container = build_container()

    events = container.pull_events()
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, ContainerIdentified)
    assert event.container_number == NUMBER
    assert event.size_type_code == "22G1"
    assert event.source == "OCR"


def test_identify_exposes_the_serialisable_fields_the_frontend_needs() -> None:
    container = build_container(code="45R1")

    assert container.number.value == NUMBER
    assert container.number.owner_prefix == "CSQU"
    assert container.number.check_digit == 3
    assert container.size_label == "40ft HC"
    assert container.container_type is ContainerType.REEFER
    assert container.condition.cargo_grade is CargoGrade.GENERAL_CARGO


def test_a_container_is_identified_by_its_number() -> None:
    a = build_container()
    b = build_container(condition=Condition.dirty())
    assert a == b
    assert hash(a) == hash(b)
    assert a != build_container(number=OTHER_NUMBER)


def test_identification_source_defaults_to_ocr_and_can_be_overridden() -> None:
    assert build_container().identified_by is IdentificationSource.OCR
    manual = build_container(source=IdentificationSource.MANUAL)
    assert manual.identified_by is IdentificationSource.MANUAL
    assert manual.pull_events()[0].source == "MANUAL"


def test_a_new_container_starts_with_no_inspections() -> None:
    container = build_container()
    assert container.inspections == ()
    assert container.latest_inspection is None


# --------------------------------------------------------------------------- #
# Recording inspections                                                        #
# --------------------------------------------------------------------------- #
def test_recording_an_inspection_adopts_its_condition() -> None:
    container = build_container()
    container.pull_events()

    container.record_inspection(build_inspection(Condition.damaged()))

    assert container.condition == Condition.damaged()
    assert container.is_available_for_loading is False
    assert container.latest_inspection is not None
    assert container.latest_inspection.inspected_by == "J. Ramirez"


def test_recording_an_inspection_emits_inspection_recorded() -> None:
    container = build_container()
    container.pull_events()
    inspection = build_inspection(Condition.good_for_food_cargo())

    container.record_inspection(inspection)
    events = container.pull_events()

    recorded = next(e for e in events if isinstance(e, InspectionRecorded))
    assert recorded.container_number == NUMBER
    assert recorded.inspection_id == inspection.id
    assert recorded.cargo_grade is CargoGrade.FOOD_GRADE
    assert recorded.inspected_by == "J. Ramirez"


def test_a_change_of_grade_also_emits_container_condition_changed() -> None:
    container = build_container()  # starts GENERAL_CARGO
    container.pull_events()

    container.record_inspection(build_inspection(Condition.dirty()))
    events = container.pull_events()

    changed = next(e for e in events if isinstance(e, ContainerConditionChanged))
    assert changed.previous_grade is CargoGrade.GENERAL_CARGO
    assert changed.new_grade is CargoGrade.NOT_SUITABLE


def test_an_inspection_confirming_the_same_grade_does_not_emit_a_change() -> None:
    container = build_container()  # starts GENERAL_CARGO
    container.pull_events()

    container.record_inspection(build_inspection(Condition.good_for_general_cargo()))
    events = container.pull_events()

    assert any(isinstance(e, InspectionRecorded) for e in events)
    assert not any(isinstance(e, ContainerConditionChanged) for e in events)


def test_the_same_inspection_cannot_be_recorded_twice() -> None:
    container = build_container()
    inspection = build_inspection(Condition.dirty())
    container.record_inspection(inspection)

    with pytest.raises(BusinessRuleViolation) as excinfo:
        container.record_inspection(inspection)
    assert excinfo.value.rule == "inspection_already_recorded"


def test_history_is_returned_newest_first() -> None:
    container = build_container()
    first = build_inspection(Condition.dirty(), at=NOW)
    second = build_inspection(Condition.good_for_general_cargo(), at=NOW + timedelta(days=1))

    container.record_inspection(first)
    container.record_inspection(second)

    assert [i.id for i in container.inspections] == [second.id, first.id]
    assert container.latest_inspection is not None
    assert container.latest_inspection.id == second.id


def test_a_late_arriving_older_inspection_is_kept_but_does_not_override() -> None:
    container = build_container()
    newest = build_inspection(Condition.good_for_food_cargo(), at=NOW + timedelta(days=2))
    container.record_inspection(newest)
    container.pull_events()

    backfilled = build_inspection(Condition.damaged(), at=NOW)
    container.record_inspection(backfilled)
    events = container.pull_events()

    assert container.condition == Condition.good_for_food_cargo()
    assert len(container.inspections) == 2
    assert any(isinstance(e, InspectionRecorded) for e in events)
    assert not any(isinstance(e, ContainerConditionChanged) for e in events)


def test_an_inspection_must_name_its_inspector() -> None:
    with pytest.raises(BusinessRuleViolation) as excinfo:
        Inspection.record(condition=Condition.dirty(), inspected_by="   ")
    assert excinfo.value.rule == "inspection_needs_an_inspector"


# --------------------------------------------------------------------------- #
# Correcting a bad read                                                        #
# --------------------------------------------------------------------------- #
def test_correcting_the_size_type_emits_an_event() -> None:
    container = build_container(code="45G1")  # OCR read a 40ft high cube
    container.pull_events()

    container.correct_size_type(SizeType("L5G1"))  # it was really a 45-footer
    events = container.pull_events()

    assert container.size_type == SizeType("L5G1")
    assert container.size_label == "45ft HC"
    corrected = next(e for e in events if isinstance(e, ContainerSizeTypeCorrected))
    assert corrected.previous_code == "45G1"
    assert corrected.new_code == "L5G1"


def test_correcting_to_the_same_size_type_is_a_no_op() -> None:
    container = build_container(code="22G1")
    container.pull_events()

    container.correct_size_type(SizeType("22G1"))

    assert container.pull_events() == []
