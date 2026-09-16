"""Maps exceptions to HTTP responses in one place.

Routers stay free of try/except: a use case raises what actually went wrong
and the mapping lives here. Starlette resolves handlers along the exception's
MRO, so registering ``DomainError`` catches every subclass that has no more
specific handler of its own.
"""

from __future__ import annotations

import re

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.context.recognition.application import RecognitionJobNotFound
from src.context.registry.application import (
    ContainerAlreadyRegistered,
    ContainerNotFound,
)
from src.shared_kernel.domain import BusinessRuleViolation, DomainError

_CAMEL_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")


def error_code(exc: Exception) -> str:
    """``InvalidContainerNumber`` -> ``invalid_container_number``."""
    return _CAMEL_BOUNDARY.sub("_", type(exc).__name__).lower()


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ContainerNotFound)
    async def _not_found(request: Request, exc: ContainerNotFound) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"code": error_code(exc), "detail": str(exc)},
        )

    @app.exception_handler(RecognitionJobNotFound)
    async def _job_not_found(
        request: Request, exc: RecognitionJobNotFound
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"code": error_code(exc), "detail": str(exc)},
        )

    @app.exception_handler(ContainerAlreadyRegistered)
    async def _conflict(
        request: Request, exc: ContainerAlreadyRegistered
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"code": error_code(exc), "detail": str(exc)},
        )

    @app.exception_handler(BusinessRuleViolation)
    async def _rule_violated(
        request: Request, exc: BusinessRuleViolation
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "code": error_code(exc),
                "detail": exc.message,
                "rule": exc.rule,
            },
        )

    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"code": error_code(exc), "detail": str(exc)},
        )
