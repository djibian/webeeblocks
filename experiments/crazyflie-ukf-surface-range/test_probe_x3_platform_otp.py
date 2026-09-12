#!/usr/bin/env python3
"""Deterministic tests for the X3 STM32 OTP provenance probe."""

from types import SimpleNamespace
import unittest

import probe_x3_platform_otp as probe


class Event:
    def __init__(self):
        self.callbacks = []

    def add_callback(self, callback):
        self.callbacks.append(callback)

    def emit(self, *args):
        for callback in list(self.callbacks):
            callback(*args)


class FakeLogConfig:
    memory = {}
    mutate_address = None
    instances = []

    def __init__(self, name, period):
        self.name = name
        self.period = period
        self.vars = []
        self.data_received_cb = Event()
        self.error_cb = Event()
        self.stopped = False
        type(self).instances.append(self)

    def add_memory(self, name, fetch_as, stored_as, address):
        self.vars.append((name, fetch_as, stored_as, address))

    def start(self):
        for sample_no in range(probe.REPEATED_SAMPLES):
            data = {}
            for name, fetch_as, stored_as, address in self.vars:
                assert fetch_as == stored_as == "uint8_t"
                value = type(self).memory[address]
                if type(self).mutate_address == address and sample_no == probe.REPEATED_SAMPLES - 1:
                    value ^= 1
                data[name] = value
            self.data_received_cb.emit(sample_no, data, self)

    def stop(self):
        self.stopped = True


class OtpProbeTests(unittest.TestCase):
    def setUp(self):
        FakeLogConfig.memory = {}
        FakeLogConfig.mutate_address = None
        FakeLogConfig.instances = []
        self.cf = SimpleNamespace(log=SimpleNamespace(add_config=lambda _: None))
        for index in range(probe.OTP_BLOCK_COUNT):
            base = probe.otp_block_address(index)
            for offset in range(probe.OTP_BLOCK_LEN):
                FakeLogConfig.memory[base + offset] = 0

    def install_block(self, index, payload: bytes):
        self.assertLessEqual(len(payload), probe.OTP_BLOCK_LEN)
        base = probe.otp_block_address(index)
        data = payload + bytes(probe.OTP_BLOCK_LEN - len(payload))
        for offset, value in enumerate(data):
            FakeLogConfig.memory[base + offset] = value

    def test_exact_firmware_block_selection_and_fallback(self):
        starts = bytes([0, 0, ord("0")] + [0] * 13)
        self.assertEqual(probe.select_platform_block(starts), (2, "selected-first-nonzero-block"))
        starts = bytes([0, 0xFF] + [0] * 14)
        self.assertEqual(probe.select_platform_block(starts), (None, "firmware-fallback-first-nonzero-is-ff"))
        self.assertEqual(probe.select_platform_block(bytes(16)), (None, "firmware-fallback-no-nonzero-block"))

    def test_parse_accepts_only_explicit_cf21_and_retains_revision(self):
        parsed = probe.parse_platform_block(b"0;CF21;R=B1\0" + bytes(20))
        self.assertEqual(parsed["device_type"], "CF21")
        self.assertEqual(parsed["revision_field"], "B1")
        self.assertEqual(parsed["identity_verdict"], "EXPLICIT_CF21")
        other = probe.parse_platform_block(b"0;CF20\0" + bytes(25))
        self.assertEqual(other["identity_verdict"], "UNPROVEN")

    def test_probe_reads_selected_cf21_block_in_bounded_groups(self):
        self.install_block(3, b"0;CF21;R=B1\0")
        result = probe.observe_otp(self.cf, FakeLogConfig)
        self.assertEqual(result["selected_block_index"], 3)
        self.assertEqual(result["platform_string"], "0;CF21;R=B1")
        self.assertEqual(result["identity_verdict"], "EXPLICIT_CF21")
        self.assertEqual(result["electrical_interrupt_source"], "UNPROVEN")
        self.assertIsNone(result["physical_verdict"])
        self.assertEqual(len(FakeLogConfig.instances), 11)  # 4 start groups + 7 block groups
        self.assertTrue(all(1 <= len(config.vars) <= 5 for config in FakeLogConfig.instances))
        self.assertTrue(all(config.period == probe.LOG_PERIOD_MS for config in FakeLogConfig.instances))
        self.assertTrue(all(config.stopped for config in FakeLogConfig.instances))

    def test_fallback_does_not_invent_cf20_or_revision(self):
        FakeLogConfig.memory[probe.otp_block_address(1)] = 0xFF
        result = probe.observe_otp(self.cf, FakeLogConfig)
        self.assertIsNone(result["selected_block_index"])
        self.assertIsNone(result["platform_string"])
        self.assertEqual(result["identity_verdict"], "UNPROVEN")
        self.assertEqual(len(FakeLogConfig.instances), 4)

    def test_changed_repeated_memory_observation_fails_closed(self):
        self.install_block(2, b"0;CF21\0")
        FakeLogConfig.mutate_address = probe.otp_block_address(2)
        with self.assertRaisesRegex(RuntimeError, "changed"):
            probe.observe_otp(self.cf, FakeLogConfig)

    def test_describe_preserves_scope_and_packet_limit(self):
        description = probe.describe()
        self.assertEqual(description["pinned_firmware_commit"], probe.PINNED_FIRMWARE_COMMIT)
        self.assertEqual(description["pinned_cflib_commit_required"], probe.PINNED_CFLIB_COMMIT)
        self.assertEqual(description["max_memory_variables_per_log_config"], 5)
        self.assertEqual(description["electrical_interrupt_source"], "UNPROVEN")
        self.assertIsNone(description["physical_verdict"])


if __name__ == "__main__":
    unittest.main()
