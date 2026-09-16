"""Public surface of the recognition domain.

Consumers outside the domain import from here. Inside it, modules import each
other by full path so this facade never takes part in an import cycle.
"""

from src.context.recognition.domain.errors import (
    InvalidImage,
    OcrEngineFailure,
    RecognitionError,
)
from src.context.recognition.domain.events import (
    RecognitionCompleted,
    RecognitionFailed,
    RecognitionRequested,
)
from src.context.recognition.domain.model.bounding_box import BoundingBox
from src.context.recognition.domain.model.confidence import Confidence
from src.context.recognition.domain.model.container_code_candidate import (
    ContainerCodeCandidate,
)
from src.context.recognition.domain.model.recognition_job import (
    JobStatus,
    RecognitionJob,
)
from src.context.recognition.domain.model.text_fragment import TextFragment
from src.context.recognition.domain.port.image_store import ImageStore
from src.context.recognition.domain.port.ocr_engine import OcrEngine
from src.context.recognition.domain.port.recognition_job_repository import (
    RecognitionJobRepository,
)
from src.context.recognition.domain.services.container_code_extractor import (
    ContainerCodeExtractor,
)

__all__ = [
    "BoundingBox",
    "Confidence",
    "ContainerCodeCandidate",
    "ContainerCodeExtractor",
    "ImageStore",
    "InvalidImage",
    "JobStatus",
    "OcrEngine",
    "OcrEngineFailure",
    "RecognitionCompleted",
    "RecognitionError",
    "RecognitionFailed",
    "RecognitionJob",
    "RecognitionJobRepository",
    "RecognitionRequested",
    "TextFragment",
]
