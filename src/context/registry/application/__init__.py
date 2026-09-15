"""Public surface of the registry application layer.

The API layer and the composition root import from here. Inside the layer,
modules import each other by full path so this facade stays out of any cycle.
"""

from src.context.registry.application.acl.recognition_translator import (
    DEFAULT_MINIMUM_CONFIDENCE,
    RecognitionOutcome,
    RecognitionTranslator,
)
from src.context.registry.application.dto import (
    AmendContainerDetailsCommand,
    ConditionObservation,
    ContainerDetailView,
    ContainerView,
    InspectionView,
    RecordInspectionCommand,
    RegisterContainerCommand,
)
from src.context.registry.application.errors import (
    ApplicationError,
    ContainerAlreadyRegistered,
    ContainerNotFound,
)
from src.context.registry.application.unit_of_work import RegistryUnitOfWork
from src.context.registry.application.use_cases.amend_container_details import (
    AmendContainerDetails,
)
from src.context.registry.application.use_cases.queries import (
    ContainerQuery,
    GetContainer,
    GetInspectionHistory,
    InspectionHistoryQuery,
    ListContainers,
    PagedQuery,
)
from src.context.registry.application.use_cases.record_inspection import RecordInspection
from src.context.registry.application.use_cases.register_container import (
    RegisterContainerFromRecognition,
)

__all__ = [
    "DEFAULT_MINIMUM_CONFIDENCE",
    "AmendContainerDetails",
    "AmendContainerDetailsCommand",
    "ApplicationError",
    "ConditionObservation",
    "ContainerAlreadyRegistered",
    "ContainerDetailView",
    "ContainerNotFound",
    "ContainerQuery",
    "ContainerView",
    "GetContainer",
    "GetInspectionHistory",
    "InspectionHistoryQuery",
    "InspectionView",
    "ListContainers",
    "PagedQuery",
    "RecognitionOutcome",
    "RecognitionTranslator",
    "RecordInspection",
    "RecordInspectionCommand",
    "RegisterContainerCommand",
    "RegisterContainerFromRecognition",
    "RegistryUnitOfWork",
]
