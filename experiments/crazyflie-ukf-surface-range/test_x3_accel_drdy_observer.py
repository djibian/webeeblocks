#!/usr/bin/env python3
"""Deterministic contract tests for the X3 BMI088 accelerometer-DRDY observer."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import unittest

HERE = Path(__file__).resolve().parent
APPLICATOR = HERE / "apply_x3_accel_drdy_observer.py"
SPEC = importlib.util.spec_from_file_location("x3_accel_drdy_observer", APPLICATOR)
assert SPEC is not None and SPEC.loader is not None
observer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(observer)


class X3AccelDrdyObserverContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_git = observer.git
        observer.git = lambda *args: observer.EXPECTED_COMMIT
        self.fixture = "\n".join(
            old for _label, old, _new, _count in observer.MARKERS
        ) + "\nLOG_GROUP_START(x3AccObs)\nBMI088_GYRO_DATA_RDY_INT\nEXTI_PinSource14\n"

    def tearDown(self) -> None:
        observer.git = self.original_git

    def transformed(self) -> str:
        return observer.transform(self.fixture)

    def test_exact_transform_is_idempotent_and_fail_closed_on_partial_state(self) -> None:
        transformed = self.transformed()
        self.assertEqual("applied", observer.marker_state(transformed))
        self.assertEqual(transformed, observer.transform(transformed))

        _label, old, new, _count = observer.MARKERS[0]
        partial = transformed.replace(new, old, 1)
        with self.assertRaisesRegex(SystemExit, "partial X3 accelerometer-DRDY observer"):
            observer.marker_state(partial)

    def test_accelerometer_drdy_is_explicitly_mapped_to_int1(self) -> None:
        transformed = self.transformed()
        self.assertIn(
            "x3AccelIntConfig.accel_int_channel = BMI088_INT_CHANNEL_1;",
            transformed,
        )
        self.assertIn(
            "x3AccelIntConfig.accel_int_type = BMI088_ACCEL_DATA_RDY_INT;",
            transformed,
        )
        self.assertIn(
            "rslt |= bmi088_set_accel_int_config(&x3AccelIntConfig, &bmi088Dev);",
            transformed,
        )

    def test_pc13_observer_does_not_wake_or_retime_sensor_task(self) -> None:
        transformed = self.transformed()
        match = re.search(
            r"void __attribute__\(\(used\)\) EXTI13_Callback\(void\)\n"
            r"\{(.*?)\n\}\n\nvoid sensorsBmi088Bmp3xxDataAvailableCallback",
            transformed,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group(1)
        self.assertIn("x3AccelDrdyTimestampUsLow = (uint32_t)usecTimestamp();", body)
        self.assertIn("x3AccelDrdySequence++;", body)
        self.assertNotIn("vTaskNotifyGiveFromISR", body)
        self.assertNotIn("portYIELD", body)
        self.assertNotIn("imuIntTimestamp", body)
        self.assertIn("void sensorsBmi088Bmp3xxDataAvailableCallback(void)", transformed)

    def test_pc13_and_existing_pc14_paths_are_both_configured(self) -> None:
        transformed = self.transformed()
        self.assertIn("GPIO_InitStructure.GPIO_Pin = GPIO_Pin_13;", transformed)
        self.assertIn(
            "SYSCFG_EXTILineConfig(EXTI_PortSourceGPIOC, EXTI_PinSource13);",
            transformed,
        )
        self.assertIn("EXTI_InitStructure.EXTI_Line = EXTI_Line13;", transformed)
        self.assertIn("GPIO_InitStructure.GPIO_Pin = GPIO_Pin_14;", transformed)
        self.assertIn(
            "SYSCFG_EXTILineConfig(EXTI_PortSourceGPIOC, EXTI_PinSource14);",
            transformed,
        )
        self.assertIn("EXTI_InitStructure.EXTI_Line = EXTI_Line14;", transformed)

    def test_each_accel_read_is_bracketed_by_coherent_drdy_observations(self) -> None:
        transformed = self.transformed()
        before = transformed.index("x3AccDrdySequenceBefore = x3AccelDrdySequence;")
        read = transformed.index("sensorsAccelGet(&accelRaw);", before)
        after = transformed.index("x3AccDrdySequenceAfter = x3AccelDrdySequence;", read)
        publish = transformed.index(
            "x3AccDrdyObserverSnapshot.accSequence = x3AccObserverSnapshot.sequence;",
            after,
        )
        self.assertLess(before, read)
        self.assertLess(read, after)
        self.assertLess(after, publish)
        self.assertIn(
            "x3AccDrdyObserverSnapshot.drdyTimestampBeforeUsLow = "
            "x3AccDrdyTimestampBeforeUsLow;",
            transformed,
        )
        self.assertIn(
            "x3AccDrdyObserverSnapshot.drdyTimestampAfterUsLow = "
            "x3AccDrdyTimestampAfterUsLow;",
            transformed,
        )

    def test_drdy_group_fits_one_log_packet_and_joins_by_acc_sequence(self) -> None:
        transformed = self.transformed()
        match = re.search(
            r"LOG_GROUP_START\(x3AccDrdy\)(.*?)LOG_GROUP_STOP\(x3AccDrdy\)",
            transformed,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group(1)
        entries = re.findall(
            r"LOG_ADD_BY_FUNCTION\((LOG_[A-Z0-9]+), ([A-Za-z0-9_]+),", body
        )
        self.assertEqual(5, len(entries))
        self.assertEqual(20, sum(4 for type_name, _name in entries if type_name == "LOG_UINT32"))
        self.assertIn(("LOG_UINT32", "accSeq"), entries)

    def test_build_oracle_requires_cf21_only_sensor_configuration(self) -> None:
        oracle = (HERE / "run_x3_prelpf_build_oracle.sh").read_text(encoding="utf-8")
        self.assertIn("# CONFIG_SENSORS_MPU9250_LPS25H is not set", oracle)
        self.assertIn("CONFIG_SENSORS_BMI088_BMP3XX=y", oracle)
        self.assertIn("apply_x3_accel_drdy_observer.py", oracle)
        self.assertIn("test_x3_accel_drdy_observer.py", oracle)


if __name__ == "__main__":
    unittest.main()
