"""Errors raised by the registry's use cases.

Distinct from ``DomainError``: these are about the *state of the system*
(this container is not on file) rather than a broken business rule. The API
layer maps them to 404 / 409 respectively.
"""

from __future__ import annotations


class ApplicationError(Exception):
    """Base class for failures a use case can report to its caller."""


class ContainerNotFound(ApplicationError):
    """No container is registered under that number."""

    def __init__(self, container_number: str) -> None:
        self.container_number = container_number
        super().__init__(f"container {container_number} is not registered")


class ContainerAlreadyRegistered(ApplicationError):
    """A container with that number is already on file."""

    def __init__(self, container_number: str) -> None:
        self.container_number = container_number
        super().__init__(f"container {container_number} is already registered")
