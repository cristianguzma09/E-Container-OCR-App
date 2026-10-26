"""End-to-end tests for the full capture loop over HTTP.

Photo in, container on the register, through the real app.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from src.context.recognition.infrastructure.ocr.stub_engine import StubOcrEngine

VALID = "CSQU3054383"
OTHER = "MSCU1234566"
JPEG = b"\xff\xd8\xff\xe0" + b"fake jpeg payload" * 8


def upload(client: TestClient) -> str:
    response = client.post(
        "/api/v1/recognitions",
        files={"image": ("capture.jpg", JPEG, "image/jpeg")},
        data={"submitted_by": "gate-1"},
    )
    assert response.status_code == 202
    return response.json()["id"]


def confirm(client: TestClient, job_id: str, **overrides: Any):
    payload: dict[str, Any] = {
        "confirmed_by": "J. Ramirez",
        "size_type_code": "22G1",
        "cleanliness": "CLEAN",
        "structural": "SOUND",
    }
    payload.update(overrides)
    return client.post(f"/api/v1/recognitions/{job_id}/confirm", json=payload)


# --------------------------------------------------------------------------- #
# The whole loop in one test                                                   #
# --------------------------------------------------------------------------- #
def test_photo_to_registered_container(client: TestClient) -> None:
    job_id = upload(client)

    response = confirm(client, job_id)

    assert response.status_code == 201
    body = response.json()
    assert body["newly_registered"] is True
    assert body["corrected"] is False
    assert body["job"]["status"] == "CONFIRMED"
    assert body["container"]["number"] == VALID
    assert body["container"]["size_label"] == "20ft"
    assert body["container"]["cargo_grade"] == "GENERAL_CARGO"

    # ...and it is genuinely on the register, reachable on its own URL.
    registered = client.get(f"/api/v1/containers/{VALID}")
    assert registered.status_code == 200
    assert registered.json()["container"]["number"] == VALID
    assert registered.json()["inspections"][0]["inspected_by"] == "J. Ramirez"


def test_the_job_leaves_the_review_queue_once_confirmed(
    client: TestClient, ocr_engine: StubOcrEngine
) -> None:
    ocr_engine.set_reading("C5QU3054383")  # repaired -> NEEDS_REVIEW
    job_id = upload(client)
    assert len(client.get("/api/v1/recognitions", params={"status": "NEEDS_REVIEW"}).json()) == 1

    confirm(client, job_id)

    queue = client.get("/api/v1/recognitions", params={"status": "NEEDS_REVIEW"})
    confirmed = client.get("/api/v1/recognitions", params={"status": "CONFIRMED"})
    assert queue.json() == []
    assert len(confirmed.json()) == 1


def test_the_confirmation_is_persisted_on_the_job(client: TestClient) -> None:
    job_id = upload(client)
    confirm(client, job_id, confirmed_by="A. Silva")

    job = client.get(f"/api/v1/recognitions/{job_id}").json()

    assert job["status"] == "CONFIRMED"
    assert job["confirmed_container_number"] == VALID
    assert job["confirmed_by"] == "A. Silva"
    assert job["confirmed_at"] is not None


# --------------------------------------------------------------------------- #
# Corrections                                                                  #
# --------------------------------------------------------------------------- #
def test_an_operator_correction_registers_the_typed_number(
    client: TestClient,
) -> None:
    job_id = upload(client)

    body = confirm(client, job_id, container_number=OTHER).json()

    assert body["corrected"] is True
    assert body["container"]["number"] == OTHER
    assert body["container"]["identified_by"] == "MANUAL"
    assert client.get(f"/api/v1/containers/{VALID}").status_code == 404
    assert client.get(f"/api/v1/containers/{OTHER}").status_code == 200


def test_an_unreadable_photo_can_be_rescued_by_typing_the_number(
    client: TestClient, ocr_engine: StubOcrEngine
) -> None:
    ocr_engine.set_reading("HAMBURG SUD", "MAX GROSS 30480 KG")
    job_id = upload(client)

    body = confirm(client, job_id, container_number=VALID).json()

    assert body["container"]["number"] == VALID
    assert body["corrected"] is True


def test_an_unreadable_photo_with_no_number_cannot_be_confirmed(
    client: TestClient, ocr_engine: StubOcrEngine
) -> None:
    ocr_engine.set_reading("HAMBURG SUD")
    job_id = upload(client)

    response = confirm(client, job_id)

    assert response.status_code == 409
    assert response.json()["code"] == "capture_not_confirmable"


# --------------------------------------------------------------------------- #
# A box seen twice                                                             #
# --------------------------------------------------------------------------- #
def test_the_same_box_through_the_gate_twice(client: TestClient) -> None:
    confirm(client, upload(client))

    second = confirm(client, upload(client), cleanliness="DIRTY").json()

    assert second["newly_registered"] is False
    assert second["container"]["cargo_grade"] == "NOT_SUITABLE"
    assert second["container"]["inspection_count"] == 2
    assert len(client.get("/api/v1/containers").json()) == 1


# --------------------------------------------------------------------------- #
# Guards                                                                       #
# --------------------------------------------------------------------------- #
def test_confirming_an_unknown_job_is_a_404(client: TestClient) -> None:
    response = confirm(client, str(uuid.uuid4()))

    assert response.status_code == 404
    assert response.json()["code"] == "recognition_job_not_found"


def test_confirming_twice_is_a_conflict(client: TestClient) -> None:
    job_id = upload(client)
    assert confirm(client, job_id).status_code == 201

    response = confirm(client, job_id)

    assert response.status_code == 409
    assert response.json()["code"] == "capture_not_confirmable"


def test_a_failed_job_cannot_be_confirmed(
    client: TestClient, ocr_engine: StubOcrEngine
) -> None:
    ocr_engine._fail_with = "model weights missing"
    job_id = upload(client)

    response = confirm(client, job_id)

    assert response.status_code == 409


def test_an_override_failing_its_check_digit_is_refused(
    client: TestClient,
) -> None:
    job_id = upload(client)

    response = confirm(client, job_id, container_number="CSQU3054384")

    assert response.status_code == 409
    assert "check digit" in response.json()["detail"]
    assert client.get("/api/v1/containers").json() == []


def test_an_unknown_size_type_is_refused(client: TestClient) -> None:
    job_id = upload(client)

    response = confirm(client, job_id, size_type_code="ZZZZ")

    assert response.status_code in (409, 422)
    assert client.get("/api/v1/containers").json() == []


def test_a_confirmation_must_name_who_signed_it(client: TestClient) -> None:
    response = confirm(client, upload(client), confirmed_by="")
    assert response.status_code == 422
