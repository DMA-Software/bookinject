"""BaseService: lifecycle, lookups, resource accounting."""

from __future__ import annotations

import json
import time

from twisted.internet.task import Clock
from twisted.trial.unittest import TestCase

from src.application.services import BaseService, EventBus, ServiceStateChanged
from src.enumerations import MetricSource, ServiceState
from tests.services import helpers
from tests.services.helpers import Db, Fatal, newManager


class Hooked(BaseService):
    """Records which hooks ran."""

    failOnStart = False
    failOnStop = False

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.hooks: list[str] = []

    async def onStart(self) -> None:
        self.hooks.append("onStart")
        if self.failOnStart:
            raise RuntimeError("start failed")

    async def onStop(self) -> None:
        self.hooks.append("onStop")
        if self.failOnStop:
            raise RuntimeError("stop failed")

    async def onFailure(self) -> None:
        self.hooks.append("onFailure")

    async def onAbort(self) -> None:
        self.hooks.append("onAbort")


class Worker(BaseService):
    def collectResources(self) -> None:
        self.resources.gauge("queueDepth", 7)
        self.resources.count("requests", 3, unit="req")


class BrokenCollector(BaseService):
    def collectResources(self) -> None:
        raise RuntimeError("bad collector")


class LifecycleTests(TestCase):
    def setUp(self) -> None:
        self.clock = Clock()
        self.events = EventBus(self.clock)
        self.transitions: list[tuple[ServiceState, ServiceState]] = []
        self.events.subscribe(
            ServiceStateChanged,
            lambda e: self.transitions.append((e.oldState, e.newState)),
        )

    async def test_startAndStopWalkThroughTheStateMachine(self) -> None:
        service = Hooked(self.events)
        self.assertIs(service.state, ServiceState.New)

        self.assertTrue(await service.start())
        self.assertIs(service.state, ServiceState.Running)
        await service.stop()
        self.assertIs(service.state, ServiceState.Stopped)

        self.clock.advance(0)
        self.assertEqual(
            self.transitions,
            [
                (ServiceState.New, ServiceState.Starting),
                (ServiceState.Starting, ServiceState.Running),
                (ServiceState.Running, ServiceState.Stopping),
                (ServiceState.Stopping, ServiceState.Stopped),
            ],
        )
        self.assertEqual(service.hooks, ["onStart", "onStop"])

    async def test_startFromWrongStateReturnsFalseAndAborts(self) -> None:
        service = Hooked(self.events)
        self.assertTrue(await service.start())

        self.assertFalse(await service.start())  # no exception

        self.assertIs(service.state, ServiceState.Running)
        self.assertEqual(service.hooks, ["onStart", "onAbort"])

    async def test_failingOnStartEndsInFailed(self) -> None:
        service = Hooked(self.events)
        service.failOnStart = True

        self.assertFalse(await service.start())

        self.assertIs(service.state, ServiceState.Failed)
        self.assertEqual(service.hooks, ["onStart", "onFailure"])

    async def test_failedServiceCanBeStopped(self) -> None:
        service = Hooked(self.events)
        service.failOnStart = True
        await service.start()

        await service.stop()

        self.assertIs(service.state, ServiceState.Stopped)

    async def test_failingOnStopStillStops(self) -> None:
        service = Hooked(self.events)
        service.failOnStop = True
        await service.start()

        await service.stop()

        self.assertIs(service.state, ServiceState.Stopped)
        self.assertEqual(service.hooks, ["onStart", "onStop", "onFailure"])

    async def test_stoppedServiceCanBeStartedAgain(self) -> None:
        service = Hooked(self.events)
        await service.start()
        await service.stop()

        self.assertTrue(await service.start())

        self.assertIs(service.state, ServiceState.Running)

    async def test_stopWhenNotRunningDoesNothing(self) -> None:
        service = Hooked(self.events)

        await service.stop()

        self.assertIs(service.state, ServiceState.New)
        self.assertEqual(service.hooks, [])

    def test_reportFailureMarksFailed(self) -> None:
        service = Hooked(self.events)

        service.reportFailure(RuntimeError("lost the database"))

        self.assertIs(service.state, ServiceState.Failed)


class RequireTests(TestCase):
    def setUp(self) -> None:
        helpers.journal.clear()
        self.manager, _ = newManager()

    def test_returnsTheRegisteredService(self) -> None:
        db, fatal = Db(self.manager.events), Fatal(self.manager.events)
        self.manager.register(db)
        self.manager.register(fatal)

        # regression: the lookup used to ask the parent for a method that does not exist
        self.assertIs(fatal.require(Db), db)

    def test_unregisteredTypeIsNone(self) -> None:
        fatal = Fatal(self.manager.events)
        self.manager.register(fatal)

        self.assertIsNone(fatal.require(Db))

    def test_serviceWithoutManagerIsNone(self) -> None:
        self.assertIsNone(Db(self.manager.events).require(Db))


class ResourceUsageTests(TestCase):
    def setUp(self) -> None:
        self.events = EventBus(Clock())

    async def test_snapshotCarriesStateUptimeAndReportedMetrics(self) -> None:
        worker = Worker(self.events)
        await worker.start()

        snapshot = worker.getResourceUsage()

        self.assertIs(snapshot.state, ServiceState.Running)
        self.assertGreaterEqual(snapshot.uptimeSeconds, 0)
        self.assertEqual(snapshot.gauges["queueDepth"].value, 7)
        self.assertIs(snapshot.gauges["queueDepth"].source, MetricSource.Reported)
        self.assertEqual(snapshot.counters["requests"].value, 3)
        json.dumps(snapshot.toJSON())

    def test_notStartedServiceHasNoUptime(self) -> None:
        self.assertEqual(Worker(self.events).getResourceUsage().uptimeSeconds, 0.0)

    def test_failingCollectorDoesNotRaise(self) -> None:
        snapshot = BrokenCollector(self.events).getResourceUsage()

        self.assertEqual(snapshot.serviceName, "BrokenCollector")

    async def test_runBlockingAccountsCpuTimeAndOutcome(self) -> None:
        # Runs in the real reactor thread pool: thread_time() is per worker thread
        worker = Worker(self.events)

        def burn() -> int:
            start = time.perf_counter()
            while time.perf_counter() - start < 0.2:
                pass
            return 42

        def fail() -> None:
            raise ValueError("x")

        self.assertEqual(await worker.runBlocking(burn), 42)
        await self.assertFailure(worker.runBlocking(fail), ValueError)

        snapshot = worker.getResourceUsage()
        self.assertEqual(snapshot.counters["blockingCompleted"].value, 2)
        self.assertEqual(snapshot.counters["blockingFailed"].value, 1)
        self.assertGreaterEqual(snapshot.counters["blockingCpuSeconds"].value, 0.15)
        self.assertIs(snapshot.counters["blockingCpuSeconds"].source, MetricSource.Measured)
        self.assertEqual(snapshot.gauges["blockingActive"].value, 0)
