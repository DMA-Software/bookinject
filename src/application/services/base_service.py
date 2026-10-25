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
import time
from collections.abc import Awaitable, Callable
from typing import Any, ClassVar, TypeVar

from twisted.application.service import Service
from twisted.internet.defer import Deferred, ensureDeferred
from twisted.internet.threads import deferToThread

from src.application.services.events import (
    EventBus,
    ServiceFailed,
    ServiceStateChanged,
)
from src.application.services.resources import ResourceMeter, ResourceSnapshot
from src.constants import DEFAULT_DEBUG_LOGGER_NAME, DEFAULT_MAIN_LOGGER_NAME
from src.enumerations import FailurePolicy, MetricSource, ServiceState

ServiceT = TypeVar("ServiceT", bound="BaseService")

logger = logging.getLogger(DEFAULT_MAIN_LOGGER_NAME)
debugLogger = logging.getLogger(DEFAULT_DEBUG_LOGGER_NAME)


class BaseService(Service):
    """
    BaseService defines the foundation for services that can be managed, monitored,
    and operated in an asynchronous environment using hooks and lifecycle states.

    This class provides common functionality for service management, including
    dependency handling, failure policies, and resource monitoring.

    Attributes:
        dependsOn (tuple[type[BaseService], ...]): Services that must be running
            before this one starts (matched by type).
        failurePolicy (FailurePolicy): Policy defining how failures are handled.
        name (str): Name of the service.
        events (EventBus): Event bus instance for publishing and subscribing to events.
        state (ServiceState): Current state of the service.
        resources (ResourceMeter): Tracks resource metrics for the service.
        _startedAt (float | None): Timestamp when the service was started.
    """
    # Services that must be Running before this one starts (matched by type)
    dependsOn: ClassVar[tuple[type[BaseService], ...]] = ()
    failurePolicy: ClassVar[FailurePolicy] = FailurePolicy.FailFast

    def __init__(self, events: EventBus, name: str | None = None):
        """
        Represents a service with event handling and lifecycle states.

        Args:
            events (EventBus): The event bus for publishing and subscribing to events.
            name (str | None): Optional custom name for the service. Defaults to the class name.

        Attributes:
            name (str): The name of the service, either user-defined or derived from the class.
            events (EventBus): The event bus associated with the service.
            state (ServiceState): The current state of the service lifecycle.
            resources (ResourceMeter): Tracks resource usage of the service.
            _startedAt (float | None): The timestamp when the service was started, or None if not started.
        """
        logger.debug(f"Creating {self.__class__.__name__} service")
        self.name = name or type(self).__name__
        self.events = events
        self.state = ServiceState.New
        self.resources = ResourceMeter()
        self._startedAt: float | None = None

        debugLogger.debug(f"{self.name}: initialized")

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

    def collectResources(self) -> None:
        """Refresh gauges in ``self.resources`` just before a snapshot is taken.

        Override to publish values that are cheaper to read on demand than to
        keep current (queue depth, open connections, a subprocess's
        ``ProcessMonitor.read()``). Must be fast, must not block the reactor.
        """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def start(self) -> bool:
        """
        Start a service asynchronously, transitioning it to the running state.

        This method ensures the service moves from an appropriate state (New or Stopped)
        to the Running state by invoking necessary hooks and handling state transitions.
        If the service fails to start, it transitions to the Failed state and executes
        the failure hook.

        Returns:
            bool: True if the service started successfully; False otherwise.

        Raises:
            TODO(doc): clarify explicit exceptions if any are known to be raised.

        Note:
            The method is asynchronous and must be awaited.
            This method leverages internal state management and hooks for functionality.
        """
        logger.debug(f"{self.name}: starting")

        if self.state not in (ServiceState.New, ServiceState.Stopped):
            logger.error(f"{self.name}: cannot start from state {self.state}")
            await self._runHook(self.onAbort)
            return False

        self._setState(ServiceState.Starting)
        try:
            debugLogger.info(f"{self.name}: starting")
            await self.onStart()

        except Exception:
            logger.exception(f"{self.name}: onStart failed")
            await self._runHook(self.onFailure)
            self._setState(ServiceState.Failed)
            return False

        debugLogger.info(f"{self.name}: started")

        Service.startService(self)
        self._startedAt = time.monotonic()
        self._setState(ServiceState.Running)
        return True

    async def stop(self) -> None:
        """
        Stop the service if it is running or failed.

        This method changes the service state to Stopping, executes the onStop
        hook asynchronously, and handles any exceptions that may occur during
        the stop process. It ensures the service transitions to the Stopped
        state regardless of errors.

        Note:
            This method will log errors and continue the stopping process, even
            if exceptions occur during the onStop hook.

        Warning:
            Attempting to stop the service when it is not in the Running or
            Failed states will log an error and return early without stopping
            the service.
        """
        logger.info(f"{self.name}: stopping")

        if self.state not in (ServiceState.Running, ServiceState.Failed):
            # Not an error: shutdown stops every service, including ones never started
            debugLogger.debug(f"{self.name}: nothing to stop in state {self.state}")
            return

        self._setState(ServiceState.Stopping)
        try:
            debugLogger.debug(f"{self.name}: onStop")
            await self.onStop()

        except Exception as _e:
            # Keep stopping: one broken service must not block the shutdown
            logger.exception(f"{self.name}: onStop failed with exception: {_e}")
            await self._runHook(self.onFailure)

        debugLogger.info(f"{self.name}: stopped")

        Service.stopService(self)
        self._startedAt = None
        self._setState(ServiceState.Stopped)

    def reportFailure(self, error: BaseException) -> None:
        """
        Log the failure, change the service state to Failed, and publish the failure event.

        Args:
            error (BaseException): The exception describing the failure.
        """
        logger.error(f"{self.name}: reportFailure called with exception: {error}")
        self._setState(ServiceState.Failed)
        self.events.publish(ServiceFailed(self.name or "", error))

    # Twisted IService API: used by MultiService.addService() and twistd
    # pyrefly: ignore[bad-override]
    def startService(self) -> Deferred[bool]:  # pyright: ignore[reportIncompatibleMethodOverride]
        """
        Manage the lifecycle of the service.

        This module provides functionality to start and manage the service's lifecycle.
        It includes methods to initialize, start, and monitor the state of the service.
        """
        logger.info(f"{self.name}: startService called")
        return ensureDeferred(self.start())

    # pyrefly: ignore[bad-override]
    def stopService(self) -> Deferred[None]:  # pyright: ignore[reportIncompatibleMethodOverride]
        """
        This module defines a service management function for stopping a service.
        """
        logger.info(f"{self.name}: stopService called")
        return ensureDeferred(self.stop())

    # ------------------------------------------------------------------
    # Helpers for subclasses
    # ------------------------------------------------------------------
    def require(self, serviceType: type[ServiceT]) -> ServiceT | None:
        """
        Require a service of the given type from the ServiceManager.

        This method attempts to retrieve a service of the specified type from the
        parent ServiceManager. Logs relevant information about the request and
        whether the service type is registered.

        Args:
            serviceType (type[ServiceT]): The type of the service to be retrieved.

        Returns:
            ServiceT | None: The requested service instance if available; None if
            the service is not attached to a ServiceManager or not available.

        """
        logger.info(f"{self.name}: require called")
        getAttributeLookup = getattr(self.parent, "get", None)
        if getAttributeLookup is None:
            logger.error(f"{self.name}: service is not attached to a ServiceManager")
            return None

        debugLogger.info(
            f"The service type for {self.name} is {serviceType} and it is registered."
        )
        return getAttributeLookup(serviceType)

    def runBlocking(self, func: Any, *args: Any, **kwargs: Any) -> Deferred[Any]:
        """
        Execute a blocking function in a separate thread and measure its performance.

        This method runs the given function in a separate worker thread to ensure
        it does not block the main thread. Execution details, such as CPU and wall
        time consumption, are recorded using the `resources` meter. If the function
        produces an exception, it is propagated and properly measured.

        Args:
            func (Callable): The function to execute in the blocking thread.
            *args: Positional arguments to pass to the function.
            **kwargs: Keyword arguments to pass to the function.

        Returns:
            Deferred[Any]: A Twisted Deferred that resolves with the return value
            of the function or propagates its exception.
        """
        logger.info(f"{self.name}: runBlocking called")
        meter = self.resources
        meter.gaugeAdd("blockingActive", 1, MetricSource.Measured)

        def measured() -> Any:
            """
            Measure execution time and record metrics for a function.

            This function records both wall-clock and CPU time for the execution of
            a wrapped function. It updates several metrics like the number of completed
            tasks, active tasks, and failures. Designed to handle failures by counting
            blocking failures and propagating the exception.

            Returns:
                Any: The return value from the wrapped function.

            Raises:
                Exception: If the wrapped function raises an exception.
            """
            wallStart, cpuStart = time.monotonic(), time.thread_time()
            try:
                return func(*args, **kwargs)
            except Exception:
                meter.count("blockingFailed", 1, MetricSource.Measured)
                raise
            finally:
                # The worker thread ran nothing but func, so its CPU time is exact
                meter.count(
                    "blockingCpuSeconds",
                    time.thread_time() - cpuStart,
                    MetricSource.Measured,
                    "s",
                )
                meter.count(
                    "blockingWallSeconds",
                    time.monotonic() - wallStart,
                    MetricSource.Measured,
                    "s",
                )
                meter.count("blockingCompleted", 1, MetricSource.Measured)
                meter.gaugeAdd("blockingActive", -1, MetricSource.Measured)

        return deferToThread(measured)

    def getResourceUsage(self) -> ResourceSnapshot:
        """
        Collect resource usage and return a snapshot.

        This method gathers current resource usage metrics, including counters, gauges, and
        uptime, and returns them as a ResourceSnapshot object.

        Returns:
            ResourceSnapshot: An object containing resource usage details, including service
                name, timestamp, state, uptime in seconds, counters, and gauges.

        """
        try:
            self.collectResources()
        except Exception:
            logger.exception(f"{self.name}: collectResources failed")

        counters, gauges = self.resources.read()
        uptime = (
            time.monotonic() - self._startedAt if self._startedAt is not None else 0.0
        )
        return ResourceSnapshot(
            serviceName=self.name or "",
            timestamp=time.time(),
            state=self.state,
            uptimeSeconds=uptime,
            counters=counters,
            gauges=gauges,
        )

    async def _runHook(self, hook: Callable[[], Awaitable[None]]) -> None:
        """Run the provided hook and handle exceptions.

        Logs the start of the hook execution and captures any exceptions raised
        during the hook's execution.

        Args:
            hook (Callable[[], Awaitable[None]]): An asynchronous function to be executed.
        """
        logger.info(f"{self.name}: _runHook called")
        try:
            await hook()
        except Exception:
            logger.exception("%s: %s failed", self.name, hook.__name__)

    def _setState(self, newState: ServiceState) -> None:
        """
        Update the service state and publish a state change event.

        This method logs the old and new states, updates the service's state, and
        notifies subscribed listeners of the state change.

        Args:
            newState (ServiceState): The new state to set for the service.
        """
        logger.info(f"{self.name}: _setState called")
        oldState, self.state = self.state, newState

        debugLogger.debug("%s: %s -> %s", self.name, oldState, newState)
        self.events.publish(ServiceStateChanged(self.name or "", oldState, newState))
