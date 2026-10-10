#!/usr/bin/env python3
"""Exercise the real host takeoff factory and actual command-9 exclusion."""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json
import socket
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools/physical"), str(ROOT / "tools/ci")]
import dynamic_run_activation as activation
import pre_takeoff_range_readiness as readiness
import test_physical_takeoff_transport as takeoff_test
import teacher_run_authorization as teacher
from physical_run_activation import PhysicalRunActivationError
from range_observer import RangeObservation, range_mm_to_m

BINDING = (ROOT / "tools/ci/fixtures/physical_fail_554_ast.json").read_text().strip()


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.cf = object()
        self.epoch = "readiness-epoch"
        self.events = []
        self.raw = 1000
        self.filter_values = ["1", "1"]
        self.ctype = "uint16_t"
        self.open_error = self.close_error = None
        self.on_read = self.on_close = lambda: None
        self.sample_override = None
        test = self

        class Adapter:
            def __init__(self, cf):
                test.assertIs(cf, test.cf)
            def describe(self, name):
                test.assertEqual(name, "multiranger.filterMask")
                return test.ctype, True, "cached-value-is-not-used"
            def read_fresh(self, name):
                test.events.append(("filter", name))
                return test.filter_values.pop(0)

        class Observer:
            def __init__(self, cf, epoch_reader, direction):
                self.bound_crazyflie = cf
                self.bound_connection_epoch = None
                self.direction = direction
                self.epoch_reader = epoch_reader
            def open(self):
                test.events.append(("open", self.direction))
                self.bound_connection_epoch = self.epoch_reader()
                if test.open_error:
                    raise test.open_error
            def read(self):
                test.events.append(("read", self.direction))
                test.on_read()
                if test.sample_override is not None:
                    return test.sample_override
                return RangeObservation(self.bound_connection_epoch, 200, self.direction,
                                        test.raw, range_mm_to_m(test.raw))
            def close(self):
                test.events.append(("close", self.direction))
                test.on_close()
                if test.close_error:
                    raise test.close_error

        self.adapter_patch = patch.object(readiness, "CflibParamAdapter", Adapter)
        self.observer_patch = patch.object(readiness, "FreshRangeObserver", Observer)
        self.adapter_patch.start()
        self.observer_patch.start()
        self.addCleanup(self.adapter_patch.stop)
        self.addCleanup(self.observer_patch.stop)

    def check(self, binding=BINDING):
        return readiness.require_pre_takeoff_ranges(self.cf, lambda: self.epoch, binding)

    def test_historical_demand_and_no_sensor_program(self):
        self.assertEqual(readiness.demanded_range_directions(BINDING), ("front",))
        samples = self.check()
        self.assertEqual(samples, (RangeObservation(self.epoch, 200, "front", 1000, 1.0),))
        self.assertEqual(self.events, [("filter", "multiranger.filterMask"),
                                     ("open", "front"), ("read", "front"), ("close", "front"),
                                     ("filter", "multiranger.filterMask")])
        self.events.clear()
        self.assertEqual(self.check(takeoff_test.canonical_ast()), ())
        self.assertFalse(self.events, "an AST without range must not demand Multi-ranger")

    def test_both_branches_nested_expressions_and_deduplication(self):
        ast = json.loads(BINDING)
        condition = ast["program"][3]["condition"]
        condition["right"] = {"kind": "range", "direction": "left", "unit": "m"}
        ast["program"][3]["else"] = [{"kind": "if", "condition": condition,
            "then": [], "else": [{"kind": "set_variable", "variable": {"id": "x", "name": "x"},
                "value": {"kind": "range", "direction": "up", "unit": "m"}}]}]
        from takeoff_command import _canonical_json
        binding = _canonical_json(ast)
        self.assertEqual(readiness.demanded_range_directions(binding), ("front", "left", "up"))
        self.assertEqual(len(self.check(binding)), 3)
        self.assertEqual([e for e in self.events if e[0] == "read"],
                         [("read", "front"), ("read", "left"), ("read", "up")])

    def test_unavailable_never_skipped_to_a_later_finite_sample(self):
        for raw in (8000, 32766, 32767, 65535):
            with self.subTest(raw=raw):
                self.raw = raw
                self.events.clear()
                self.filter_values = ["1", "1"]
                with self.assertRaisesRegex(Exception, "unavailable"):
                    self.check()
                self.assertEqual(self.events.count(("read", "front")), 1)
                self.assertEqual(self.events.count(("close", "front")), 1)

    def test_filter_must_be_typed_fresh_default_before_and_after_samples(self):
        for values, ctype in ((["3"], "uint16_t"), (["1"], "uint8_t"),
                              (["bad"], "uint16_t"), (["1", "3"], "uint16_t")):
            with self.subTest(values=values, ctype=ctype):
                self.filter_values = values.copy()
                self.ctype = ctype
                with self.assertRaises(Exception):
                    self.check()

    def test_epoch_loss_and_wrong_sample_binding_fail_closed(self):
        for sample in (RangeObservation("another-epoch", 200, "front", 1000, 1.0),
                       RangeObservation(self.epoch, 200, "left", 1000, 1.0),
                       RangeObservation(self.epoch, 200, "front", 32766, 1.0),
                       RangeObservation(self.epoch, True, "front", 1000, 1.0),
                       RangeObservation(self.epoch, 200, "front", 1000, float("nan"))):
            self.filter_values = ["1", "1"]
            self.sample_override = sample
            with self.assertRaises(Exception):
                self.check()
        self.sample_override = None
        self.filter_values = ["1", "1"]
        self.on_close = lambda: setattr(self, "epoch", "reconnected")
        with self.assertRaisesRegex(Exception, "epoch changed"):
            self.check()

    def test_open_and_close_failure_preserve_cause_without_retry(self):
        self.open_error = RuntimeError("injected open timeout")
        self.close_error = RuntimeError("injected uncertain closure")
        with self.assertRaisesRegex(Exception, "cleanup uncertain") as result:
            self.check()
        self.assertIs(result.exception.__cause__, self.open_error)
        self.assertEqual(self.events.count(("open", "front")), 1)
        self.assertEqual(self.events.count(("close", "front")), 1)

    def test_real_activation_factory_vetoes_command_and_reasserts_after_blocking_read(self):
        # Capture the actual lexical transport factory before controller.start.
        # No reset, teacher exchange or takeoff occurs during this composition.
        class Captured(Exception):
            pass
        factories = []
        class Controller:
            def __init__(self, **kwargs):
                factories.append(kwargs["host_bound_transport_factory"])
            def start(self, **kwargs):
                raise Captured()

        f = takeoff_test.Fixture("pre-range")
        f.authorizer.close_run(f.authorization, "replace deterministic test binding")
        f.binding = teacher.PhysicalRunBinding("reactive-obstacle-v2", BINDING, f.epoch())
        f.authorization = f.authorizer.authorize_run(f.binding, lambda _: True)
        self.cf = f.cf
        self.epoch = f.epoch()
        session = SimpleNamespace(_scf=SimpleNamespace(cf=f.cf, is_link_open=lambda: True),
                                  read_connection_epoch=f.epoch)
        bridge = SimpleNamespace(begin_post_reset_replacement=lambda _: None,
                                 install_post_reset_session=lambda _: None)
        program_changed = [False]
        def assert_program(*args, **kwargs):
            if program_changed[0]:
                raise PhysicalRunActivationError("program changed during range setup")
        host_socket, peer_socket = socket.socketpair()
        self.addCleanup(host_socket.close)
        self.addCleanup(peer_socket.close)
        with patch.object(activation, "ProductionTakeoffRunController", Controller), \
             patch.object(activation, "_assert_current_program", assert_program):
            with self.assertRaises(Captured):
                activation.activate_validated_dynamic_run(uri=f.cf.link_uri, session=session,
                    bridge=bridge, teacher_socket=host_socket, staged_binding=f.binding,
                    execution_domain=f.execution)
            transport = factories[0](crazyflie=f.cf, execution_domain=f.execution,
                acknowledgement_domain=f.ack, safelink_guard=f.safelink,
                teacher_authorization=f.authorization, powered_session=f.powered,
                watchdog_guard=f.watchdog, supervisor_reader=f.supervisor)
            for failure in ("unavailable", "cleanup", "program", "supervisor"):
                with self.subTest(failure=failure), redirect_stderr(StringIO()):
                    self.filter_values = ["1", "1"]
                    self.raw = 32766 if failure == "unavailable" else 1000
                    self.close_error = RuntimeError("close failed") if failure == "cleanup" else None
                    program_changed[0] = False
                    self.on_read = (lambda: program_changed.__setitem__(0, True)) if failure == "program" else lambda: None
                    f.queue_states(f.state(can_fly=failure != "supervisor"))
                    with self.assertRaises(Exception):
                        transport.send_from_authorized_ast()
                    self.assertFalse(f.cf.send_calls, "veto must precede command-9 emission")
                    self.assertEqual(f.execution.phase, "inactive")
            self.filter_values = ["1", "1"]
            self.raw = 1000
            self.close_error = None
            self.on_read = lambda: None
            program_changed[0] = False
            # At each blocking range operation the real effect exclusion holds.
            self.on_close = lambda: self.assertEqual(
                takeoff_test.execution._PROCESS_STATE.active_section, "effect")
            f.queue_states(f.state(), f.state(flying=True, hl_active=True, finished=True))
            with redirect_stderr(StringIO()):
                result = transport.send_from_authorized_ast()
            self.assertTrue(result.accepted)
            self.assertEqual(len(f.cf.send_calls), 1)
            self.assertEqual(f.cf.send_calls[0][0], 9)


if __name__ == "__main__":
    unittest.main()
