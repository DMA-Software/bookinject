"""Services shared by the services test suites."""

from __future__ import annotations

from twisted.internet.defer import Deferred
from twisted.internet.task import Clock

from src.application.services import BaseService, EventBus, ServiceManager
from src.enumerations import FailurePolicy

# Hook calls of the services below, in call order; tests clear it in setUp()
journal: list[str] = []


class Db(BaseService):
    async def onStart(self) -> None:
        journal.append(f"start {self.name}")

    async def onStop(self) -> None:
        journal.append(f"stop {self.name}")


class SlowStop(BaseService):
    """onStop() takes as long as the test wants: fire ``release`` to finish it."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.release: Deferred[None] = Deferred()
        self.stopCalls = 0

    async def onStop(self) -> None:
        self.stopCalls += 1
        await self.release


class Ocr(BaseService):
    dependsOn = (Db,)

    async def onStart(self) -> None:
        journal.append(f"start {self.name}")

    async def onStop(self) -> None:
        journal.append(f"stop {self.name}")


class Bad(BaseService):
    """Fails to start; the manager must carry on without it."""

    dependsOn = (Db,)
    failurePolicy = FailurePolicy.Ignore

    async def onStart(self) -> None:
        raise RuntimeError("boom")


class Child(BaseService):
    dependsOn = (Bad,)


class Fatal(BaseService):
    """Fails to start and, being FailFast, takes the application down."""

    async def onStart(self) -> None:
        raise RuntimeError("fatal")


def newManager() -> tuple[ServiceManager, Clock]:
    """A manager whose event delivery is driven by the returned fake clock."""
    clock = Clock()
    return ServiceManager(EventBus(clock)), clock
