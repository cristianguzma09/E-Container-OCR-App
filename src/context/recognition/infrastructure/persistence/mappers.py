"""Translation between the recognition job row and the aggregate."""

from __future__ import annotations

from typing import Any

from src.context.recognition.domain import (
    BoundingBox,
    Confidence,
    ContainerCodeCandidate,
    JobStatus,
    RecognitionJob,
    TextFragment,
)
from src.context.recognition.infrastructure.persistence.models import (
    RecognitionJobModel,
)


def _box_to_json(box: BoundingBox | None) -> dict[str, int] | None:
    if box is None:
        return None
    return {
        "left": box.left,
        "top": box.top,
        "width": box.width,
        "height": box.height,
    }


def _box_from_json(data: Any) -> BoundingBox | None:
    if not data:
        return None
    try:
        return BoundingBox(
            left=data["left"],
            top=data["top"],
            width=data["width"],
            height=data["height"],
        )
    except (KeyError, TypeError, ValueError):
        return None


def fragment_to_json(fragment: TextFragment) -> dict[str, Any]:
    return {
        "text": fragment.text,
        "confidence": fragment.confidence.value,
        "box": _box_to_json(fragment.box),
    }


def fragment_from_json(data: dict[str, Any]) -> TextFragment:
    return TextFragment(
        text=data["text"],
        confidence=Confidence(data["confidence"]),
        box=_box_from_json(data.get("box")),
    )


def candidate_to_json(candidate: ContainerCodeCandidate) -> dict[str, Any]:
    return {
        "raw_text": candidate.raw_text,
        "value": candidate.value,
        "confidence": candidate.confidence.value,
        "check_digit_valid": candidate.check_digit_valid,
        "expected_check_digit": candidate.expected_check_digit,
        "repaired": candidate.repaired,
        "box": _box_to_json(candidate.box),
    }


def candidate_from_json(data: dict[str, Any]) -> ContainerCodeCandidate:
    return ContainerCodeCandidate(
        raw_text=data["raw_text"],
        value=data["value"],
        confidence=Confidence(data["confidence"]),
        check_digit_valid=data["check_digit_valid"],
        expected_check_digit=data.get("expected_check_digit"),
        repaired=data.get("repaired", False),
        box=_box_from_json(data.get("box")),
    )


def job_to_domain(model: RecognitionJobModel) -> RecognitionJob:
    return RecognitionJob(
        job_id=model.id,
        image_ref=model.image_ref,
        submitted_at=model.submitted_at,
        submitted_by=model.submitted_by,
        status=JobStatus(model.status),
        fragments=[fragment_from_json(f) for f in model.fragments or []],
        candidates=[candidate_from_json(c) for c in model.candidates or []],
        failure_reason=model.failure_reason,
        completed_at=model.completed_at,
    )


def job_to_model(job: RecognitionJob) -> RecognitionJobModel:
    model = RecognitionJobModel(
        id=job.id,
        image_ref=job.image_ref,
        submitted_at=job.submitted_at,
        submitted_by=job.submitted_by,
    )
    apply_to_model(model, job)
    return model


def apply_to_model(model: RecognitionJobModel, job: RecognitionJob) -> None:
    best = job.best_candidate
    model.status = str(job.status)
    model.completed_at = job.completed_at
    model.failure_reason = job.failure_reason
    model.best_container_number = best.value if best else None
    model.best_confidence = best.confidence.value if best else None
    model.fragments = [fragment_to_json(f) for f in job.fragments]
    model.candidates = [candidate_to_json(c) for c in job.candidates]
