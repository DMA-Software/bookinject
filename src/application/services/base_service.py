#!/usr/bin/env python3
"""Base class of all Book Injector services.

Builds on ``twisted.application.service.Service`` so a service can live in a
Twisted service tree. The lifecycle is driven by coroutines::

    class OcrService(BaseService):
        dependsOn = (DatabaseService,)

        async def onStart(self) -> None: ...
        async def onStop(self) -> None: ...

State machine: New -> Starting -> Running -> Stopping -> Stopped, with Failed
reachable from Starting (``onStart`` raised) and Running (``reportFailure``).
A Stopped service can be started again.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar, TypeVar

from twisted.application.service import Service
from twisted.internet.defer import Deferred, ensureDeferred
from twisted.internet.threads import deferToThread

from src.application.services.events import (
    EventBus,
    ServiceFailed,
    ServiceStateChanged,
)
from src.constants import DEFAULT_DEBUG_LOGGER_NAME, DEFAULT_MAIN_LOGGER_NAME
from src.enumerations import FailurePolicy, ServiceState

ServiceT = TypeVar("ServiceT", bound="BaseService")

logger = logging.getLogger(DEFAULT_MAIN_LOGGER_NAME)
debugLogger = logging.getLogger(DEFAULT_DEBUG_LOGGER_NAME)


class BaseService(Service):
    # Services that must be Running before this one starts (matched by type)
    dependsOn: ClassVar[tuple[type[BaseService], ...]] = ()
    failurePolicy: ClassVar[FailurePolicy] = FailurePolicy.FailFast

    def __init__(self, events: EventBus, name: str | None = None):
        logger.debug(f"Creating {self.__class__.__name__} service")
        self.name = name or type(self).__name__
        self.events = events
        self.state = ServiceState.New

    # ------------------------------------------------------------------
    # Hooks for subclasses
    # ------------------------------------------------------------------
    async def onStart(self) -> None:
        """Acquire resources and start working. Raise to abort the start."""

    async def onStop(self) -> None:
        """Release resources. Must tolerate a partially completed ``onStart``."""

    async def onFailure(self) -> None:
        """Handle a failure. Must tolerate a partially completed ``onStart``."""

    async def onAbort(self) -> None:
        """Handle an abort. Must tolerate a partially completed ``onStart``."""

    async def onShutdown(self) -> None:
        """Handle a shutdown. Must tolerate a partially completed ``onStart``."""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def start(self) -> None:
        if self.state not in (ServiceState.New, ServiceState.Stopped):
            await self.onAbort()
            raise RuntimeError(f"{self.name}: cannot start from state {self.state}")

        self._setState(ServiceState.Starting)
        try:
            await self.onStart()
        except Exception:
            await self.onFailure()
            self._setState(ServiceState.Failed)
            raise

        Service.startService(self)
        self._setState(ServiceState.Running)

    async def stop(self) -> None:
        if self.state not in (ServiceState.Running, ServiceState.Failed):
            return

        self._setState(ServiceState.Stopping)
        try:
            await self.onStop()
        except Exception:
            # Keep stopping: one broken service must not block the shutdown
            logger.exception("%s: onStop failed", self.name)
            await self.onFailure()

        Service.stopService(self)
        self._setState(ServiceState.Stopped)

    def reportFailure(self, error: BaseException) -> None:
        """Report a failure of a Running service; the ServiceManager applies ``failurePolicy``."""
        self._setState(ServiceState.Failed)
        self.events.publish(ServiceFailed(self.name or "", error))

    # Twisted IService API: used by MultiService.addService() and twistd
    # pyrefly: ignore[bad-override]
    def startService(self) -> Deferred[None]:  # pyright: ignore[reportIncompatibleMethodOverride]
        return ensureDeferred(self.start())

    # pyrefly: ignore[bad-override]
    def stopService(self) -> Deferred[None]:  # pyright: ignore[reportIncompatibleMethodOverride]
        return ensureDeferred(self.stop())

    # ------------------------------------------------------------------
    # Helpers for subclasses
    # ------------------------------------------------------------------
    def require(self, serviceType: type[ServiceT]) -> ServiceT:
        """Return the registered service of ``serviceType`` from the parent ServiceManager."""
        if self.parent is None:
            raise RuntimeError(f"{self.name}: service is not attached to a ServiceManager")
        return self.parent.get(serviceType)  # pyright: ignore[reportAttributeAccessIssue]

    def runBlocking(self, func: Any, *args: Any, **kwargs: Any) -> Deferred[Any]:
        """Run blocking ``func`` in the reactor thread pool; the reactor thread must never block."""
        return deferToThread(func, *args, **kwargs)

    def _setState(self, newState: ServiceState) -> None:
        oldState, self.state = self.state, newState
        debugLogger.debug("%s: %s -> %s", self.name, oldState, newState)
        self.events.publish(ServiceStateChanged(self.name or "", oldState, newState))
