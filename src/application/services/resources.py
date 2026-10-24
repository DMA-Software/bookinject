#!/usr/bin/env python3
"""Resource accounting for Book Injector services.

All services share one process and one reactor thread, so the OS only knows
the resources of the process as a whole. Every metric therefore carries a
``MetricSource``:

* ``Measured``   - exact for its scope: OS counters of a process, CPU time of
                   a worker thread that ran only the service's function.
* ``Attributed`` - estimated share of a resource the services use together.
* ``Reported``   - counted by the service itself (requests, bytes, queue depth).

Nothing in this module raises: a metric that cannot be read is left out.
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

from src.constants import DEFAULT_DEBUG_LOGGER_NAME, DEFAULT_MAIN_LOGGER_NAME
from src.enumerations import MetricSource, ServiceState

try:
    import psutil
except ImportError:
    psutil = None  # pyright: ignore[reportAssignmentType]

logger = logging.getLogger(DEFAULT_MAIN_LOGGER_NAME)
debugLogger = logging.getLogger(DEFAULT_DEBUG_LOGGER_NAME)


@dataclass(frozen=True)
class Metric:
    """Represent a metric with a value, source, and unit.

    This class encapsulates the concept of a measurable metric, including its
    numeric value, the unit of measurement, and the source of the metric.

    Attributes:
        value (float): The numeric value of the metric.
        source (MetricSource): The source of the metric (e.g., reported, inferred).
        unit (str): The unit of measurement for the metric (e.g., "kg", "m", ""). Defaults to an empty string.
    """

    value: float = field(
        default=0.0, metadata={"description": "The numeric value of the metric"}
    )
    source: MetricSource = field(
        default=MetricSource.Reported,
        metadata={"description": "The source of the metric"},
    )
    unit: str = field(
        default="", metadata={"description": "The unit of measurement for the metric"}
    )

    def toJSON(self) -> dict:
        return {"value": self.value, "source": str(self.source), "unit": self.unit}


@dataclass(frozen=True)
class ResourceSnapshot:
    """Immutable snapshot of a service's resource state.

    Provides a record of a specific point in time for a service's metrics and
    operational status.

    Attributes:
        serviceName (str): The name of the service.
        timestamp (float): The epoch timestamp (in seconds) when the snapshot was
            taken.
        state (ServiceState): The operational state of the service.
        uptimeSeconds (float): The service uptime at the time of the snapshot, in
            seconds.
        counters (dict[str, Metric]): Monotonically increasing metrics.
        gauges (dict[str, Metric]): Metrics representing current values.
    """

    serviceName: str = field(
        default_factory=str, metadata={"description": "The name of the service."}
    )
    timestamp: float = field(
        default_factory=float,
        metadata={
            "description": "The epoch timestamp (in seconds) when the snapshot was taken."
        },
    )  # Seconds since the epoch
    # pyrefly: ignore[no-matching-overload]
    state: ServiceState = field(
        default_factory=ServiceState,
        metadata={"description": "The operational state of the service."},
    )
    uptimeSeconds: float = field(
        default_factory=float,
        metadata={
            "description": "The service uptime at the time of the snapshot, in seconds."
        },
    )
    counters: dict[str, Metric] = field(
        default_factory=dict, metadata={"description": "Monotonic totals"}
    )  # Monotonic totals
    gauges: dict[str, Metric] = field(
        default_factory=dict, metadata={"description": "Current values"}
    )  # Current values

    def toJSON(self) -> dict:
        return {
            "serviceName": self.serviceName,
            "timestamp": self.timestamp,
            "state": str(self.state),
            "uptimeSeconds": self.uptimeSeconds,
            "counters": {
                name: metric.toJSON() for name, metric in self.counters.items()
            },
            "gauges": {name: metric.toJSON() for name, metric in self.gauges.items()},
        }


@dataclass(frozen=True)
class ResourceReport:
    """Represent resource usage over time.

    Detailed description of the class, its purpose, and usage.

    Attributes:
        timestamp (float): The time at which the resource usage is recorded.
        process (dict[str, Metric]): A dictionary mapping process names to their metrics.
            Defaults to an empty dictionary.
        services (dict[str, ResourceSnapshot]): A dictionary mapping service names to
            their resource snapshots. Defaults to an empty dictionary.
    """

    timestamp: float = field(
        default_factory=float,
        metadata={"description": "The time at which the resource usage is recorded."},
    )
    process: dict[str, Metric] = field(
        default_factory=dict,
        metadata={
            "description": "A dictionary mapping process names to their metrics."
        },
    )
    services: dict[str, ResourceSnapshot] = field(
        default_factory=dict,
        metadata={
            "description": "A dictionary mapping service names to their resource snapshots."
        },
    )

    def toJSON(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "process": {name: metric.toJSON() for name, metric in self.process.items()},
            "services": {
                name: snapshot.toJSON() for name, snapshot in self.services.items()
            },
        }


class ResourceMeter:
    """
    Manage counters and gauges for tracking metrics in a thread-safe way.

    This class provides methods to increment counters, set or adjust gauges, and
    retrieve the current state of all metrics. It ensures thread-safety by using
    an internal lock.

    Attributes:
        _lock (threading.Lock): A lock to synchronize access to internal state.
        _counters (dict[str, Metric]): A dictionary of counters mapped by name.
        _gauges (dict[str, Metric]): A dictionary of gauges mapped by name.
    """

    def __init__(self):
        """
        Module providing the ResourceMeter class for managing metrics.

        This module contains functionality to initialize, store, and manage counters
        and gauges for tracking various metrics in a thread-safe manner.
        """
        logger.info("Initializing ResourceMeter")

        self._lock = threading.Lock()
        self._counters: dict[str, Metric] = {}
        self._gauges: dict[str, Metric] = {}

        debugLogger.debug("ResourceMeter initialized")

    def count(
        self,
        name: str,
        amount: float = 1.0,
        source: MetricSource = MetricSource.Reported,
        unit: str = "",
    ) -> None:
        """
        Increment the counter-metric for a given name by a specified amount.

        Updates the internal counter-state with the provided amount, sourcing, and unit.
        Emits an error log if the amount is negative. Thread-safe operation using a lock.

        Args:
            name (str): The name of the counter-metric to increment.
            amount (float, optional): Amount to increment the counter by. Defaults to 1.0.
                                      Must be non-negative.
            source (MetricSource, optional): Source of the metric. Defaults to
                                              MetricSource.Reported.
            unit (str, optional): Unit of the metric. Defaults to an empty string.

        Returns:
            None
        """

        if not isinstance(name, str) or not name:
            logger.error(f"The name of the counter-metric must be a non-empty string")
            return

        if amount < 0:
            logger.error(f"Counter '{name}' cannot decrease (amount={amount})")
            return

        logger.info(f"Increasing counter with name '{name}' by {amount}")

        with self._lock:
            previous = self._counters.get(name)
            debugLogger.debug(f"Previous value for counter '{name}': {previous.value if previous else 0.0}")

            total = (previous.value if previous else 0.0) + amount
            debugLogger.debug(f"New value for counter '{name}': {total}")

            self._counters[name] = Metric(total, source, unit)

        debugLogger.debug(f"Counter '{name}' updated with new value: {total}")

    def gauge(
        self,
        name: str,
        value: float,
        source: MetricSource = MetricSource.Reported,
        unit: str = "",
    ) -> None:
        """
        Record a gauge metric, representing a single value measurement.

        This method updates an internal dictionary with the given gauge metric,
        associating it with its name and corresponding metadata.

        Args:
            name (str): The unique name of the gauge metric.
            value (float): The value of the gauge metric.
            source (MetricSource, optional): The source of the metric data. Defaults to
                MetricSource.Reported.
            unit (str, optional): A string representing the metric's unit, such as
                "ms", "MB", or an empty string for no unit. Defaults to "".
        """

        if not isinstance(name, str) or not name:
            logger.error("The name must be a non-empty string")
            return

        if not isinstance(value, float) or not isinstance(value, int):
            logger.error("The value must be a float or an integer")
            return

        logger.info(f"Gauge metric recorded: name={name}, value={value}, source={source}, unit={unit}")

        with self._lock:
            self._gauges[name] = Metric(value, source, unit)
            debugLogger.debug(f"Gauge metric added: name={name}, value={value}, source={source}, unit={unit}")

        logger.debug(f"Gauge metric recorded: name={name}, value={value}, source={source}, unit={unit}")

    def gaugeAdd(
        self,
        name: str,
        delta: float,
        source: MetricSource = MetricSource.Reported,
        unit: str = "",
    ) -> None:
        """
        Add a delta value to an existing gauge or create a new gauge.

        This method updates the value of a gauge identified by its name by adding
        the given delta. If the gauge does not exist, it creates a new one with the
        specified delta, source, and unit.

        Args:
            name (str): The name of the gauge to update or create.
            delta (float): The value to add to the gauge.
            source (MetricSource, optional): The source of the metric. Defaults to
                MetricSource.Reported.
            unit (str, optional): The unit of measurement for the gauge. Defaults
                to an empty string.

        Returns:
            None
        """

        if not isinstance(name, str) or not name:
            logger.error("The name must be a non-empty string")
            return

        if not isinstance(delta, float) or not isinstance(delta, int):
            logger.error("The value of delta must be float or integer.")
            return

        logger.info(f"Adding delta {delta} to gauge {name}")

        with self._lock:
            previous = self._gauges.get(name)
            debugLogger.info(f"Previous value of gauge {name}: {previous.value if previous else 0.0}")

            self._gauges[name] = Metric(
                (previous.value if previous else 0.0) + delta, source, unit
            )
            debugLogger.info(f"New value of gauge {name}: {self._gauges[name].value}")

        logger.debug(f"Updated gauge {name} with delta {delta}")

    def read(self) -> tuple[dict[str, Metric], dict[str, Metric]]:
        """
        Module containing the functionality to read counters and gauges in a thread-safe
        manner.

        This module provides a `read` method that returns thread-safe copies of counters
        and gauges as dictionaries.
        """
        with self._lock:
            return dict(self._counters), dict(self._gauges)


class ProcessMonitor:
    """OS-level metrics (``Measured``) of one process via ``psutil``.

    Without ``pid`` it watches the current process. A service that runs its
    work in a subprocess passes the child's pid and publishes the result from
    ``BaseService.collectResources``. Without ``psutil``, or when the process
    is gone, ``read()`` returns an empty dict.

    ``cpuPercent`` is the load since the previous ``read()`` (can exceed 100 on
    multi-core machines), so concurrent readers shorten each other's window.
    The ``io*Bytes`` counters are OS-wide I/O of the process: files, pipes and
    sockets together.
    """

    def __init__(self, pid: int | None = None):
        """
        Monitoring process resource usage.

        This module is used to monitor process resource metrics, such as CPU usage
        and other process-specific statistics. It uses the `psutil` library to retrieve
        and handle process information. The monitoring attempts to connect to a
        specific process using its PID, falling back to the current process if no PID
        is specified. If `psutil` is not installed, a warning will be logged, and no
        monitoring can be performed.

        Args:
            pid: The PID of the process to monitor. If not specified, the current process is monitored.

        """
        if psutil is None:
            logger.warning(
                "psutil is not installed: process resource metrics are unavailable"
            )
            return

        logger.info("Initializing process resource monitoring")

        self.pid = pid if pid is not None else os.getpid()
        self._process = None
        self._warned: set[str] = set()

        try:
            self._process = psutil.Process(self.pid)
            debugLogger.info(f"Process info for the process with PID {self.pid}: {self._process.info}")

            self._process.cpu_percent(None)  # The first call always returns 0.0
            debugLogger.info(f"Process CPU percent for the process with PID {self.pid}: {self._process.cpu_percent(None)}")

        except psutil.Error as exc:
            logger.warning(f"Cannot monitor process {self.pid}: {exc}")
            self._process = None
            return

        debugLogger.info(f"Process resource monitoring initialized for the process with PID {self.pid}")

    def read(self) -> dict[str, Metric]:
        """Read process metrics and return them as a dictionary.

        This method gathers various metrics about a process, such as memory usage,
        CPU usage, thread count, handle count, I/O statistics, and network
        connections. It attempts to compute these metrics for the process object
        and constructs a dictionary where the keys are metric names and the
        values are Metric objects.

        Returns:
            dict[str, Metric]: A dictionary of process metrics, where keys are
            metric names and values are Metric objects. If the process is `None`,
            an empty dictionary is returned.

        Examples:
            >>> metrics = some_instance.read()
            >>> 'rssBytes' in metrics
            True

        Note:
            If any metric is unavailable due to an exception, it will be skipped,
            and a debug message will be logged. Unavailable metrics will not be
            included in the returned dictionary.
        """

        process = self._process
        if process is None:
            return {}

        getters: tuple[tuple[str, Callable[[], float], str], ...] = (
            ("rssBytes", lambda: process.memory_info().rss, "B"),
            ("vmsBytes", lambda: process.memory_info().vms, "B"),
            ("cpuPercent", lambda: process.cpu_percent(None), "%"),
            ("cpuUserSeconds", lambda: process.cpu_times().user, "s"),
            ("cpuSystemSeconds", lambda: process.cpu_times().system, "s"),
            ("threads", process.num_threads, ""),
            ("handles", lambda: self._handleCount(process), ""),
            ("ioReadBytes", lambda: process.io_counters().read_bytes, "B"),
            ("ioWriteBytes", lambda: process.io_counters().write_bytes, "B"),
            ("networkConnections", lambda: self._connectionCount(process), ""),
        )

        metrics: dict[str, Metric] = {}
        for name, getter, unit in getters:
            debugLogger.debug(f"Process {self.pid}: metric '{name}'")

            if psutil is None:
                logger.warning(f"Process {self.pid}: psutil is not available")
                continue

            try:
                metrics[name] = Metric(float(getter()), MetricSource.Measured, unit)
                debugLogger.debug(f"Process {self.pid}: metric '{name}' is available")

            except (psutil.Error, AttributeError, NotImplementedError, OSError) as exc:
                logger.warning(f"Process {self.pid}: metric '{name}' is unavailable: {exc}")

                if name not in self._warned:
                    self._warned.add(name)
                    debugLogger.debug(
                        f"Process {self.pid}: metric '{name}' is unavailable: {exc}"
                    )

        debugLogger.debug(f"Process {self.pid}: metrics: {metrics}")
        return metrics

    @staticmethod
    def _handleCount(process) -> int:
        """
        Return the number of system-wide resources a process is using.

        On Windows, this returns the number of handles. On POSIX systems, it
        returns the number of file descriptors.

        Args:
            process: An instance representing the process whose system-wide
                resource usage is to be counted. This object must have either
                a `num_handles` or `num_fds` method.

        Returns:
            int: The number of handles or file descriptors in use by the process.
        """
        # Windows: handles, POSIX: file descriptors
        if hasattr(process, "num_handles"):
            debugLogger.debug(f"Process {process.pid}: num_handles")
            return process.num_handles()

        debugLogger.debug(f"Process {process.pid}: num_fds")
        return process.num_fds()

    @staticmethod
    def _connectionCount(process) -> int:
        """
        Return the number of network connections for a given process.

        Determines the number of active network connections attributed to
        the specified process using the psutil library.

        Args:
            process: An instance of a psutil.Process object representing
                the process to inspect.

        Returns:
            int: The number of network connections associated with the process.

        Raises:
            TODO(doc): clarify if any exceptions are explicitly raised in this method.
        """
        # psutil < 6 calls it "connections"
        getConnections = (
            getattr(process, "net_connections", None) or process.connections
        )

        debugLogger.debug(f"Process {process.pid}: net_connections")
        return len(getConnections())
