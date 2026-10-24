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

from src.application.services.resources import ResourceReport
from src.constants import DEFAULT_MAIN_LOGGER_NAME, DEFAULT_DEBUG_LOGGER_NAME
from src.enumerations import ServiceState

logger = logging.getLogger(DEFAULT_MAIN_LOGGER_NAME)
debugLogger = logging.getLogger(DEFAULT_DEBUG_LOGGER_NAME)


@dataclass(frozen=True)
class Event:
    """Represents an event with a type and optional details.

    Each instance of this class corresponds to a specific event and contains
    information about its type and any additional details.

    Attributes:
        type (str): The type of the event (e.g., "ERROR", "INFO", etc.).
        details (str): Additional details about the event, can be empty.
    """


@dataclass(frozen=True)
class ServiceStateChanged(Event):
    """Event representing a change in the state of a service.

    Encapsulates information regarding a state's transition for a specific
    service, including its name, old state, and new state.

    Attributes:
        serviceName (str): The name of the service undergoing the state change.
        oldState (ServiceState): The previous state of the service.
        newState (ServiceState): The new state of the service after the change.
    """
    serviceName: str
    oldState: ServiceState
    newState: ServiceState


@dataclass(frozen=True)
class ServiceFailed(Event):
    """Event representing the failure of a service.

    Detailed description of this event, which includes the name of the failed
    service and the associated error.

    Attributes:
        serviceName (str): The name of the service that failed.
        error (BaseException): The exception associated with the service failure.
    """

    serviceName: str
    error: BaseException


@dataclass(frozen=True)
class ResourceSampled(Event):
    """
    Defines the ResourceSampled event class for managing resource sampling data.
    """

    report: ResourceReport


# Handler may be a plain function or a coroutine function
EventHandler = Callable[[Any], Any]


class EventBus:
    """Event bus for handling event subscriptions and publications.

    This class provides a mechanism to subscribe handlers to event types, publish
    events to the subscribed handlers, and manage the scheduling of event delivery
    using a reactor. It supports deferred delivery of events and ensures that
    handlers are invoked with their respective events.

    Attributes:
        _clock (IReactorTime | None): The scheduler used for deferred delivery.
            Defaults to the global reactor if not provided.
        _subscribers (list[tuple[type[Event], EventHandler]]): A list of event-type
            and handler pairs representing subscriptions.
    """
    def __init__(self, clock: IReactorTime | None = None):
        """
        Module handling event-driven communication through an event bus.

        Provides an EventBus class for registering event handlers, notifying subscribers,
        and distributing events.
        """
        logger.info("Initializing EventBus")
        self._clock = clock
        self._subscribers: list[tuple[type[Event], EventHandler]] = []

    def subscribe(self, eventType: type[Event], handler: EventHandler) -> None:
        """
        Subscribe a handler to a specific event type.

        Adds a handler to the list of subscribers for a given event type. If the handler
        is already subscribed to the given event type, it won't be added again.

        Args:
            eventType (type[Event]): The event type to subscribe to.
            handler (EventHandler): The handler to process events of the given type.
        """
        logger.info(f"Subscribing {handler} to event type {eventType}.")
        entry = (eventType, handler)
        if entry not in self._subscribers:
            debugLogger.debug(f"Adding {handler} to the list of subscribers with event type {eventType}.")
            self._subscribers.append(entry)

    def unsubscribe(self, eventType: type[Event], handler: EventHandler) -> None:
        """
        Unsubscribe a handler for a specific event type.

        Removes the given handler from the list of subscribers associated with
        the specified event type. Suppresses errors if the handler is not in
        the list of subscribers.

        Args:
            eventType (type[Event]): The type of the event to unsubscribe from.
            handler (EventHandler): The handler to remove from the subscriber list.

        """
        logger.info(f"Removing {handler} with event type {eventType}.")
        with contextlib.suppress(ValueError):
            debugLogger.debug(f"Removing {handler} from the list of subscribers with event type {eventType}.")
            self._subscribers.remove((eventType, handler))

    def publish(self, event: Event) -> None:
        """
        Publish an event to currently subscribed handlers.

        This method filters handlers subscribed to the specific event type and
        delivers the event to those handlers asynchronously using the clock.

        Args:
            event (Event): The event instance to be published.
        """
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
        Retrieve the reactor to use for scheduling event delivery.

        If no reactor is found, a new reactor is created and stored for future use.

        Returns:
            IReactorTime: The reactor to use for scheduling events.
        """
        logger.info("Getting reactor to use for scheduling event delivery.")
        if self._clock is None:
            logger.warning("No reactor found, creating one.")
            from twisted.internet import reactor

            self._clock = reactor  # pyright: ignore[reportAttributeAccessIssue]

        debugLogger.debug("Returning reactor clock.")
        return self._clock  # pyright: ignore[reportReturnType]

    def _deliver(self, handler: EventHandler, event: Event) -> None:
        """
        Deliver an event to the specified handler and handle its result appropriately.

        Logs the event handling process and checks if the result from the handler is
        awaitable. If so, it ensures the deferred result is processed and any errors
        are handled via the `_onHandlerFailure` method.

        Args:
            handler (EventHandler): The handler function or callable to process the event.
            event (Event): The event to be processed by the handler.
        """
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
        """
        Handle a failure during an event handler execution and log the error.

        This function logs a detailed error message including the event handler,
        the event involved, and the failure's traceback.

        Args:
            failure (Failure): The failure object encapsulating the error details.
            handler (EventHandler): The event handler where the failure occurred.
            event (Event): The event being handled when the failure happened.
        """
        logger.error(
            f"Event handler {handler} failed on {event}:\n{failure.getTraceback()}"
        )
