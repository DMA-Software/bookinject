#!/usr/bin/env python3
"""Registry and lifecycle owner of all Book Injector services.

Services start in dependency order (``BaseService.dependsOn``) and stop in the
reverse order. The manager is itself a Twisted ``MultiService`` and can be
attached to an ``Application`` or driven manually::

    manager = ServiceManager(EventBus())
    manager.register(DatabaseService(manager.events, config.localDatabase))
    reactor.callWhenRunning(lambda: ensureDeferred(manager.startAll()))
    reactor.addSystemEventTrigger("before", "shutdown", manager.stopAll)
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable

from twisted.application.service import MultiService, Service
from twisted.internet.defer import Deferred, ensureDeferred
from twisted.internet.error import ReactorNotRunning
from twisted.internet.interfaces import IReactorTime
from twisted.internet.task import LoopingCall
from twisted.python.failure import Failure

from src.application.services.base_service import BaseService, ServiceT
from src.application.services.events import EventBus, ResourceSampled, ServiceFailed
from src.application.services.resources import ProcessMonitor, ResourceReport
from src.constants import DEFAULT_DEBUG_LOGGER_NAME, DEFAULT_MAIN_LOGGER_NAME
from src.enumerations import FailurePolicy, ServiceState

logger = logging.getLogger(DEFAULT_MAIN_LOGGER_NAME)
debugLogger = logging.getLogger(DEFAULT_DEBUG_LOGGER_NAME)


class ServiceManager(MultiService):
    """
    ServiceManager module.

    This module provides the implementation of the ServiceManager class, which
    is a custom service manager built on top of Twisted's MultiService framework.
    It handles service registration, dependency management, lifecycle operations,
    resource monitoring, and sampling.

    Classes:
        ServiceManager: Configures and manages services following dependency rules.
    """

    def __init__(self, events: EventBus):
        """
        ServiceManager handles service-level events and monitoring.

        This module provides a service management layer, integrating event handling,
        monitoring, and a shutdown mechanism. It subscribes to specific events and reacts
        to failures or other workflow scenarios.
        """
        logger.info("Initializing ServiceManager")
        super().__init__()

        if not isinstance(events, EventBus):
            logger.error("events must be an instance of EventBus")
            return

        self.events = events
        self._shuttingDown = False

        self._processMonitor = ProcessMonitor()
        if not isinstance(self._processMonitor, ProcessMonitor):
            logger.error("self._processMonitor must be an instance of ProcessMonitor")
            return

        self._sampler: LoopingCall | None = None
        self.events.subscribe(ServiceFailed, self._onServiceFailed)

        debugLogger.info("ServiceManager initialized")

    # ------------------------------------------------------------------
    # Registry
    # ------------------------------------------------------------------
    def register(self, service: BaseService) -> None:
        """
        Register a service within the current parent service.

        Associates the provided service with the current service as its parent,
        enabling parent-child relationships in the service hierarchy.

        Args:
            service (BaseService): The service to be registered.
        """
        logger.debug(f"Registering service {service.name}")
        service.setServiceParent(self)

    def get(self, serviceType: type[ServiceT]) -> ServiceT | None:
        """
        Retrieve a service instance of the specified type from the registered services.

        This method searches through the list of registered services and returns an
        instance of the specified service type if it is found.

        Args:
            serviceType (type[ServiceT]): The type of the service to retrieve.

        Returns:
            ServiceT | None: The service instance if found; otherwise, None.
        """
        logger.debug(f"Getting service {serviceType.__name__}")
        for service in self.services:
            debugLogger.debug(f"Checking service {service.name}")
            if isinstance(service, serviceType):
                logger.debug(f"Found service {service.name}")
                return service

        logger.error(f"Service {serviceType.__name__} is not registered")
        return None

    def getByName(self, name: str) -> BaseService | None:
        """
        Retrieve a service by its name.

        Look up a service in the 'namedServices' dictionary using the given name.
        If the service is not an instance of 'BaseService', log an error and return
        None. If found and valid, return the service instance.

        Args:
            name (str): The name of the service to retrieve.

        Returns:
            BaseService | None: The service instance if found and valid, otherwise
            None.

        Example:
            >>> service_registry = ServiceRegistry()
            >>> base_service = service_registry.getByName("example_service")
            >>> print(base_service is None)
            False
        """
        service = self.namedServices.get(name)
        if not isinstance(service, BaseService):
            logger.error(f"Service '{name}' is not registered")
            return None
        return service

    def status(self) -> dict[str, ServiceState]:
        """
        Return a dictionary mapping service names to their states.

        This method retrieves all base services and constructs a dictionary where
        the keys are the names of the services or an empty string for unnamed
        services, and the values are their respective states.

        Returns:
            dict[str, ServiceState]: A dictionary where the keys are service names
            as strings or empty strings for unnamed services, and the values are
            ServiceState instances representing the state of each service.
        """
        return {service.name or "": service.state for service in self._baseServices()}

    # ------------------------------------------------------------------
    # Resources
    # ------------------------------------------------------------------
    def getResourceUsage(self) -> ResourceReport:
        """
        Retrieve resource usage data from the process monitor and base services.

        This method consolidates the resource usage information from both the process
        monitor and the associated base services, returning a comprehensive resource
        report.

        Returns:
            ResourceReport: Contains the timestamp, process resource usage, and a
            dictionary of resource usage for each base service.
        """
        services = {service.name or "": service.getResourceUsage() for service in self._baseServices()}
        return ResourceReport(
            timestamp=time.time(),
            process=self._processMonitor.read(),
            services=services,
        )

    def startSampling(self, intervalSeconds: float, clock: IReactorTime | None = None) -> bool:
        """
        Start the resource sampling process at a specified interval.

        This method initializes and starts a looping call to sample resources at
        the given interval. It also allows setting a custom clock for the sampling
        loop. If sampling is already running, or if the interval is invalid, the
        function will immediately return False without starting a new loop.

        Args:
            intervalSeconds: The interval in seconds between sampling actions. Must
                be greater than 0.
            clock: An optional custom clock object implementing IReactorTime.
                Defaults to None.

        Returns:
            bool: True if the sampling loop started successfully, otherwise False.

        Warning:
            Ensure that the sampling interval is valid and greater than zero,
            otherwise the function will fail.

        """
        if intervalSeconds <= 0:
            logger.error(f"Invalid sampling interval: {intervalSeconds}")
            return False

        if self._sampler is not None and self._sampler.running:
            logger.warning("Resource sampling is already running")
            return False

        sampler = LoopingCall(self._sample)
        if not sampler:
            logger.error("Failed to create resource sampling loop")
            return False

        if clock is not None:
            debugLogger.debug("Clock is set for resource sampling")
            sampler.clock = clock

        self._sampler = sampler

        debugLogger.info("Starting resource sampling")
        _defferedLoopingCall = sampler.start(intervalSeconds, now=False).addErrback(self._onSamplerFailure)
        if not _defferedLoopingCall:
            logger.error("Failed to start resource sampling loop")
            return False

        debugLogger.info("Resource sampling started")
        return True

    def stopSampling(self) -> None:
        """Stop the current sampler if it is running.

        This method stops the running sampler, if any, and resets the internal
        sampler to None.

        Returns:
            None
        """
        sampler, self._sampler = self._sampler, None
        if sampler is not None and sampler.running:
            debugLogger.info("Stopping resource sampling")
            sampler.stop()
            return

        logger.error("No running sampler to stop")

    def _sample(self) -> None:
        """
        The module provides functionality for publishing resource usage events.
        """
        try:
            self.events.publish(ResourceSampled(self.getResourceUsage()))
            debugLogger.info("Resource sampling completed")
        except Exception:
            logger.exception("Resource sampling failed")

    @staticmethod
    def _onSamplerFailure(failure: Failure) -> None:
        """
        Handle sampler failure by logging the error and traceback.

        Args:
            failure (Failure): An object representing the failure, which contains
                details of the error and a traceback.
        """
        logger.error(f"Resource sampling stopped:\n{failure.getTraceback()}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def startAll(self) -> bool:
        """Start services in dependency order; never raises.

        A service whose dependencies are not Running is skipped. If a start
        fails, ``failurePolicy`` decides: FailFast stops what was started and
        returns False, Ignore logs and continues.

        Returns:
            False if the application must not continue: the dependency graph
            is invalid or a FailFast service failed to start.
        """

        logger.info("Starting all services")

        try:
            order = self._resolveOrder()
            debugLogger.info("Starting services in dependency order")

        except ValueError:
            logger.exception("Cannot resolve service dependencies")
            return False

        started: list[BaseService] = []
        for service in order:
            debugLogger.info(f"Starting service {service.name}")

            if self._dependenciesOf(service) is None:
                logger.warning(f"Skipping service {service.name}: no dependencies")
                return False
            
            notRunning = [
                # pyrefly: ignore[not-iterable]
                dep.name for dep in self._dependenciesOf(service) if dep.state is not ServiceState.Running
            ]
            if notRunning:
                logger.warning(
                    # pyrefly: ignore[no-matching-overload]
                    f"Skipping service {service.name}: dependencies not running: {','.join(notRunning)}"
                )
                continue

            logger.info("Starting service %s", service.name)
            if await service.start():
                started.append(service)
                debugLogger.info("Service %s started", service.name)

            elif service.failurePolicy is FailurePolicy.FailFast:
                logger.error("Service %s failed to start", service.name)
                await self._stopServices(reversed(started))
                return False

        debugLogger.info("All services started")
        return True

    async def stopAll(self) -> None:
        """
        Stop all ongoing services and sampling processes.

        This method stops any current sampling, resolves the order of services
        to stop, and then halts them in reverse order. If a ValueError occurs
        during the resolution of service order, the base services are used
        instead.

        Raises:
            ValueError: If the service order cannot be resolved.
        """
        self.stopSampling()
        try:
            order = self._resolveOrder()
            debugLogger.info("Stopping services in order: %s", order)
        except ValueError:
            logger.error("Failed to resolve service order, using base services")
            order = self._baseServices()

        await self._stopServices(reversed(order))
        debugLogger.info("Stopped services in order: %s", order)

    def shutdown(self) -> None:
        """
        Handle a graceful shutdown of the application.

        This module provides functionality to shut down the application,
        including stopping reactors and all active operations.
        """

        if self._shuttingDown:
            debugLogger.info("Already shutting down, skipping")
            return

        self._shuttingDown = True

        from twisted.internet import reactor

        def stopReactor(_: object) -> None:
            try:
                # pyrefly: ignore[bad-argument-count]
                reactor.stop()  # pyright: ignore[reportAttributeAccessIssue]
                debugLogger.info("Stopped reactor")
            except ReactorNotRunning:
                logger.warning("Reactor already stopped")

        ensureDeferred(self.stopAll()).addBoth(stopReactor)

    # Twisted IService API: overrides MultiService to honour the dependency order
    # pyrefly: ignore[bad-override]
    def startService(self) -> Deferred[bool]:  # pyright: ignore[reportIncompatibleMethodOverride]
        """
        TODO(doc): clarify the purpose and behavior of this module.
        """
        Service.startService(self)
        return ensureDeferred(self.startAll())

    # pyrefly: ignore[bad-override]
    def stopService(self) -> Deferred[None]:  # pyright: ignore[reportIncompatibleMethodOverride]
        """
        Stop the service and all associated processes asynchronously.

        Calls the parent Service.stopService() method and ensures
        that all processes managed by this service are properly stopped.

        Returns:
            Deferred[None]: A deferred that resolves when the service and all
            associated processes have been stopped.
        """
        Service.stopService(self)
        return ensureDeferred(self.stopAll())

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _baseServices(self) -> list[BaseService]:
        """Return a list of BaseService instances filtered from self.services.

        Iterates over the `self.services` attribute and selects those that are
        instances of the `BaseService` class.

        Returns:
            list[BaseService]: A list of `BaseService` instances.
        """
        return [service for service in self.services if isinstance(service, BaseService)]

    def _dependenciesOf(self, service: BaseService) -> list[BaseService] | None:
        """
        Return a list of service dependencies for a given service.

        The method iterates over all dependency types declared in the provided
        service's `dependsOn` attribute, determines the corresponding registered
        services, and collects them in a list of dependencies.

        Args:
            service (BaseService): The service whose dependencies are to be determined.

        Returns:
            list[BaseService]: A list of dependent services for the given service.

        Raises:
            ValueError: If a required dependency is not registered in the system.
        """

        dependencies: list[BaseService] = []
        for dependencyType in service.dependsOn:
            debugLogger.debug(f"Resolving dependency {dependencyType.__name__} for {service.name}")
            dependency = next((s for s in self._baseServices() if isinstance(s, dependencyType)), None)

            if dependency is None:
                logger.error(
                    f"{service.name} depends on {dependencyType.__name__}, which is not registered"
                )
                return None

            debugLogger.debug(f"Resolved dependency {dependencyType.__name__} for {service.name}")
            dependencies.append(dependency)

        debugLogger.debug(f"Resolved dependencies for {service.name}")
        return dependencies

    def _resolveOrder(self) -> list[BaseService]:
        """Resolve the order of service initialization based on dependencies.

        This method topologically sorts the services according to their dependencies,
        ensuring no dependency cycles exist.

        Returns:
            list[BaseService]: A list of services in the order they should be initialized.

        Raises:
            ValueError: If a dependency cycle is detected among the services.
        """
        order: list[BaseService] = []
        visiting: set[int] = set()
        visited: set[int] = set()

        def visit(service: BaseService) -> None:
            """
            Perform a depth-first traversal for resolving service dependencies.

            Given a service, this function ensures that the service and its dependencies
            are processed in a topological order, avoiding cyclic dependencies.

            Args:
                service (BaseService): The service whose dependencies need to be resolved.

            Raises:
                ValueError: If a cyclic dependency is detected involving the given service.
            """
            if id(service) in visited:
                debugLogger.debug("Service %s already visited", service.name)
                return

            if id(service) in visiting:
                logger.error(f"Dependency cycle detected at {service.name}")
                return

            visiting.add(id(service))
            if self._dependenciesOf(service) is None:
                debugLogger.debug(f"Service {service.name} has no dependencies")
                visiting.discard(id(service))
                visited.add(id(service))
                order.append(service)
                return

            # pyrefly: ignore[not-iterable]
            for dependency in self._dependenciesOf(service):
                debugLogger.debug(f"Visiting dependency {dependency.name} of service {service.name}")
                visit(dependency)

            visiting.discard(id(service))
            visited.add(id(service))
            order.append(service)

        for service in self._baseServices():
            debugLogger.debug(f"Visiting service {service.name}")
            visit(service)

        debugLogger.debug(f"Service order: {order}")
        return order

    async def _stopServices(self, services: Iterable[BaseService]) -> None:
        """
        Stop the provided services asynchronously.

        Each service will have its stop method called, and any exceptions during
        the process are logged.

        Args:
            services (Iterable[BaseService]): An iterable of services to stop.

        Note:
            This method logs exceptions but does not propagate them.
        """
        for service in services:
            logger.info("Stopping service %s", service.name)
            try:
                await service.stop()
                debugLogger.info("Service %s stopped", service.name)
            except Exception:
                logger.exception("Service %s failed to stop", service.name)

    def _onServiceFailed(self, event: ServiceFailed) -> None:
        """
        Handle a service failure event.

        This method logs the failure of a service, retrieves the service by its
        name, and shuts down the system if the service's failure policy is
        FailFast.

        Args:
            event (ServiceFailed): The event containing details about the
                service failure, including the name of the service and the
                error that occurred.
        """
        logger.error("Service %s failed: %r", event.serviceName, event.error)
        service = self.getByName(event.serviceName)
        if service is not None and service.failurePolicy is FailurePolicy.FailFast:
            self.shutdown()
