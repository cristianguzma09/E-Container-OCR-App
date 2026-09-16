"""Public surface of the registry domain.

Consumers outside the domain (use cases, the ACL, adapters) import from here.
Inside the domain, modules import each other by full path so this facade never
takes part in an import cycle.
"""

from src.context.registry.domain.errors import (
    InvalidContainerNumber,
    InvalidSizeTypeCode,
)
from src.context.registry.domain.events.container_events import (
    ContainerConditionChanged,
    ContainerIdentified,
    ContainerSizeTypeCorrected,
    InspectionRecorded,
)
from src.context.registry.domain.model.condition import (
    CargoGrade,
    Cleanliness,
    Condition,
    StructuralState,
)
from src.context.registry.domain.model.container import Container, IdentificationSource
from src.context.registry.domain.model.container_number import ContainerNumber
from src.context.registry.domain.model.inspection import Inspection
from src.context.registry.domain.model.size_type import ContainerType, SizeType
from src.context.registry.domain.port.container_repository import ContainerRepository
from src.context.registry.domain.port.inspection_repository import InspectionRepository
from src.context.registry.domain.services.condition_grading_policy import (
    ConditionGradingPolicy,
)
from src.shared_kernel.iso6346 import calculate_check_digit

__all__ = [
    "CargoGrade",
    "Cleanliness",
    "Condition",
    "ConditionGradingPolicy",
    "Container",
    "ContainerConditionChanged",
    "ContainerIdentified",
    "ContainerNumber",
    "ContainerRepository",
    "ContainerSizeTypeCorrected",
    "ContainerType",
    "IdentificationSource",
    "Inspection",
    "InspectionRecorded",
    "InspectionRepository",
    "InvalidContainerNumber",
    "InvalidSizeTypeCode",
    "SizeType",
    "StructuralState",
    "calculate_check_digit",
]
