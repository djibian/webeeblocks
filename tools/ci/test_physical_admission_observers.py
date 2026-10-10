#!/usr/bin/env python3
"""Independent adversarial schedules through real admission/command-9 code.

Only the external CRTP/LogConfig surface is modeled. No returned observation,
PARAM adapter, readiness decision or production transport is replaced.
"""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import socket
import struct
import sys
from threading import Lock
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools/physical"), str(ROOT / "tools/ci")]
import admission_observers as observers
import dynamic_run_activation as activation
import pre_takeoff_range_readiness as readiness
import range_observer
import teacher_run_authorization as teacher
import test_physical_takeoff_transport as takeoff
from test_physical_range_observer import FakeConfig, FakeToc

BINDING = (ROOT / "tools/ci/fixtures/physical_fail_554_ast.json").read_text().strip()


class Packet:
    def __init__(self, port, channel, data):
        self.port, self.channel, self.data = port, channel, data


class NativeAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.f = takeoff.Fixture("native-admission-" + self._testMethodName)
        f = self.f
        f.authorizer.close_run(f.authorization, "replace exact test AST")
        f.binding = teacher.PhysicalRunBinding("reactive-obstacle-v2", BINDING, f.epoch())
        f.authorization = f.authorizer.authorize_run(f.binding, lambda _: True)
        cf = f.cf
        self.headers, self.events, self.fences = {}, [], []
        self.mask = 1
        self.read_values = []
        self.fence_mode = self.read_mode = self.delete_mode = "valid"
        self.burst = [(200, 1000)]
        self.next_log_id = 1
        self.program_changed = False
        element = SimpleNamespace(group="multiranger", name="filterMask", ident=42,
                                  ctype="uint16_t", pytype="<H")
        self.element = element
        self.updater = SimpleNamespace(cf=cf, wait_lock=Lock(), _lock_pattern=None, _should_close=False)
        self.toc = SimpleNamespace(
            get_element_by_complete_name=lambda name: element if name == "multiranger.filterMask" else None,
            get_element_by_id=lambda ident: element if ident == element.ident else None,
        )
        def forbidden(*args, **kwargs):
            raise AssertionError("generic/cached PARAM adapter was used")
        cf.param = SimpleNamespace(toc=self.toc, param_updater=self.updater,
                                  get_value=forbidden, request_param_update=forbidden,
                                  add_update_callback=forbidden, set_value=forbidden)
        cf.log = SimpleNamespace(toc=FakeToc("range.front"), log_blocks=[])
        def add_config(config):
            config.cf, config.id = cf, self.next_log_id
            self.next_log_id += 1
            cf.log.log_blocks.append(config)
        cf.log.add_config = add_config
        cf.add_header_callback = lambda cb, port, channel: self.headers.setdefault((port, channel), []).append(cb)
        cf.remove_header_callback = lambda cb, port, channel: self.headers[(port, channel)].remove(cb)
        original_send = cf.send_packet
        def send(packet, **kwargs):
            if packet.port == 2:
                self.events.append(("param", bytes(packet.data)))
                ident = struct.unpack("<H", bytes(packet.data))[0]
                self.assertTrue(self.updater.wait_lock.locked(), "queued cflib reads/writes must be excluded")
                if ident != element.ident:
                    self.fences.append(ident)
                    # Old target reply arrives behind local enqueue, before
                    # the unique fence reply. It must never satisfy READ.
                    self.emit(2, 1, struct.pack("<HBH", element.ident, 0, 1))
                    if self.fence_mode != "missing":
                        status = 2 if self.fence_mode == "valid" else 0
                        self.emit(2, 1, struct.pack("<HB", ident, status))
                else:
                    self.emit(2, 3, struct.pack("<HBH", ident, 0, 1))  # generic update is irrelevant
                    if self.read_mode != "missing":
                        mask = self.read_values.pop(0) if self.read_values else self.mask
                        data = struct.pack("<HBH", ident, 0, mask)
                        self.emit(2, 1, data + (b"extra" if self.read_mode == "malformed" else b""))
            elif packet.port == 5:
                self.events.append(("log", bytes(packet.data)))
                command, ident = bytes(packet.data)
                if command == 2 and self.delete_mode != "missing":
                    self.assertTrue(self.headers[(5, 1)], "delete listener removed before firmware proof")
                    status = {"valid": 0, "absent": 2, "rejected": 5}.get(self.delete_mode, 0)
                    data = bytes((2, ident, status))
                    if self.delete_mode == "wrong_id":
                        data = bytes((2, ident + 1, 0))
                    if self.delete_mode == "malformed":
                        data += b"extra"
                    if self.delete_mode == "epoch":
                        f.epoch_value += "-reconnected"
                    self.emit(5, 1, data)
            else:
                original_send(packet)
        cf.send_packet = send

        def config_factory(observer):
            config = FakeConfig(observer.variable, (100, 1000))
            def stop():
                config.stopped = True
                cf.send_packet(Packet(5, 1, bytes((4, config.id))))
            def delete():
                config.deleted = True
                cf.send_packet(Packet(5, 1, bytes((2, config.id))))
            config.stop, config.delete = stop, delete
            return config
        original_wait = range_observer.FreshRangeObserver._wait_for_sample
        def scheduled_wait(observer, **kwargs):
            if kwargs["request_generation"] != 0:
                for timestamp, raw in self.burst:
                    observer._config.emit(timestamp, raw)
            return original_wait(observer, **kwargs)
        patches = (
            patch.object(observers, "_default_packet_factory", lambda ch, data: Packet(2, ch, data)),
            patch.object(range_observer.FreshRangeObserver, "_make_config", config_factory),
            patch.object(range_observer.FreshRangeObserver, "_wait_for_sample", scheduled_wait),
        )
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def emit(self, port, channel, data):
        for cb in tuple(self.headers.get((port, channel), ())):
            cb(Packet(port, channel, data))

    def observer(self):
        return observers.AdmissionRangeObserver(self.f.cf, self.f.epoch, "front", close_timeout_seconds=0.01)

    def reader(self):
        return observers.FreshDefaultRangeFilterReader(self.f.cf, self.f.epoch, timeout_seconds=0.01)

    def test_burst_first_unavailable_is_preserved(self):
        for raw in (8000, 32766, 32767, 65535):
            with self.subTest(raw=raw):
                self.burst = [(200, raw), (300, 1000)]
                observer = self.observer()
                observer.open()
                with self.assertRaisesRegex(Exception, "unavailable"):
                    observer.read()
                observer.close()

    def test_first_finite_is_not_replaced_by_later_value_or_stale_timestamp(self):
        self.burst = [(100, 32766), (200, 1000), (300, 2000)]
        observer = self.observer()
        observer.open()
        self.assertEqual(observer.read().raw_mm, 1000)
        observer.close()

    def test_causal_param_ignores_old_target_and_generic_update(self):
        self.reader().read_default()
        self.reader().read_default()
        self.assertEqual(len(set(self.fences)), 2, "fence ids must never be reused")
        self.assertFalse(self.updater.wait_lock.locked())
        self.mask = 3
        with self.assertRaisesRegex(Exception, "RANGE_VALID"):
            self.reader().read_default()
        self.mask = 1
        with self.assertRaisesRegex(Exception, "poisoned"):
            self.reader().read_default()

    def test_generic_update_cannot_replace_missing_exact_read(self):
        self.read_mode = "missing"
        with self.assertRaisesRegex(Exception, "timeout"):
            self.reader().read_default()

    def test_filter_change_after_observation_vetoes_readiness(self):
        self.read_values = [1, 3]
        with self.assertRaisesRegex(Exception, "RANGE_VALID"):
            readiness.require_pre_takeoff_ranges(self.f.cf, self.f.epoch, BINDING)
        self.assertEqual(len(self.fences), 2)
        self.assertEqual(self.events.count(("log", bytes((2, 1)))), 1)

    def test_missing_or_wrong_fence_and_malformed_read_poison_without_retry(self):
        for fence, read in (("missing", "valid"), ("wrong", "valid"), ("valid", "malformed")):
            with self.subTest(fence=fence, read=read):
                self.f.epoch_value += "-fresh"
                self.fence_mode, self.read_mode = fence, read
                with self.assertRaises(Exception):
                    self.reader().read_default()
                count = len(self.events)
                with self.assertRaisesRegex(Exception, "poisoned"):
                    self.reader().read_default()
                self.assertEqual(len(self.events), count)

    def test_wrong_filter_type_and_busy_updater_fail_without_request(self):
        self.element.ctype = "uint8_t"
        with self.assertRaises(Exception):
            self.reader().read_default()
        self.assertFalse(self.events)

    def test_outstanding_param_request_is_not_bypassed(self):
        self.updater.wait_lock.acquire()
        with self.assertRaisesRegex(Exception, "outstanding"):
            self.reader().read_default()
        self.assertFalse(self.events)
        self.updater.wait_lock.release()

    def test_log_delete_timeout_rejection_wrong_id_and_epoch_poison(self):
        for mode in ("missing", "rejected", "wrong_id", "malformed", "epoch"):
            with self.subTest(mode=mode):
                self.delete_mode = mode
                observer = self.observer()
                observer.open()
                observer.read()
                with self.assertRaises(Exception):
                    observer.close()
                self.assertTrue(observer.poisoned)
                self.assertFalse(observer.is_open)
                with self.assertRaises(Exception):
                    observer.close()  # no blind resend
                ident = self.f.cf.log.log_blocks[-1].id
                self.assertEqual(self.events.count(("log", bytes((2, ident)))), 1)
                self.assertFalse(self.headers[(5, 1)])

    def test_log_id_reuse_fails_before_start_and_never_deletes_another_stream(self):
        self.f.cf.log.log_blocks.append(SimpleNamespace(id=1))
        observer = self.observer()
        with self.assertRaisesRegex(Exception, "reused"):
            observer.open()
        self.assertTrue(observer.poisoned)
        self.assertFalse(self.events)

    def test_enoent_is_positive_deletion_evidence(self):
        self.delete_mode = "absent"
        observer = self.observer()
        observer.open()
        observer.read()
        observer.close()
        self.assertFalse(observer.poisoned)

    def test_real_lexical_command9_factory_vetoes_all_three_refutations(self):
        class Captured(Exception):
            pass
        factories = []
        class Controller:
            def __init__(self, **kwargs):
                factories.append(kwargs["host_bound_transport_factory"])
            def start(self, **kwargs):
                raise Captured()
        f = self.f
        session = SimpleNamespace(_scf=SimpleNamespace(cf=f.cf, is_link_open=lambda: True),
                                  read_connection_epoch=f.epoch)
        bridge = SimpleNamespace(begin_post_reset_replacement=lambda _: None,
                                 install_post_reset_session=lambda _: None)
        host, peer = socket.socketpair()
        self.addCleanup(host.close)
        self.addCleanup(peer.close)
        with patch.object(activation, "ProductionTakeoffRunController", Controller), \
             patch.object(activation, "_assert_current_program", lambda *args, **kwargs: None):
            with self.assertRaises(Captured):
                activation.activate_validated_dynamic_run(uri=f.cf.link_uri, session=session,
                    bridge=bridge, teacher_socket=host, staged_binding=f.binding, execution_domain=f.execution)
            transport = factories[0](crazyflie=f.cf, execution_domain=f.execution,
                acknowledgement_domain=f.ack, safelink_guard=f.safelink,
                teacher_authorization=f.authorization, powered_session=f.powered,
                watchdog_guard=f.watchdog, supervisor_reader=f.supervisor)
            self.burst = [(200, 32766), (300, 1000)]
            with redirect_stderr(StringIO()), self.assertRaises(Exception):
                transport.send_from_authorized_ast()
            self.assertFalse(f.cf.send_calls)
            self.burst = [(200, 1000)]
            self.delete_mode = "rejected"
            with redirect_stderr(StringIO()), self.assertRaises(Exception):
                transport.send_from_authorized_ast()
            self.assertFalse(f.cf.send_calls)
            self.delete_mode = "valid"
            self.mask = 3
            with redirect_stderr(StringIO()), self.assertRaises(Exception):
                transport.send_from_authorized_ast()
            self.assertFalse(f.cf.send_calls)
            self.assertEqual(f.execution.phase, "inactive")

    def test_real_lexical_command9_factory_accepts_exact_native_observations(self):
        # Reuse the factory composition above with independent fresh fixture
        # state, replacing only the external schedules with valid responses.
        class Captured(Exception):
            pass
        factories = []
        class Controller:
            def __init__(self, **kwargs): factories.append(kwargs["host_bound_transport_factory"])
            def start(self, **kwargs): raise Captured()
        f = self.f
        session = SimpleNamespace(_scf=SimpleNamespace(cf=f.cf, is_link_open=lambda: True), read_connection_epoch=f.epoch)
        bridge = SimpleNamespace(begin_post_reset_replacement=lambda _: None, install_post_reset_session=lambda _: None)
        host, peer = socket.socketpair()
        self.addCleanup(host.close)
        self.addCleanup(peer.close)
        with patch.object(activation, "ProductionTakeoffRunController", Controller), \
             patch.object(activation, "_assert_current_program", lambda *args, **kwargs: None):
            with self.assertRaises(Captured):
                activation.activate_validated_dynamic_run(uri=f.cf.link_uri, session=session, bridge=bridge,
                    teacher_socket=host, staged_binding=f.binding, execution_domain=f.execution)
            transport = factories[0](crazyflie=f.cf, execution_domain=f.execution, acknowledgement_domain=f.ack,
                safelink_guard=f.safelink, teacher_authorization=f.authorization, powered_session=f.powered,
                watchdog_guard=f.watchdog, supervisor_reader=f.supervisor)
            f.queue_states(f.state(), f.state(flying=True, hl_active=True, finished=True))
            with redirect_stderr(StringIO()):
                self.assertTrue(transport.send_from_authorized_ast().accepted)
            self.assertEqual([packet[0] for packet in f.cf.send_calls], [9])
            self.assertEqual(len(set(self.fences)), 2)
            self.assertEqual(self.events.count(("log", bytes((2, 1)))), 1)


if __name__ == "__main__":
    unittest.main()
