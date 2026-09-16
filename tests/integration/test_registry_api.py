"""End-to-end tests over HTTP, against the real app."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

NUMBER = "CSQU3054383"
OTHER = "MSCU1234566"


def register(client: TestClient, **overrides: Any) -> Any:
    payload: dict[str, Any] = {
        "container_number": NUMBER,
        "size_type_code": "22G1",
        "cleanliness": "CLEAN",
        "structural": "SOUND",
    }
    payload.update(overrides)
    return client.post("/api/v1/containers", json=payload)


# --------------------------------------------------------------------------- #
# Registering                                                                  #
# --------------------------------------------------------------------------- #
def test_registering_a_container(client: TestClient) -> None:
    response = register(client, size_type_code="45R1", food_certified=True)

    assert response.status_code == 201
    body = response.json()
    assert body["number"] == NUMBER
    assert body["formatted_number"] == "CSQU 305438 3"
    assert body["owner_code"] == "CSQ"
    assert body["equipment_category"] == "U"
    assert body["serial_number"] == "305438"
    assert body["check_digit"] == 3
    assert body["size_type_code"] == "45R1"
    assert body["size_label"] == "40ft HC"
    assert body["container_type"] == "REEFER"
    assert body["cargo_grade"] == "FOOD_GRADE"
    assert body["is_available_for_loading"] is True
    assert body["identified_by"] == "OCR"
    assert body["inspection_count"] == 0


def test_a_messy_ocr_read_is_accepted_and_normalised(client: TestClient) -> None:
    response = register(client, container_number="csqu 305438 3", size_type_code="22g1")

    assert response.status_code == 201
    assert response.json()["number"] == NUMBER
    assert response.json()["size_type_code"] == "22G1"


def test_naming_an_inspector_records_the_first_inspection(
    client: TestClient,
) -> None:
    response = register(client, inspected_by="J. Ramirez", notes="seal intact")

    assert response.status_code == 201
    assert response.json()["inspection_count"] == 1


def test_the_api_never_lets_a_dirty_box_be_food_grade(client: TestClient) -> None:
    response = register(client, cleanliness="DIRTY", food_certified=True)

    assert response.status_code == 201
    assert response.json()["cargo_grade"] == "NOT_SUITABLE"
    assert response.json()["is_available_for_loading"] is False


def test_registering_the_same_container_twice_is_a_conflict(
    client: TestClient,
) -> None:
    assert register(client).status_code == 201

    response = register(client)

    assert response.status_code == 409
    assert response.json()["code"] == "container_already_registered"
    assert NUMBER in response.json()["detail"]


def test_a_bad_check_digit_is_rejected(client: TestClient) -> None:
    response = register(client, container_number="CSQU3054384")

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_container_number"
    assert "check digit must be 3" in body["detail"]


def test_an_unknown_size_type_is_rejected(client: TestClient) -> None:
    response = register(client, size_type_code="ZZZZ")

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_size_type_code"


def test_a_missing_field_is_a_schema_error(client: TestClient) -> None:
    response = client.post("/api/v1/containers", json={"container_number": NUMBER})
    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# Reading                                                                      #
# --------------------------------------------------------------------------- #
def test_fetching_a_container_with_its_history(client: TestClient) -> None:
    register(client, inspected_by="J. Ramirez")

    response = client.get(f"/api/v1/containers/{NUMBER}")

    assert response.status_code == 200
    body = response.json()
    assert body["container"]["number"] == NUMBER
    assert len(body["inspections"]) == 1
    assert body["inspections"][0]["inspected_by"] == "J. Ramirez"


def test_fetching_an_unregistered_container_is_a_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/containers/{OTHER}")

    assert response.status_code == 404
    assert response.json()["code"] == "container_not_found"


def test_listing_containers(client: TestClient) -> None:
    register(client)
    register(client, container_number=OTHER)

    response = client.get("/api/v1/containers")

    assert response.status_code == 200
    assert {c["number"] for c in response.json()} == {NUMBER, OTHER}


def test_listing_pages(client: TestClient) -> None:
    register(client)
    register(client, container_number=OTHER)

    first = client.get("/api/v1/containers", params={"limit": 1, "offset": 0})
    second = client.get("/api/v1/containers", params={"limit": 1, "offset": 1})

    assert len(first.json()) == 1
    assert len(second.json()) == 1
    assert first.json()[0]["number"] != second.json()[0]["number"]


def test_an_out_of_range_limit_is_refused(client: TestClient) -> None:
    assert client.get("/api/v1/containers", params={"limit": 0}).status_code == 422
    assert client.get("/api/v1/containers", params={"limit": 500}).status_code == 422


# --------------------------------------------------------------------------- #
# Inspections                                                                  #
# --------------------------------------------------------------------------- #
def test_recording_an_inspection_updates_the_condition(client: TestClient) -> None:
    register(client)

    response = client.post(
        f"/api/v1/containers/{NUMBER}/inspections",
        json={
            "inspected_by": "J. Ramirez",
            "cleanliness": "CLEAN",
            "structural": "DAMAGED",
            "notes": "dented rear door",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["structural"] == "DAMAGED"
    assert body["cargo_grade"] == "NOT_SUITABLE"
    assert body["is_available_for_loading"] is False
    assert body["inspection_count"] == 1
    assert body["last_inspected_at"] is not None


def test_inspection_history_is_newest_first(client: TestClient) -> None:
    register(client)
    for index in range(3):
        client.post(
            f"/api/v1/containers/{NUMBER}/inspections",
            json={
                "inspected_by": f"inspector-{index}",
                "cleanliness": "CLEAN",
                "structural": "SOUND",
                "inspected_at": f"2026-09-15T0{index}:00:00+00:00",
            },
        )

    response = client.get(f"/api/v1/containers/{NUMBER}/inspections")

    assert response.status_code == 200
    assert [i["inspected_by"] for i in response.json()] == [
        "inspector-2",
        "inspector-1",
        "inspector-0",
    ]


def test_a_timestamp_without_an_offset_is_read_as_utc(client: TestClient) -> None:
    register(client)

    response = client.post(
        f"/api/v1/containers/{NUMBER}/inspections",
        json={
            "inspected_by": "J. Ramirez",
            "cleanliness": "CLEAN",
            "structural": "SOUND",
            "inspected_at": "2026-09-15T09:30:00",
        },
    )

    assert response.status_code == 201
    history = client.get(f"/api/v1/containers/{NUMBER}/inspections").json()
    assert history[0]["inspected_at"].startswith("2026-09-15T09:30:00")


def test_inspecting_an_unregistered_container_is_a_404(client: TestClient) -> None:
    response = client.post(
        f"/api/v1/containers/{OTHER}/inspections",
        json={
            "inspected_by": "J. Ramirez",
            "cleanliness": "CLEAN",
            "structural": "SOUND",
        },
    )

    assert response.status_code == 404
    assert response.json()["code"] == "container_not_found"


def test_an_inspection_needs_an_inspector(client: TestClient) -> None:
    register(client)

    response = client.post(
        f"/api/v1/containers/{NUMBER}/inspections",
        json={"inspected_by": "", "cleanliness": "CLEAN", "structural": "SOUND"},
    )

    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# Amending                                                                     #
# --------------------------------------------------------------------------- #
def test_correcting_a_misread_size_type(client: TestClient) -> None:
    register(client, size_type_code="45G1")

    response = client.patch(
        f"/api/v1/containers/{NUMBER}", json={"size_type_code": "L5G1"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["size_type_code"] == "L5G1"
    assert body["length_ft"] == 45
    assert body["size_label"] == "45ft HC"


def test_amending_an_unregistered_container_is_a_404(client: TestClient) -> None:
    response = client.patch(
        f"/api/v1/containers/{OTHER}", json={"size_type_code": "22G1"}
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Read validation                                                              #
# --------------------------------------------------------------------------- #
def test_validating_a_good_read(client: TestClient) -> None:
    response = client.post(
        "/api/v1/container-numbers/validate",
        json={"container_number": "csqu 305438 3"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_valid"] is True
    assert body["number"] == NUMBER
    assert body["formatted_number"] == "CSQU 305438 3"
    assert body["check_digit"] == 3
    assert body["expected_check_digit"] == 3
    assert body["error"] is None


def test_validating_a_misread_last_digit_suggests_the_right_one(
    client: TestClient,
) -> None:
    """The point of the endpoint: say which character OCR probably got wrong."""
    response = client.post(
        "/api/v1/container-numbers/validate",
        json={"container_number": "CSQU3054387"},
    )

    body = response.json()
    assert body["is_valid"] is False
    assert body["expected_check_digit"] == 3
    assert "check digit must be 3" in body["error"]


def test_validating_unreadable_text(client: TestClient) -> None:
    response = client.post(
        "/api/v1/container-numbers/validate", json={"container_number": "CS?U3054"}
    )

    body = response.json()
    assert body["is_valid"] is False
    assert body["expected_check_digit"] is None
    assert body["number"] is None


# --------------------------------------------------------------------------- #
# Wiring                                                                       #
# --------------------------------------------------------------------------- #
def test_health_and_docs_still_work(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "healthy"}
    assert client.get("/openapi.json").status_code == 200
