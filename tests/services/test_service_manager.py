"""ServiceManager: registry, dependency-ordered lifecycle, resources, shutdown."""

from __future__ import annotations

import json

from twisted.internet import reactor
from twisted.internet.defer import ensureDeferred
from twisted.trial.unittest import TestCase

from src.application.services import (
    BaseService,
    ResourceSampled,
    ServiceStateChanged,
)
from src.enumerations import FailurePolicy, MetricSource, ServiceState
from tests.services import helpers
from tests.services.helpers import Bad, Child, Db, Fatal, Ocr, SlowStop, newManager


class Worker(BaseService):
    def collectResources(self) -> None:
        self.resources.gauge("queueDepth", 7)


class Tolerant(BaseService):
    failurePolicy = FailurePolicy.Ignore


class ManagerTestCase(TestCase):
    def setUp(self) -> None:
        helpers.journal.clear()
        self.manager, self.clock = newManager()
        self.events = self.manager.events


class LifecycleTests(ManagerTestCase):
    def registerAll(self) -> None:
        # Registered in reverse on purpose: the order must come from dependsOn
        for service in (Child, Ocr, Bad, Db):
            self.manager.register(service(self.events))

    async def test_startsInDependencyOrderAndSkipsDependentsOfFailedOnes(self) -> None:
        self.registerAll()

        self.assertTrue(await self.manager.startAll())  # Bad is Ignore: carry on

        self.assertEqual(helpers.journal, ["start Db", "start Ocr"])
        self.assertIs(self.manager.get(Ocr).state, ServiceState.Running)
        self.assertIs(self.manager.get(Bad).state, ServiceState.Failed)
        self.assertIs(self.manager.get(Child).state, ServiceState.New)  # Bad is not Running

    async def test_stopsInReverseDependencyOrder(self) -> None:
        self.registerAll()
        seen: list[tuple[str, ServiceState]] = []
        self.events.subscribe(
            ServiceStateChanged, lambda e: seen.append((e.serviceName, e.newState))
        )
        await self.manager.startAll()

        await self.manager.stopAll()

        self.assertEqual(helpers.journal[2:], ["stop Ocr", "stop Db"])
        self.clock.advance(0)
        self.assertIn(("Db", ServiceState.Running), seen)
        self.assertIn(("Db", ServiceState.Stopped), seen)

    async def test_failFastRollsBackWhatWasStarted(self) -> None:
        self.manager.register(Db(self.events, name="Db2"))
        self.manager.register(Fatal(self.events))

        self.assertFalse(await self.manager.startAll())

        self.assertEqual(helpers.journal, ["start Db2", "stop Db2"])
        self.assertIs(self.manager.get(Db).state, ServiceState.Stopped)
        self.assertIs(self.manager.get(Fatal).state, ServiceState.Failed)

    async def test_dependencyCycleRefusesToStartAnything(self) -> None:
        class A(BaseService):
            pass

        class B(BaseService):
            dependsOn = (A,)

        A.dependsOn = (B,)
        a, b = A(self.events), B(self.events)
        self.manager.register(a)
        self.manager.register(b)

        self.assertFalse(await self.manager.startAll())

        self.assertIs(a.state, ServiceState.New)
        self.assertIs(b.state, ServiceState.New)

    async def test_unregisteredDependencyRefusesToStartAnything(self) -> None:
        ocr = Ocr(self.events)  # needs Db, which is not registered
        tolerant = Tolerant(self.events)
        self.manager.register(tolerant)
        self.manager.register(ocr)

        self.assertFalse(await self.manager.startAll())

        self.assertIs(ocr.state, ServiceState.New)
        self.assertIs(tolerant.state, ServiceState.New)  # nothing was started
        self.assertEqual(helpers.journal, [])

    async def test_stopAllOnInvalidGraphFallsBackToReverseRegistration(self) -> None:
        db, ocr = Db(self.events), Ocr(self.events)
        self.manager.register(db)
        self.manager.register(ocr)
        await db.start()
        await ocr.start()
        # Make the graph invalid: a service depending on a type nobody registered
        self.manager.register(NeedsMissing(self.events))

        await self.manager.stopAll()  # must not raise

        self.assertEqual(helpers.journal, ["start Db", "start Ocr", "stop Ocr", "stop Db"])
        self.assertIs(db.state, ServiceState.Stopped)
        self.assertIs(ocr.state, ServiceState.Stopped)

    async def test_startingTheManagerAsTwistedServiceStartsAll(self) -> None:
        self.manager.register(Db(self.events))

        await self.manager.startService()

        self.assertIs(self.manager.get(Db).state, ServiceState.Running)
        await self.manager.stopService()
        self.assertIs(self.manager.get(Db).state, ServiceState.Stopped)


class NeedsMissing(BaseService):
    dependsOn = (Tolerant,)


