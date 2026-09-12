#!/usr/bin/env python3
"""Deterministic contract tests for the X3 pre-LPF timing observer applicator."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import unittest

HERE = Path(__file__).resolve().parent
APPLICATOR = HERE / "apply_x3_prelpf_timing_observer.py"
SPEC = importlib.util.spec_from_file_location("x3_prelpf_observer", APPLICATOR)
assert SPEC is not None and SPEC.loader is not None
observer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(observer)


class X3PreLpfObserverContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_git = observer.git
        observer.git = lambda *args: observer.EXPECTED_COMMIT
        self.fixture = "\n".join(
            old for _label, old, _new, _count in observer.MARKERS
        ) + "\nBMI088_GYRO_DATA_RDY_INT\nbmp3_chip_id\n"

    def tearDown(self) -> None:
        observer.git = self.original_git

    def transformed(self) -> str:
        return observer.transform(self.fixture)

    def test_exact_transform_is_idempotent_and_fail_closed_on_partial_state(self) -> None:
        transformed = self.transformed()
        self.assertEqual("applied", observer.marker_state(transformed))
        self.assertEqual(transformed, observer.transform(transformed))

        label, old, new, _count = observer.MARKERS[0]
        partial = transformed.replace(new, old, 1)
        with self.assertRaisesRegex(SystemExit, "partial X3 independent-input observer"):
            observer.marker_state(partial)
        self.assertTrue(label)

    def test_acceleration_snapshot_is_before_the_existing_30hz_lpf(self) -> None:
        transformed = self.transformed()
        snapshot = "x3AccObserverSnapshot.accPreLpf = sensorData.acc;"
        lpf = "applyAxis3fLpf((lpf2pData*)(&accLpf), &sensorData.acc);"
        self.assertLess(transformed.index(snapshot), transformed.index(lpf))
        self.assertIn("const uint64_t x3AccReadStartUs = usecTimestamp();", transformed)
        self.assertIn("const uint64_t x3AccReadEndUs = usecTimestamp();", transformed)

    def test_packet_timestamp_latches_every_observer_field(self) -> None:
        transformed = self.transformed()
        latch_contracts = {
            "x3LogAccX": ("x3LatchAccObserver", "x3AccObserverLatch.accPreLpf.x"),
            "x3LogAccY": ("x3LatchAccObserver", "x3AccObserverLatch.accPreLpf.y"),
            "x3LogAccZ": ("x3LatchAccObserver", "x3AccObserverLatch.accPreLpf.z"),
            "x3LogAccSequence": ("x3LatchAccObserver", "x3AccObserverLatch.sequence"),
            "x3LogAccReadStart": ("x3LatchAccObserver", "x3AccObserverLatch.readStartUsLow"),
            "x3LogAccReadEnd": ("x3LatchAccObserver", "x3AccObserverLatch.readEndUsLow"),
            "x3LogBaroAsl": ("x3LatchBaroObserver", "x3BaroObserverLatch.baro.asl"),
            "x3LogBaroPressure": ("x3LatchBaroObserver", "x3BaroObserverLatch.baro.pressure"),
            "x3LogBaroTemp": ("x3LatchBaroObserver", "x3BaroObserverLatch.baro.temperature"),
            "x3LogBaroSequence": ("x3LatchBaroObserver", "x3BaroObserverLatch.sequence"),
            "x3LogBaroReadStart": ("x3LatchBaroObserver", "x3BaroObserverLatch.readStartUsLow"),
            "x3LogBaroReadEnd": ("x3LatchBaroObserver", "x3BaroObserverLatch.readEndUsLow"),
            "x3LogBaroChipId": ("x3LatchBaroObserver", "x3BaroObserverLatch.chipId"),
        }
        for function, (latcher, field) in latch_contracts.items():
            match = re.search(
                rf"static [^\n]+ {function}\(uint32_t timestamp, void\* data\)\n\{{(.*?)\n\}}",
                transformed,
                re.DOTALL,
            )
            self.assertIsNotNone(match, function)
            body = match.group(1)
            self.assertIn(f"{latcher}(timestamp);", body, function)
            self.assertIn(f"return {field};", body, function)

        for prefix in ("Acc", "Baro"):
            self.assertIn(
                f"if (timestamp != x3{prefix}ObserverLatchTimestamp)", transformed
            )
            self.assertRegex(
                transformed,
                rf"taskENTER_CRITICAL\(\);\n\s+x3{prefix}ObserverLatch = x3{prefix}ObserverSnapshot;\n\s+taskEXIT_CRITICAL\(\);",
            )
            self.assertIn(
                f"x3{prefix}ObserverLatchTimestamp = timestamp;", transformed
            )

    def test_complete_group_payloads_fit_one_log_packet(self) -> None:
        transformed = self.transformed()
        sizes = {"LOG_FLOAT": 4, "LOG_UINT32": 4, "LOG_UINT8": 1}

        def payload(group: str) -> int:
            match = re.search(
                rf"LOG_GROUP_START\({group}\)(.*?)LOG_GROUP_STOP\({group}\)",
                transformed,
                re.DOTALL,
            )
            self.assertIsNotNone(match, group)
            types = re.findall(r"LOG_ADD_BY_FUNCTION\((LOG_[A-Z0-9]+),", match.group(1))
            return sum(sizes[item] for item in types)

        self.assertEqual(24, payload("x3AccObs"))
        self.assertEqual(25, payload("x3BaroObs"))
        self.assertLessEqual(payload("x3AccObs"), 26)
        self.assertLessEqual(payload("x3BaroObs"), 26)

    def test_publication_and_latch_copy_are_bounded_critical_sections(self) -> None:
        transformed = self.transformed()
        self.assertRegex(
            transformed,
            r"(?s)taskENTER_CRITICAL\(\);\n\s+x3AccObserverSnapshot\.accPreLpf = sensorData\.acc;.*?taskEXIT_CRITICAL\(\);\n\n\s+applyAxis3fLpf",
        )
        self.assertRegex(
            transformed,
            r"(?s)taskENTER_CRITICAL\(\);\n\s+x3BaroObserverSnapshot\.baro = \*baro388;.*?taskEXIT_CRITICAL\(\);\n\n\s+measurement\.type = MeasurementTypeBarometer;",
        )


if __name__ == "__main__":
    unittest.main()
