"""End-to-end tests for the OCR capture endpoints."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from src.context.recognition.infrastructure.ocr.stub_engine import StubOcrEngine
from src.context.recognition.infrastructure.storage.local_image_store import (
    LocalImageStore,
)

VALID = "CSQU3054383"
JPEG = b"\xff\xd8\xff\xe0" + b"fake jpeg payload" * 8


def upload(client: TestClient, *, content_type: str = "image/jpeg", data: bytes = JPEG):
    return client.post(
        "/api/v1/recognitions",
        files={"image": ("capture.jpg", data, content_type)},
        data={"submitted_by": "gate-1"},
    )


# --------------------------------------------------------------------------- #
# Upload                                                                       #
# --------------------------------------------------------------------------- #
def test_uploading_returns_a_pending_job_immediately(client: TestClient) -> None:
    """202 with a job, not the reading - the camera must not wait on Paddle."""
    response = upload(client)

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "PENDING"
    assert body["container_number"] is None
    assert body["submitted_by"] == "gate-1"
    assert uuid.UUID(body["id"])


def test_the_image_is_written_to_the_store(
    client: TestClient, image_store: LocalImageStore
) -> None:
    body = upload(client).json()
    assert image_store.load(body["image_ref"]) == JPEG


def test_an_unsupported_file_type_is_refused(client: TestClient) -> None:
    response = client.post(
        "/api/v1/recognitions",
        files={"image": ("notes.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_image"


def test_an_empty_upload_is_refused(client: TestClient) -> None:
    response = upload(client, data=b"")
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_image"


# --------------------------------------------------------------------------- #
# Background processing                                                        #
# --------------------------------------------------------------------------- #
def test_the_job_is_read_in_the_background_and_then_polls_as_completed(
    client: TestClient,
) -> None:
    job_id = upload(client).json()["id"]

    result = client.get(f"/api/v1/recognitions/{job_id}")

    assert result.status_code == 200
    body = result.json()
    assert body["status"] == "COMPLETED"
    assert body["container_number"] == VALID
    assert body["check_digit_valid"] is True
    assert body["repaired"] is False
    assert body["needs_review"] is False
    assert body["completed_at"] is not None


def test_a_number_painted_across_lines_is_assembled(
    client: TestClient, ocr_engine: StubOcrEngine
) -> None:
    ocr_engine.set_reading("MAERSK", "CSQU", "305438", "3", "22G1")

    job_id = upload(client).json()["id"]
    body = client.get(f"/api/v1/recognitions/{job_id}").json()

    assert body["status"] == "COMPLETED"
    assert body["container_number"] == VALID


def test_a_repaired_read_is_offered_but_held_for_review(
    client: TestClient, ocr_engine: StubOcrEngine
) -> None:
    ocr_engine.set_reading("C5QU3054383")

    job_id = upload(client).json()["id"]
    body = client.get(f"/api/v1/recognitions/{job_id}").json()

    assert body["status"] == "NEEDS_REVIEW"
    assert body["needs_review"] is True
    assert body["container_number"] is None  # never presented as the answer
    assert body["candidates"][0]["value"] == VALID
    assert body["candidates"][0]["repaired"] is True
    assert body["candidates"][0]["needs_human_confirmation"] is True


def test_a_wrong_check_digit_reports_what_it_should_have_been(
    client: TestClient, ocr_engine: StubOcrEngine
) -> None:
    ocr_engine.set_reading("CSQU3054387")

    job_id = upload(client).json()["id"]
    body = client.get(f"/api/v1/recognitions/{job_id}").json()

    assert body["status"] == "NEEDS_REVIEW"
    candidate = body["candidates"][0]
    assert candidate["check_digit_valid"] is False
    assert candidate["expected_check_digit"] == 3


def test_an_unreadable_photo_needs_review(
    client: TestClient, ocr_engine: StubOcrEngine
) -> None:
    ocr_engine.set_reading("HAMBURG SUD", "MAX GROSS 30480 KG")

    job_id = upload(client).json()["id"]
    body = client.get(f"/api/v1/recognitions/{job_id}").json()

    assert body["status"] == "NEEDS_REVIEW"
    assert body["candidates"] == []
    assert body["failure_reason"] is None
    assert len(body["fragments"]) == 2


def test_a_broken_engine_fails_the_job(
    client: TestClient, ocr_engine: StubOcrEngine
) -> None:
    ocr_engine._fail_with = "model weights not found"

    job_id = upload(client).json()["id"]
    body = client.get(f"/api/v1/recognitions/{job_id}").json()

    assert body["status"] == "FAILED"
    assert "model weights not found" in body["failure_reason"]


def test_every_fragment_read_is_kept_for_the_reviewer(
    client: TestClient, ocr_engine: StubOcrEngine
) -> None:
    ocr_engine.set_reading("MAERSK", VALID, "22G1")

    job_id = upload(client).json()["id"]
    body = client.get(f"/api/v1/recognitions/{job_id}").json()

    assert [f["text"] for f in body["fragments"]] == ["MAERSK", VALID, "22G1"]


# --------------------------------------------------------------------------- #
# Polling and the review queue                                                 #
# --------------------------------------------------------------------------- #
def test_polling_an_unknown_job_is_a_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/recognitions/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["code"] == "recognition_job_not_found"


def test_a_malformed_job_id_is_a_schema_error(client: TestClient) -> None:
    assert client.get("/api/v1/recognitions/not-a-uuid").status_code == 422


def test_the_review_queue_lists_only_jobs_needing_a_person(
    client: TestClient, ocr_engine: StubOcrEngine
) -> None:
    upload(client)  # clean read -> COMPLETED
    ocr_engine.set_reading("C5QU3054383")
    upload(client)  # repaired -> NEEDS_REVIEW
    ocr_engine.set_reading("nothing legible")
    upload(client)  # unreadable -> NEEDS_REVIEW

    queue = client.get("/api/v1/recognitions", params={"status": "NEEDS_REVIEW"})
    done = client.get("/api/v1/recognitions", params={"status": "COMPLETED"})
    everything = client.get("/api/v1/recognitions")

    assert len(queue.json()) == 2
    assert len(done.json()) == 1
    assert len(everything.json()) == 3


def test_an_unknown_status_filter_is_refused(client: TestClient) -> None:
    response = client.get("/api/v1/recognitions", params={"status": "BANANA"})
    assert response.status_code == 422


def test_listing_pages(client: TestClient) -> None:
    for _ in range(3):
        upload(client)

    first = client.get("/api/v1/recognitions", params={"limit": 2, "offset": 0})
    second = client.get("/api/v1/recognitions", params={"limit": 2, "offset": 2})

    assert len(first.json()) == 2
    assert len(second.json()) == 1


# --------------------------------------------------------------------------- #
# Persistence round trip                                                       #
# --------------------------------------------------------------------------- #
def test_candidates_and_fragments_survive_the_database(
    client: TestClient, ocr_engine: StubOcrEngine
) -> None:
    """They are stored as JSON, so the mapping is worth proving both ways."""
    ocr_engine.set_reading("MAERSK", "C5QU3054383")

    job_id = upload(client).json()["id"]
    body = client.get(f"/api/v1/recognitions/{job_id}").json()

    candidate = body["candidates"][0]
    assert candidate["value"] == VALID
    assert candidate["raw_text"] == "C5QU3054383"
    assert candidate["repaired"] is True
    assert candidate["expected_check_digit"] == 3
    assert 0.0 <= candidate["confidence"] <= 1.0
    assert 0.0 <= candidate["score"] <= 1.0
    assert [f["text"] for f in body["fragments"]] == ["MAERSK", "C5QU3054383"]
