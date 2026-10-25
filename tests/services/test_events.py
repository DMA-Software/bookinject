"""EventBus: deferred delivery, subscription bookkeeping, handler isolation."""

from __future__ import annotations

from twisted.internet.task import Clock
from twisted.trial.unittest import TestCase

from src.application.services import EventBus, ServiceFailed, ServiceStateChanged
from src.enumerations import ServiceState


class EventBusTests(TestCase):
    def setUp(self) -> None:
        self.clock = Clock()
        self.bus = EventBus(self.clock)
        self.changed = ServiceStateChanged("Db", ServiceState.New, ServiceState.Starting)

    def test_deliveryIsDeferredToTheNextIteration(self) -> None:
        seen: list[object] = []
        self.bus.subscribe(ServiceStateChanged, seen.append)

        self.bus.publish(self.changed)
        self.assertEqual(seen, [])  # never inside publish()

        self.clock.advance(0)
        self.assertEqual(seen, [self.changed])

    def test_handlerGetsOnlyItsEventType(self) -> None:
        seen: list[object] = []
        self.bus.subscribe(ServiceFailed, seen.append)

        self.bus.publish(self.changed)
        self.clock.advance(0)

        self.assertEqual(seen, [])

    def test_duplicateSubscriptionIsIgnored(self) -> None:
        seen: list[object] = []
        self.bus.subscribe(ServiceStateChanged, seen.append)
        self.bus.subscribe(ServiceStateChanged, seen.append)

        self.bus.publish(self.changed)
        self.clock.advance(0)

        self.assertEqual(len(seen), 1)

    def test_unsubscribeStopsDelivery(self) -> None:
        seen: list[object] = []
        self.bus.subscribe(ServiceStateChanged, seen.append)
        self.bus.unsubscribe(ServiceStateChanged, seen.append)
        self.bus.unsubscribe(ServiceStateChanged, seen.append)  # unknown pair: no error

        self.bus.publish(self.changed)
        self.clock.advance(0)

        self.assertEqual(seen, [])

    def test_failingHandlerDoesNotAffectOthers(self) -> None:
        seen: list[object] = []

        def broken(event: object) -> None:
            raise RuntimeError("handler bug")

        self.bus.subscribe(ServiceStateChanged, broken)
        self.bus.subscribe(ServiceStateChanged, seen.append)

        self.bus.publish(self.changed)
        self.clock.advance(0)

        self.assertEqual(seen, [self.changed])

    def test_coroutineHandlerIsAwaited(self) -> None:
        seen: list[object] = []

        async def handler(event: object) -> None:
            seen.append(event)

        async def brokenHandler(event: object) -> None:
            raise RuntimeError("handler bug")

        self.bus.subscribe(ServiceStateChanged, brokenHandler)
        self.bus.subscribe(ServiceStateChanged, handler)

        self.bus.publish(self.changed)
        self.clock.advance(0)

        self.assertEqual(seen, [self.changed])
