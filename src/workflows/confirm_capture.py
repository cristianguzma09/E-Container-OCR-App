"""Turn a signed-off OCR reading into a registered container."""

from __future__ import annotations

from dataclasses import dataclass, replace
from uuid import UUID

from src.context.recognition.application import (
    RecognitionJobNotFound,
    RecognitionJobView,
    RecognitionUnitOfWork,
)
from src.context.registry.application import (
    ConditionObservation,
    ContainerView,
    RecognitionOutcome,
    RecognitionTranslator,
    RecordInspection,
    RecordInspectionCommand,
    RegisterContainerFromRecognition,
    RegistryUnitOfWork,
)
from src.context.registry.domain import (
    Cleanliness,
    ConditionGradingPolicy,
    ContainerNumber,
    IdentificationSource,
    StructuralState,
)
from src.shared_kernel.application import EventDispatcher


class CaptureNotConfirmable(Exception):
    """The job cannot be signed off as it stands."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True, kw_only=True)
class ConfirmCaptureCommand:
    """What an operator submits from the capture screen.

    ``container_number`` is the override. Left out, the engine's best reading
    is accepted; supplied, it wins - which is how a NEEDS_REVIEW job gets
    corrected.
    """

    job_id: UUID
    confirmed_by: str
    size_type_code: str
    cleanliness: Cleanliness
    structural: StructuralState
    container_number: str | None = None
    food_certified: bool = False
    notes: str | None = None


@dataclass(frozen=True, kw_only=True)
class ConfirmedCaptureView:
    job: RecognitionJobView
    container: ContainerView
    newly_registered: bool
    corrected: bool


class ConfirmCapture:
    """Sign off a reading, register the container, and link the two.

    The one place that holds both units of work. They commit separately -
    there is no distributed transaction here - so the order matters: the
    container is written first and the job is marked afterwards. If the second
    step fails, the container exists and the job is still in the queue, so a
    retry simply runs again and takes the "already registered" path below.
    The reverse order would leave a job claiming a container that was never
    written, which is the worse of the two failures.
    """

    def __init__(
        self,
        recognition: RecognitionUnitOfWork,
        registry: RegistryUnitOfWork,
        *,
        translator: RecognitionTranslator | None = None,
        grading_policy: ConditionGradingPolicy | None = None,
        events: EventDispatcher | None = None,
    ) -> None:
        self._recognition = recognition
        self._registry = registry
        self._translator = translator or RecognitionTranslator()
        self._policy = grading_policy or ConditionGradingPolicy()
        self._events = events or EventDispatcher()

    def execute(self, request: ConfirmCaptureCommand) -> ConfirmedCaptureView:
        read, image_ref = self._inspect_job(request.job_id)

        number = request.container_number or read
        if not number:
            raise CaptureNotConfirmable(
                "the engine read no container number and none was supplied"
            )

        command = self._translate(request, number, image_ref)
        corrected = read != command.container_number
        if corrected:
            # A person typed this, so it is no longer an OCR identification.
            command = replace(command, source=IdentificationSource.MANUAL)

        container, newly_registered = self._put_on_the_register(request, command)
        job = self._sign_off(request, command.container_number)

        return ConfirmedCaptureView(
            job=RecognitionJobView.of(job),
            container=container,
            newly_registered=newly_registered,
            corrected=corrected,
        )

    # -- steps -------------------------------------------------------------
    def _inspect_job(self, job_id: UUID) -> tuple[str | None, str]:
        with self._recognition as uow:
            job = uow.jobs.get(job_id)
            if job is None:
                raise RecognitionJobNotFound(job_id)
            if not job.can_be_confirmed:
                raise CaptureNotConfirmable(
                    f"job {job_id} is {job.status}; only a job that produced a "
                    f"reading can be signed off"
                )
            best = job.best_candidate
            return (best.value if best else None), job.image_ref

    def _translate(
        self, request: ConfirmCaptureCommand, number: str, image_ref: str
    ):
        """Run the reading through the registry's anti-corruption layer.

        Confidence is pinned at 1.0 rather than carried over from the engine.
        The translator's confidence threshold exists to stop a shaky
        *unattended* read reaching the register; once a person has put their
        name to the number that gate has been answered by a better authority.
        The check digit and the size-type are still validated, which is the
        part that catches a typo.
        """
        outcome = RecognitionOutcome(
            job_id=str(request.job_id),
            container_number=number,
            size_type_code=request.size_type_code,
            confidence=1.0,
            image_ref=image_ref,
        )
        observation = ConditionObservation(
            cleanliness=request.cleanliness,
            structural=request.structural,
            food_certified=request.food_certified,
            inspected_by=request.confirmed_by,
            notes=request.notes,
            evidence_image_ref=image_ref,
        )

        result = self._translator.translate(outcome, observation)
        if result.is_failure:
            raise CaptureNotConfirmable(result.error)
        return result.unwrap()

    def _put_on_the_register(
        self, request: ConfirmCaptureCommand, command
    ) -> tuple[ContainerView, bool]:
        """Register the container, or inspect it again if it is already known.

        A box coming through the gate a second time is normal, not an error.
        The first capture registers it; every one after that is an inspection
        against the container already on file.
        """
        number = ContainerNumber.parse(command.container_number)
        with self._registry as uow:
            already_known = uow.containers.exists(number)

        if already_known:
            container = RecordInspection(
                self._registry, grading_policy=self._policy, events=self._events
            ).execute(
                RecordInspectionCommand(
                    container_number=command.container_number,
                    inspected_by=request.confirmed_by,
                    cleanliness=request.cleanliness,
                    structural=request.structural,
                    food_certified=request.food_certified,
                    notes=request.notes,
                    evidence_image_ref=command.evidence_image_ref,
                )
            )
            return container, False

        container = RegisterContainerFromRecognition(
            self._registry, grading_policy=self._policy, events=self._events
        ).execute(command)
        return container, True

    def _sign_off(self, request: ConfirmCaptureCommand, container_number: str):
        with self._recognition as uow:
            job = uow.jobs.get(request.job_id)
            if job is None:  # pragma: no cover - vanished mid-workflow
                raise RecognitionJobNotFound(request.job_id)
            job.confirm(container_number, confirmed_by=request.confirmed_by)
            uow.jobs.save(job)
            uow.commit()

        self._events.dispatch(job.pull_events())
        return job
