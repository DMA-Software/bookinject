"""ResourceMeter and ProcessMonitor."""

from __future__ import annotations

from twisted.trial.unittest import TestCase

from src.application.services import ProcessMonitor, ResourceMeter
from src.enumerations import MetricSource


class ResourceMeterTests(TestCase):
    def setUp(self) -> None:
        self.meter = ResourceMeter()

    def test_countAccumulatesAndKeepsSourceAndUnit(self) -> None:
        self.meter.count("requests", 3, unit="req")
        self.meter.count("requests", 2, unit="req")

        counters, gauges = self.meter.read()
        self.assertEqual(counters["requests"].value, 5)
        self.assertEqual(counters["requests"].unit, "req")
        self.assertIs(counters["requests"].source, MetricSource.Reported)
        self.assertEqual(gauges, {})

    def test_counterCannotDecrease(self) -> None:
        self.meter.count("x", -1)  # rejected, must not raise

        self.assertNotIn("x", self.meter.read()[0])

    def test_emptyNameIsRejected(self) -> None:
        self.meter.count("", 1)
        self.meter.gauge("", 1)
        self.meter.gaugeAdd("", 1)

        self.assertEqual(self.meter.read(), ({}, {}))

    def test_gaugeAcceptsIntAndFloat(self) -> None:
        # regression: the type check used to reject every value
        self.meter.gauge("queueDepth", 7)
        self.meter.gauge("load", 0.5, MetricSource.Measured, "%")

        gauges = self.meter.read()[1]
        self.assertEqual(gauges["queueDepth"].value, 7)
        self.assertEqual(gauges["load"].value, 0.5)
        self.assertIs(gauges["load"].source, MetricSource.Measured)
        self.assertEqual(gauges["load"].unit, "%")

    def test_gaugeRejectsNonNumbers(self) -> None:
        self.meter.gauge("x", "7")  # type: ignore[arg-type]
        self.meter.gaugeAdd("y", "7")  # type: ignore[arg-type]

        self.assertEqual(self.meter.read()[1], {})

    def test_booleansAndNonFiniteNumbersAreRejected(self) -> None:
        for bad in (True, False, float("nan"), float("inf"), float("-inf")):
            self.meter.count("c", bad)  # type: ignore[arg-type]
            self.meter.gauge("g", bad)
            self.meter.gaugeAdd("a", bad)

        self.assertEqual(self.meter.read(), ({}, {}))

    def test_countRejectsNonNumbersWithoutRaising(self) -> None:
        self.meter.count("c", "3")  # type: ignore[arg-type]
        self.meter.count("c", None)  # type: ignore[arg-type]

        self.assertEqual(self.meter.read()[0], {})

    def test_rejectedValueKeepsThePreviousOne(self) -> None:
        self.meter.count("c", 2)
        self.meter.count("c", float("nan"))
        self.meter.gauge("g", 5)
        self.meter.gauge("g", True)

        counters, gauges = self.meter.read()
        self.assertEqual(counters["c"].value, 2)
        self.assertEqual(gauges["g"].value, 5)

    def test_gaugeOverwrites(self) -> None:
        self.meter.gauge("queueDepth", 7)
        self.meter.gauge("queueDepth", 2)

        self.assertEqual(self.meter.read()[1]["queueDepth"].value, 2)

    def test_gaugeAddCreatesThenAdds(self) -> None:
        self.meter.gaugeAdd("active", 1)
        self.meter.gaugeAdd("active", 1)
        self.meter.gaugeAdd("active", -1)

        self.assertEqual(self.meter.read()[1]["active"].value, 1)

    def test_readReturnsCopies(self) -> None:
        self.meter.count("x", 1)

        self.meter.read()[0].clear()

        self.assertIn("x", self.meter.read()[0])


class ProcessMonitorTests(TestCase):
    def test_currentProcessIsMeasured(self) -> None:
        # regression: the constructor used to log the nonexistent Process.info
        metrics = ProcessMonitor().read()

        self.assertGreater(metrics["rssBytes"].value, 0)
        self.assertIs(metrics["rssBytes"].source, MetricSource.Measured)
        self.assertEqual(metrics["rssBytes"].unit, "B")

    def test_missingProcessYieldsNoMetrics(self) -> None:
        self.assertEqual(ProcessMonitor(99999999).read(), {})
