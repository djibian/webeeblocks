#!/usr/bin/env python3
"""Read-only causal PARAM admission and confirmed LOG teardown.

No X3 preparation/reset or Commander operation is imported. PARAM reads share
the established Color LED receive-fence ids and epoch lock, but expose no write
operation. The pinned cflib updater is excluded while direct reads are fenced;
generic update callbacks are never readback evidence.
"""
from __future__ import annotations

import errno
from math import isfinite
import struct
from threading import Event, Lock
from time import monotonic

from color_led_transport import (
    _ack_lock, _ack_poison_reason, _poison_ack_epoch, _reserve_fence_id,
    _default_packet_factory,
)
from range_observer import FreshRangeObserver, RangeReadError
from safelink_precondition import LiveSafeLinkPrecondition


class AdmissionObservationError(RuntimeError):
    pass


class FreshDefaultRangeFilterReader:
    """One exact uint16 READ, following a never-reused absent-id receive fence."""

    def __init__(self, cf, epoch_reader, *, timeout_seconds=3.0, packet_factory=None):
        if (type(timeout_seconds) not in (int, float)
                or not isfinite(timeout_seconds) or timeout_seconds <= 0):
            raise AdmissionObservationError("invalid PARAM observation timeout")
        self.cf = cf
        self.epoch_reader = epoch_reader
        self.epoch = epoch_reader()
        self.timeout = timeout_seconds
        self.packet_factory = packet_factory or _default_packet_factory
        self.safelink = LiveSafeLinkPrecondition(cf, epoch_reader)

    def _verify(self):
        if self.epoch_reader() != self.epoch:
            raise AdmissionObservationError("PARAM observation epoch changed")
        self.safelink.assert_ready()

    def _element(self):
        element = self.cf.param.toc.get_element_by_complete_name("multiranger.filterMask")
        if (element is None or getattr(element, "group", None) != "multiranger"
                or getattr(element, "name", None) != "filterMask"
                or getattr(element, "ctype", None) != "uint16_t"
                or getattr(element, "pytype", None) != "<H"
                or type(getattr(element, "ident", None)) is not int
                or not 0 <= element.ident <= 65535
                or self.cf.param.toc.get_element_by_id(element.ident) is not element):
            raise AdmissionObservationError("exact uint16 multiranger.filterMask TOC required")
        return element

    def _read(self, ident):
        request = struct.pack("<H", ident)
        packet = self.packet_factory(1, request)
        if (packet.port != 2 or packet.channel != 1 or bytes(packet.data) != request):
            raise AdmissionObservationError("PARAM READ packet mismatch")
        event, lock, replies = Event(), Lock(), []

        def callback(reply):
            try:
                data = bytes(reply.data)
            except Exception:
                return
            if data[:2] == request:
                with lock:
                    if not replies:
                        replies.append(data)
                        event.set()

        installed = False
        try:
            installed = True
            self.cf.add_header_callback(callback, 2, 1)
            self._verify()
            self.cf.send_packet(packet)
            deadline = monotonic() + self.timeout
            while not event.is_set():
                self._verify()
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise AdmissionObservationError("causal PARAM READ timeout")
                event.wait(min(remaining, 0.02))
            self._verify()
            return replies[0]
        finally:
            if installed:
                self.cf.remove_header_callback(callback, 2, 1)

    def read_default(self):
        epoch_lock = _ack_lock(self.epoch)
        if not epoch_lock.acquire(blocking=False):
            raise AdmissionObservationError("PARAM epoch observation is already active")
        updater_lock = None
        try:
            self._verify()
            if _ack_poison_reason(self.epoch) is not None:
                raise AdmissionObservationError("PARAM epoch freshness is poisoned")
            if self.cf.platform.get_protocol_version() != 12:
                raise AdmissionObservationError("pinned PARAM protocol 12 required")
            # request_param_update only queues requests. Holding the pinned
            # updater's wait_lock prevents an older queued read/write from
            # being sent behind our receive fence and impersonating our READ.
            updater = self.cf.param.param_updater
            if (updater is None or getattr(updater, "_should_close", True) is not False
                    or not updater.wait_lock.acquire(blocking=False)):
                raise AdmissionObservationError("PARAM updater is unavailable or has an outstanding request")
            updater_lock = updater.wait_lock
            if getattr(updater, "cf", None) is not self.cf:
                raise AdmissionObservationError("PARAM updater belongs to another Crazyflie")
            if updater._lock_pattern is not None:
                raise AdmissionObservationError("PARAM updater receive state is uncertain")
            element = self._element()
            fence_id = _reserve_fence_id(self.epoch, self.cf.param.toc.get_element_by_id)
            if self._read(fence_id) != struct.pack("<HB", fence_id, errno.ENOENT):
                raise AdmissionObservationError("PARAM receive fence is not exact ENOENT")
            if self._element() is not element:
                raise AdmissionObservationError("PARAM TOC changed during receive fence")
            reply = self._read(element.ident)
            if (len(reply) != 5 or reply[:3] != struct.pack("<HB", element.ident, 0)
                    or struct.unpack("<H", reply[3:])[0] != 1):
                raise AdmissionObservationError("unchanged official RANGE_VALID-only filter required before takeoff")
            if self._element() is not element or self.cf.param.param_updater is not updater:
                raise AdmissionObservationError("PARAM connection/TOC changed during READ")
            self._verify()
        except Exception as exc:
            _poison_ack_epoch(self.epoch, "admission PARAM observation uncertain: " + str(exc))
            raise
        finally:
            if updater_lock is not None:
                updater_lock.release()
            epoch_lock.release()


