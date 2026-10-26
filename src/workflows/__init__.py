"""Workflows that span more than one bounded context.

Everything under ``src/context`` is deliberately ignorant of its neighbours:
the Registry does not import Recognition, and Recognition does not import the
Registry. That is what keeps each one free to change its own model.

Some real operations still need both. Confirming a capture is one: it signs
off a reading in Recognition *and* puts a container on the Registry. Rather
than let one context reach into the other, those operations live here, one
level up, where knowing both is the explicit job of the module.

A workflow is composition, like the API layer - it orchestrates use cases and
owns no model of its own.
"""

from src.workflows.confirm_capture import (
    CaptureNotConfirmable,
    ConfirmCapture,
    ConfirmCaptureCommand,
    ConfirmedCaptureView,
)

__all__ = [
    "CaptureNotConfirmable",
    "ConfirmCapture",
    "ConfirmCaptureCommand",
    "ConfirmedCaptureView",
]