class RegistryTests(ManagerTestCase):
    def test_lookupsNeverRaise(self) -> None:
        db = Db(self.events)
        self.manager.register(db)

        self.assertIs(self.manager.get(Db), db)
        self.assertIs(self.manager.getByName("Db"), db)
        self.assertIsNone(self.manager.get(Fatal))
        self.assertIsNone(self.manager.getByName("nope"))

    def test_statusMapsNamesToStates(self) -> None:
        self.manager.register(Db(self.events))
        self.manager.register(Ocr(self.events))

        self.assertEqual(
            self.manager.status(),
            {"Db": ServiceState.New, "Ocr": ServiceState.New},
        )


class ResourceTests(ManagerTestCase):
    async def test_reportCoversProcessAndEveryService(self) -> None:
        self.manager.register(Worker(self.events))
        self.manager.register(Db(self.events))
        await self.manager.startAll()

        report = self.manager.getResourceUsage()

        self.assertGreater(report.process["rssBytes"].value, 0)
        self.assertIs(report.process["rssBytes"].source, MetricSource.Measured)
        self.assertEqual(set(report.services), {"Worker", "Db"})
        self.assertEqual(report.services["Worker"].gauges["queueDepth"].value, 7)
        json.dumps(report.toJSON())

    async def test_samplingPublishesReportsUntilStopped(self) -> None:
        self.manager.register(Worker(self.events))
        sampled: list[ResourceSampled] = []
        self.events.subscribe(ResourceSampled, sampled.append)
        await self.manager.startAll()

        self.assertFalse(self.manager.startSampling(0))  # invalid interval
        self.assertTrue(self.manager.startSampling(5, clock=self.clock))
        self.assertFalse(self.manager.startSampling(5, clock=self.clock))  # already running

        self.clock.advance(5)
        self.clock.advance(0)
        self.assertEqual(len(sampled), 1)
        self.assertIn("Worker", sampled[0].report.services)

        await self.manager.stopAll()  # also stops the sampler
        self.clock.advance(10)
        self.clock.advance(0)
        self.assertEqual(len(sampled), 1)


class ShutdownTests(ManagerTestCase):
    def setUp(self) -> None:
        super().setUp()
        # The test reactor is running: never let the manager stop it
        self.reactorStops = 0
        self.patch(reactor, "stop", self.fakeStop)

    def fakeStop(self) -> None:
        self.reactorStops += 1

    async def test_shutdownStopsServicesAndReactorOnce(self) -> None:
        db = Db(self.events)
        self.manager.register(db)
        await db.start()

        self.manager.shutdown()
        self.manager.shutdown()  # second call is a no-op

        self.assertTrue(self.manager.isShuttingDown)
        self.assertIs(db.state, ServiceState.Stopped)
        self.assertEqual(self.reactorStops, 1)

    async def test_shutdownDeferredFiresAfterServicesStopped(self) -> None:
        slow = SlowStop(self.events)
        self.manager.register(slow)
        await slow.start()

        done = self.manager.shutdown()
        self.assertFalse(done.called)
        self.assertEqual(self.reactorStops, 0)
        self.assertIs(self.manager.shutdown(), done)  # idempotent

        slow.release.callback(None)

        self.assertTrue(done.called)
        self.assertIs(slow.state, ServiceState.Stopped)
        self.assertEqual(self.reactorStops, 1)

    async def test_stopAllDuringStopInFlightWaitsForIt(self) -> None:
        slow = SlowStop(self.events)
        self.manager.register(slow)
        await slow.start()

        first = ensureDeferred(self.manager.stopAll())
        second = ensureDeferred(self.manager.stopAll())  # e.g. a signal during shutdown()
        self.assertFalse(first.called)
        self.assertFalse(second.called)

        slow.release.callback(None)

        self.assertTrue(first.called)
        self.assertTrue(second.called)
        self.assertEqual(slow.stopCalls, 1)

    async def test_shutdownDuringStopAllWaitsForIt(self) -> None:
        slow = SlowStop(self.events)
        self.manager.register(slow)
        await slow.start()

        stopping = ensureDeferred(self.manager.stopAll())  # reactor stop by a signal
        done = self.manager.shutdown()  # a FailFast service failed meanwhile
        self.assertFalse(done.called)

        slow.release.callback(None)

        self.assertTrue(stopping.called)
        self.assertTrue(done.called)
        self.assertEqual(slow.stopCalls, 1)

    async def test_failFastServiceFailureShutsDown(self) -> None:
        db = Db(self.events)
        self.manager.register(db)
        await db.start()

        db.reportFailure(RuntimeError("lost"))
        self.clock.advance(0)

        self.assertTrue(self.manager.isShuttingDown)
        self.assertEqual(self.reactorStops, 1)

    async def test_ignoredServiceFailureKeepsRunning(self) -> None:
        tolerant = Tolerant(self.events)
        self.manager.register(tolerant)
        await tolerant.start()

        tolerant.reportFailure(RuntimeError("lost"))
        self.clock.advance(0)

        self.assertFalse(self.manager.isShuttingDown)
        self.assertEqual(self.reactorStops, 0)