class AdmissionRangeObserver(FreshRangeObserver):
    """Confirmed LOG observer, reused for admission and in-flight consumption.

    The historical class name is retained; it creates no takeoff authority.
    """

    def __init__(self, *args, close_timeout_seconds=0.7, **kwargs):
        super().__init__(*args, **kwargs)
        if (type(close_timeout_seconds) not in (int, float)
                or not isfinite(close_timeout_seconds) or close_timeout_seconds <= 0):
            raise RangeReadError("invalid LOG close timeout")
        self._close_timeout = close_timeout_seconds
        self._registered_identity = None

    def _validate_registered_config(self, config):
        ident = getattr(config, "id", None)
        blocks = getattr(self._cf.log, "log_blocks", None)
        # Pinned cflib retains deleted configurations in log_blocks. An id
        # collision (including wraparound) makes old replies ambiguous.
        if (type(ident) is not int or not 0 <= ident < 255
                or getattr(config, "cf", None) is not self._cf
                or not isinstance(blocks, list)
                or sum(block is config for block in blocks) != 1
                or sum(getattr(block, "id", None) == ident for block in blocks) != 1):
            raise RangeReadError("admission LOG block identity missing or reused")
        self._registered_identity = ident

    def _cleanup(self, config, *, data_registered, error_registered, disconnect_registered):
        errors = []
        event, replies = Event(), []
        ident = self._registered_identity
        installed = False

        def callback(reply):
            try:
                data = bytes(reply.data)
            except Exception:
                return
            if data[:2] == bytes((2, ident)) and not replies:
                replies.append(data)
                event.set()

        try:
            if (ident is None or config.id != ident or config.cf is not self._cf
                    or self._cf.log.log_blocks.count(config) != 1
                    or sum(getattr(b, "id", None) == ident for b in self._cf.log.log_blocks) != 1):
                # Do not delete an ambiguously reused id, which may belong to
                # an unrelated stream. Caller remains vetoed/poisoned.
                raise RangeReadError("LOG deletion identity is uncertain")
            self._verify_epoch()
            LiveSafeLinkPrecondition(self._cf, self._connection_epoch_reader).assert_ready()
            installed = True
            self._cf.add_header_callback(callback, 5, 1)
            config.stop()
            config.delete()
            deadline = monotonic() + self._close_timeout
            while not event.is_set():
                self._verify_epoch()
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise RangeReadError("admission LOG deletion confirmation timed out")
                event.wait(min(remaining, 0.02))
            self._verify_epoch()
            if replies[0] not in (bytes((2, ident, 0)), bytes((2, ident, errno.ENOENT))):
                raise RangeReadError("admission LOG deletion reply is malformed or rejected")
            if self._stream_error is not None:
                raise self._stream_error
        except Exception as exc:
            errors.append(str(exc))
        finally:
            if installed:
                try:
                    self._cf.remove_header_callback(callback, 5, 1)
                except Exception as exc:
                    errors.append("LOG deletion listener cleanup: " + str(exc))
            # Commands were issued exactly once above. Remove only local
            # callbacks here; the base cleanup would resend stop/delete.
            for registered, bus, callback_function in (
                (data_registered, config.data_received_cb, self._on_data),
                (error_registered, config.error_cb, self._on_log_error),
                (disconnect_registered, self._cf.disconnected, self._on_disconnect),
            ):
                if registered:
                    try:
                        bus.remove_callback(callback_function)
                    except Exception as exc:
                        errors.append("LOG callback cleanup: " + str(exc))
            self._config = None
            self._opened = False
        return errors
