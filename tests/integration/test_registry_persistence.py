"""Integration tests for the SQLAlchemy adapters."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from src.context.registry.domain import (
    CargoGrade,
    Condition,
    Container,
    ContainerNumber,
    IdentificationSource,
    Inspection,
    SizeType,
)
from src.context.registry.infrastructure.persistence.unit_of_work import (
    SqlAlchemyRegistryUnitOfWork,
)

NUMBER = ContainerNumber.parse("CSQU3054383")
OTHER = ContainerNumber.parse("MSCU1234566")
THIRD = ContainerNumber.parse("TGHU7654320")
AT = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)


def make_container(
    number: ContainerNumber = NUMBER,
    *,
    code: str = "22G1",
    condition: Condition | None = None,
    identified_at: datetime = AT,
) -> Container:
    return Container.identify(
        number=number,
        size_type=SizeType(code),
        condition=condition or Condition.good_for_general_cargo(),
        source=IdentificationSource.OCR,
        identified_at=identified_at,
    )


# --------------------------------------------------------------------------- #
# Round trip                                                                   #
# --------------------------------------------------------------------------- #
def test_a_saved_container_comes_back_intact(
    uow: SqlAlchemyRegistryUnitOfWork,
) -> None:
    with uow:
        uow.containers.save(make_container(code="45R1"))
        uow.commit()

    with uow:
        loaded = uow.containers.get(NUMBER)

    assert loaded is not None
    assert loaded.number == NUMBER
    assert loaded.number.check_digit == 3
    assert loaded.size_type == SizeType("45R1")
    assert loaded.size_label == "40ft HC"
    assert loaded.condition == Condition.good_for_general_cargo()
    assert loaded.identified_by is IdentificationSource.OCR
    assert loaded.identified_at == AT


def test_timestamps_keep_their_timezone(uow: SqlAlchemyRegistryUnitOfWork) -> None:
    """SQLite drops offsets; the UtcDateTime column type puts them back."""
    lima = timezone(timedelta(hours=-5))
    captured = datetime(2026, 9, 15, 7, 0, tzinfo=lima)

    with uow:
        uow.containers.save(make_container(identified_at=captured))
        uow.commit()

    with uow:
        loaded = uow.containers.get(NUMBER)

    assert loaded is not None
    assert loaded.identified_at.tzinfo is not None
    assert loaded.identified_at == captured
    assert loaded.identified_at.utcoffset() == timedelta(0)


def test_a_reconstituted_container_records_no_events(
    uow: SqlAlchemyRegistryUnitOfWork,
) -> None:
    with uow:
        uow.containers.save(make_container())
        uow.commit()

    with uow:
        loaded = uow.containers.get(NUMBER)

    assert loaded is not None
    assert loaded.has_pending_events is False


def test_an_unknown_container_returns_none(
    uow: SqlAlchemyRegistryUnitOfWork,
) -> None:
    with uow:
        assert uow.containers.get(NUMBER) is None
        assert uow.containers.exists(NUMBER) is False


# --------------------------------------------------------------------------- #
# Updates                                                                      #
# --------------------------------------------------------------------------- #
def test_saving_an_existing_container_updates_it_in_place(
    uow: SqlAlchemyRegistryUnitOfWork,
) -> None:
    with uow:
        uow.containers.save(make_container(code="45G1"))
        uow.commit()

    with uow:
        container = uow.containers.get(NUMBER)
        assert container is not None
        container.correct_size_type(SizeType("L5G1"))
        uow.containers.save(container)
        uow.commit()

    with uow:
        reloaded = uow.containers.get(NUMBER)
        assert reloaded is not None
        assert reloaded.size_type == SizeType("L5G1")
        assert reloaded.size_label == "45ft HC"
        assert len(uow.containers.list()) == 1


def test_inspections_are_persisted_and_ordered_newest_first(
    uow: SqlAlchemyRegistryUnitOfWork,
) -> None:
    with uow:
        container = make_container()
        for index, condition in enumerate(
            [Condition.dirty(), Condition.good_for_food_cargo()]
        ):
            container.record_inspection(
                Inspection.record(
                    condition=condition,
                    inspected_by=f"inspector-{index}",
                    notes=f"note {index}",
                    inspected_at=AT + timedelta(hours=index),
                )
            )
        uow.containers.save(container)
        uow.commit()

    with uow:
        loaded = uow.containers.get(NUMBER)

    assert loaded is not None
    assert loaded.condition.cargo_grade is CargoGrade.FOOD_GRADE
    assert [i.inspected_by for i in loaded.inspections] == [
        "inspector-1",
        "inspector-0",
    ]
    assert loaded.inspections[0].notes == "note 1"


def test_inspections_are_appended_not_rewritten(
    uow: SqlAlchemyRegistryUnitOfWork,
) -> None:
    with uow:
        container = make_container()
        container.record_inspection(
            Inspection.record(
                condition=Condition.dirty(), inspected_by="first", inspected_at=AT
            )
        )
        uow.containers.save(container)
        uow.commit()

    with uow:
        container = uow.containers.get(NUMBER)
        assert container is not None
        container.record_inspection(
            Inspection.record(
                condition=Condition.good_for_general_cargo(),
                inspected_by="second",
                inspected_at=AT + timedelta(hours=1),
            )
        )
        uow.containers.save(container)
        uow.commit()

    with uow:
        reloaded = uow.containers.get(NUMBER)

    assert reloaded is not None
    assert len(reloaded.inspections) == 2
    assert {i.inspected_by for i in reloaded.inspections} == {"first", "second"}


# --------------------------------------------------------------------------- #
# Transactions                                                                 #
# --------------------------------------------------------------------------- #
def test_leaving_the_block_without_committing_discards_the_write(
    uow: SqlAlchemyRegistryUnitOfWork,
) -> None:
    with uow:
        uow.containers.save(make_container())
        # no commit

    with uow:
        assert uow.containers.get(NUMBER) is None


def test_an_exception_inside_the_block_rolls_back(
    uow: SqlAlchemyRegistryUnitOfWork,
) -> None:
    class Boom(Exception):
        pass

    try:
        with uow:
            uow.containers.save(make_container())
            raise Boom
    except Boom:
        pass

    with uow:
        assert uow.containers.exists(NUMBER) is False


def test_the_session_is_closed_on_exit(uow: SqlAlchemyRegistryUnitOfWork) -> None:
    with uow:
        uow.containers.save(make_container())
        uow.commit()

    # The aggregate survives the session because repositories return plain
    # domain objects, not ORM instances.
    with uow:
        loaded = uow.containers.get(NUMBER)
    assert loaded is not None
    assert loaded.size_label == "20ft"


# --------------------------------------------------------------------------- #
# Listing                                                                      #
# --------------------------------------------------------------------------- #
def test_list_returns_newest_identification_first(
    uow: SqlAlchemyRegistryUnitOfWork,
) -> None:
    with uow:
        for index, number in enumerate([NUMBER, OTHER, THIRD]):
            uow.containers.save(
                make_container(number, identified_at=AT + timedelta(hours=index))
            )
        uow.commit()

    with uow:
        listed = uow.containers.list()

    assert [c.number.value for c in listed] == [
        THIRD.value,
        OTHER.value,
        NUMBER.value,
    ]


def test_list_pages(uow: SqlAlchemyRegistryUnitOfWork) -> None:
    with uow:
        for index, number in enumerate([NUMBER, OTHER, THIRD]):
            uow.containers.save(
                make_container(number, identified_at=AT + timedelta(hours=index))
            )
        uow.commit()

    with uow:
        first = uow.containers.list(limit=2, offset=0)
        second = uow.containers.list(limit=2, offset=2)

    assert len(first) == 2
    assert len(second) == 1
    assert {c.number.value for c in first}.isdisjoint(
        {c.number.value for c in second}
    )


# --------------------------------------------------------------------------- #
# Inspection query port                                                        #
# --------------------------------------------------------------------------- #
def test_inspection_repository_reads_history_without_the_aggregate(
    uow: SqlAlchemyRegistryUnitOfWork,
) -> None:
    with uow:
        container = make_container()
        for index in range(3):
            container.record_inspection(
                Inspection.record(
                    condition=Condition.good_for_general_cargo(),
                    inspected_by=f"inspector-{index}",
                    inspected_at=AT + timedelta(hours=index),
                )
            )
        uow.containers.save(container)
        uow.commit()

    with uow:
        history = uow.inspections.list_for_container(NUMBER)
        page = uow.inspections.list_for_container(NUMBER, limit=2, offset=1)
        one = uow.inspections.get(history[0].id)

    assert [i.inspected_by for i in history] == [
        "inspector-2",
        "inspector-1",
        "inspector-0",
    ]
    assert [i.inspected_by for i in page] == ["inspector-1", "inspector-0"]
    assert one is not None
    assert one.inspected_by == "inspector-2"


def test_inspection_repository_on_an_unknown_container_is_empty(
    uow: SqlAlchemyRegistryUnitOfWork,
) -> None:
    with uow:
        assert uow.inspections.list_for_container(NUMBER) == []
