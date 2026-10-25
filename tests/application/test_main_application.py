"""MainApplication: wiring of the ServiceManager into the reactor."""

from __future__ import annotations

from pathlib import Path

from twisted.internet import reactor
from twisted.internet.defer import ensureDeferred
from twisted.trial.unittest import TestCase

from src.application.main_application import MainApplication
from src.application.services import BaseService
from src.enumerations import ServiceState
from tests.services.helpers import Db, Fatal

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_CONFIG = PROJECT_ROOT / "tests" / "fixtures" / "bookinjector.xml"
# FileLoggerConfig.validate() requires an existing writable log directory
LOG_PATH_ANCHOR = "/path/to/log/file.log"


class MainApplicationTests(TestCase):
    def setUp(self) -> None:
        tmp = Path(self.mktemp())
        tmp.mkdir(parents=True)
        configFile = tmp / "bookinjector.xml"
        configFile.write_text(
            FIXTURE_CONFIG.read_text(encoding="utf-8").replace(
                LOG_PATH_ANCHOR, (tmp / "file.log").as_posix()
            ),
            encoding="utf-8",
        )
        self.app = MainApplication(str(configFile), daemonize=True)

        # The test reactor is running (or shared): record, never execute
        self.calls: list[tuple] = []
        self.patch(reactor, "addSystemEventTrigger", lambda *a: self.calls.append(("trigger", *a)))
        self.patch(reactor, "callWhenRunning", lambda f, *a, **k: self.calls.append(("running", f)))
        self.patch(reactor, "run", lambda: self.calls.append(("run",)))
        self.patch(reactor, "stop", lambda: self.calls.append(("stop",)))

    def register(self, *services: BaseService) -> None:
        for service in services:
            self.app.services.register(service)

    def test_runRegistersTriggersThenRunsReactor(self) -> None:
        self.assertEqual(self.app.run(), 0)

        kinds = [call[0] for call in self.calls]
        self.assertEqual(kinds, ["trigger", "running", "run"])
        self.assertEqual(self.calls[0][1:3], ("before", "shutdown"))

    async def test_startupStartsServices(self) -> None:
        self.register(Db(self.app.events))
        self.app.run()

        await ensureDeferred(self.app._startServices())

        self.assertIs(self.app.services.get(Db).state, ServiceState.Running)
        self.assertEqual(self.app.exitCode, 0)
        self.assertNotIn(("stop",), self.calls)

    async def test_failedStartupShutsDownWithExitCode(self) -> None:
        self.register(Fatal(self.app.events))
        self.app.run()

        await ensureDeferred(self.app._startServices())

        self.assertEqual(self.app.exitCode, 1)
        self.assertEqual(self.calls.count(("stop",)), 1)

    async def test_reactorShutdownStopsServices(self) -> None:
        self.register(Db(self.app.events))
        self.app.run()
        await ensureDeferred(self.app._startServices())
        stopTrigger = self.calls[0][3]

        await stopTrigger()

        self.assertIs(self.app.services.get(Db).state, ServiceState.Stopped)

    async def test_reactorShutdownAfterManagerShutdownDoesNotStopTwice(self) -> None:
        self.register(Db(self.app.events))
        self.app.run()
        await ensureDeferred(self.app._startServices())
        stopTrigger = self.calls[0][3]

        self.app.services.shutdown()  # e.g. a FailFast service failed
        await stopTrigger()

        self.assertEqual(self.calls.count(("stop",)), 1)
        self.assertIs(self.app.services.get(Db).state, ServiceState.Stopped)
