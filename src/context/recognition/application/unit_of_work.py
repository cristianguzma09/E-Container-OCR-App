"""The recognition context's transactional boundary."""

from __future__ import annotations

from src.context.recognition.domain import RecognitionJobRepository
from src.shared_kernel.application import UnitOfWork


class RecognitionUnitOfWork(UnitOfWork):
    """Binds the job repository to one transaction.

    Note what is *not* here: the image store and the OCR engine. Neither is
    transactional, and OCR takes seconds, so both are used outside the
    ``with`` block rather than holding a database transaction open while a
    model runs.
    """

    jobs: RecognitionJobRepository
