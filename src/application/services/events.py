#!/usr/bin/env python3
"""In-process event bus for Book Injector services.

Services do not hold references to each other: facts ("a file was detected")
are published as events, commands go through ``ServiceManager.get()``.

Delivery is always deferred to the next reactor iteration (``callLater(0)``),
so a handler never runs inside ``publish()`` and cannot re-enter the publisher.
An exception in one handler is logged and does not affect the others.
"""

from __future__ import annotations

import contextlib
import inspect
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from twisted.internet.defer import ensureDeferred
from twisted.internet.interfaces import IReactorTime
from twisted.python.failure import Failure

from src.constants import DEFAULT_MAIN_LOGGER_NAME, DEFAULT_DEBUG_LOGGER_NAME
from src.enumerations import ServiceState

logger = logging.getLogger(DEFAULT_MAIN_LOGGER_NAME)
debugLogger = logging.getLogger(DEFAULT_DEBUG_LOGGER_NAME)


@dataclass(frozen=True)
class Event:
    """Base class of all events. Subclass it with a frozen dataclass."""


@dataclass(frozen=True)
class ServiceStateChanged(Event):
    serviceName: str
    oldState: ServiceState
    newState: ServiceState


@dataclass(frozen=True)
class ServiceFailed(Event):
    """A running service reported a failure (see ``BaseService.reportFailure``)."""

    serviceName: str
    error: BaseException


# Handler may be a plain function or a coroutine function
EventHandler = Callable[[Any], Any]


class EventBus:
    def __init__(self, clock: IReactorTime | None = None):
        """
        Args:
            clock: Scheduler used for deferred delivery. Defaults to the global
                reactor; pass ``twisted.internet.task.Clock`` in tests.
        """
        logger.info("Initializing EventBus")
        self._clock = clock
        self._subscribers: list[tuple[type[Event], EventHandler]] = []

    def subscribe(self, eventType: type[Event], handler: EventHandler) -> None:
        """Subscribe ``handler`` to ``eventType`` and all of its subclasses.

        Subscribing the same pair twice is a no-op.
        """
        logger.info(f"Subscribing {handler} to event type {eventType}.")
        entry = (eventType, handler)
        if entry not in self._subscribers:
            debugLogger.debug(f"Adding {handler} to the list of subscribers with event type {eventType}.")
            self._subscribers.append(entry)

    def unsubscribe(self, eventType: type[Event], handler: EventHandler) -> None:
        """Remove a subscription made with ``subscribe``; unknown pairs are ignored."""
        logger.info(f"Removing {handler} with event type {eventType}.")
        with contextlib.suppress(ValueError):
            debugLogger.debug(f"Removing {handler} from the list of subscribers with event type {eventType}.")
            self._subscribers.remove((eventType, handler))

    def publish(self, event: Event) -> None:
        """Schedule delivery of ``event`` to the handlers subscribed right now."""
        logger.info(f"Publishing event {event} to the handlers subscribed right now.")
        handlers = [
            handler
            for eventType, handler in self._subscribers
            if isinstance(event, eventType)
        ]
        for handler in handlers:
            debugLogger.debug(f"Delivering event {event} to handler {handler}.")
            # pyrefly: ignore[bad-argument-type]
            self._getClock().callLater(0, self._deliver, handler, event)

    def _getClock(self) -> IReactorTime:
        """
        Return the reactor to use for scheduling event delivery.
        """
        logger.info("Getting reactor to use for scheduling event delivery.")
        if self._clock is None:
            logger.warning("No reactor found, creating one.")
            from twisted.internet import reactor

            self._clock = reactor  # pyright: ignore[reportAttributeAccessIssue]
        return self._clock  # pyright: ignore[reportReturnType]

    def _deliver(self, handler: EventHandler, event: Event) -> None:
        logger.info(f"Delivering event {event} to handler {handler}.")
        try:
            result = handler(event)
            if inspect.isawaitable(result):
                debugLogger.info("Delivering event to handler.")
                # pyrefly: ignore[bad-argument-type]
                ensureDeferred(result).addErrback(
                    self._onHandlerFailure, handler, event
                )
        except Exception:
            logger.exception(f"Event handler {handler} failed on {event}")

    @staticmethod
    def _onHandlerFailure(
        failure: Failure, handler: EventHandler, event: Event
    ) -> None:
        logger.error(
            f"Event handler {handler} failed on {event}:\n{failure.getTraceback()}"
        )
