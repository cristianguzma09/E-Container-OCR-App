"""FastAPI application factory.

Keeps ``main.py`` a one-liner and gives tests a clean way to build a fresh app.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.platform.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Backend service for detecting and reading maritime container IDs "
            "using AI/OCR."
        ),
        debug=settings.debug,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", tags=["system"])
    def read_root() -> dict[str, str]:
        return {"message": "Welcome to the Maritime Container OCR API!"}

    @app.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    _register_routers(app)
    return app


def _register_routers(app: FastAPI) -> None:
    """Mount each bounded context's API router.

    Wired up in later steps, e.g.::

        from src.context.registry.api.router import router as registry_router
        app.include_router(registry_router)
    """
