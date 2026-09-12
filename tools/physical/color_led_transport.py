#!/usr/bin/env python3
"""Trusted one-shot bottom Color LED effect for the physical Crazyflie.

This module is a deliberately narrow physical-effect surface for issue #340.
It accepts only the existing backend-neutral ``set_light(color)`` palette and
writes only the exact bottom Color LED parameter ``colorLedBot.wrgb8888``.
There is no generic parameter-write API and no browser/caller-selected parameter
name, id or packed value.

The normal cflib ``Param.set_value()`` path is intentionally not used here: it
queues writes through the generic parameter updater and may ask ``send_packet``
to resend while waiting for an expected reply.  The trusted path instead emits
one direct PARAM write after live SafeLink, teacher, powered-session, watchdog,
current-program and process-wide effect-exclusion checks.  A protocol-v2 valid
write echoes the exact two-byte parameter id plus value; that exact reply is
serialized per connection epoch and any post-send uncertainty poisons the epoch.
A positive write acknowledgement is completed only by a fresh direct PARAM read
of the same exact id/value on the same live run.

The class owns no current-program source.  As with the SETPOINT_HL transport,
the base ``_read_current_binding`` hook fails closed and production must supply a
host-local lexical subclass that closes over the one trusted physical bridge.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import struct
from threading import Event, Lock, RLock
from time import monotonic
from typing import Callable

import physical_execution_domain
import powered_session_authority
import safelink_precondition
import teacher_run_authorization
import watchdog_liveness

_PARAM_PORT = 0x02
_PARAM_READ_CHANNEL = 1
_PARAM_WRITE_CHANNEL = 2
_PARAM_NAME = "colorLedBot.wrgb8888"
_PARAM_CTYPE = "uint32_t"
_PARAM_PYTYPE = "<L"
_WRITE_REQUEST_SIZE = 6
_READ_REQUEST_SIZE = 2
_READ_REPLY_SIZE = 7
_DEFAULT_REPLY_TIMEOUT_SECONDS = 0.2
_WAIT_SLICE_SECONDS = 0.01

_COLOR_TO_WRGB = {
    "off": 0x00000000,
    "red": 0x00FF0000,
    "green": 0x0000FF00,
    "blue": 0x000000FF,
    "yellow": 0x00FFFF00,
    "white": 0xFF000000,
}

_ACK_STATE_LOCK = Lock()
_ACK_POISONED_EPOCHS: dict[str, str] = {}
_ACK_LOCKS: dict[str, Lock] = {}


class ColorLedTransportError(RuntimeError):
    """Fail-closed trusted bottom Color LED transport error."""


def _require_callable(value: object, name: str) -> Callable:
    if not callable(value):
        raise ColorLedTransportError(f"{name} must be callable")
    return value


def _positive_timeout(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ColorLedTransportError(f"{name} must be positive")
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        raise ColorLedTransportError(f"{name} must be positive")
    return number


def _read_epoch(reader: Callable[[], str]) -> str:
    try:
        value = reader()
    except Exception as exc:
        raise ColorLedTransportError(
            "connection epoch is unavailable for Color LED effect"
        ) from exc
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ColorLedTransportError(
            "connection epoch is invalid for Color LED effect"
        )
    return value


def color_to_wrgb8888(color: object) -> int:
    """Map the exact Runtime v2 palette to the official bottom-deck WRGB value."""
    if not isinstance(color, str) or color not in _COLOR_TO_WRGB:
        raise ColorLedTransportError("unsupported physical Color LED color")
    return _COLOR_TO_WRGB[color]


def _poison_ack_epoch(epoch: str, reason: object) -> None:
    message = str(reason).strip() or "ambiguous Color LED parameter acknowledgement"
    with _ACK_STATE_LOCK:
        _ACK_POISONED_EPOCHS.setdefault(epoch, message)


def _ack_poison_reason(epoch: str) -> str | None:
    with _ACK_STATE_LOCK:
        return _ACK_POISONED_EPOCHS.get(epoch)


def _ack_lock(epoch: str) -> Lock:
    with _ACK_STATE_LOCK:
        lock = _ACK_LOCKS.get(epoch)
        if lock is None:
            lock = Lock()
            _ACK_LOCKS[epoch] = lock
        return lock


class _ColorParamAckDomain:
    """Pure exact-reply freshness/serialization for one connection epoch."""

    def __init__(self, connection_epoch_reader: Callable[[], str]) -> None:
        self._reader = _require_callable(
            connection_epoch_reader, "Color LED connection epoch reader"
        )
        self._epoch = _read_epoch(self._reader)
        self._lock = _ack_lock(self._epoch)
        self._raise_if_poisoned()

    @property
    def bound_connection_epoch(self) -> str:
        return self._epoch

    def _raise_if_poisoned(self) -> None:
        reason = _ack_poison_reason(self._epoch)
        if reason is not None:
            raise ColorLedTransportError(
                "Color LED acknowledgement freshness is poisoned for this connection epoch: "
                + reason
            )

    def verify_epoch(self, *, poison_on_change: bool) -> None:
        self._raise_if_poisoned()
        current = _read_epoch(self._reader)
        if current != self._epoch:
            reason = "connection epoch changed during Color LED acknowledgement"
            if poison_on_change:
                _poison_ack_epoch(self._epoch, reason)
            raise ColorLedTransportError(reason)

    def transaction(self, request: bytes) -> "_ColorParamAckTransaction":
        self.verify_epoch(poison_on_change=False)
        if not isinstance(request, bytes) or len(request) != _WRITE_REQUEST_SIZE:
            raise ColorLedTransportError("exact Color LED PARAM write request is required")
        if not self._lock.acquire(blocking=False):
            raise ColorLedTransportError(
                "another Color LED acknowledgement transaction is already active"
            )
        try:
            self.verify_epoch(poison_on_change=False)
            return _ColorParamAckTransaction(self, request, self._lock)
        except Exception:
            self._lock.release()
            raise


class _ColorParamAckTransaction:
    _PREPARED = "prepared"
    _EMITTED = "emitted"
    _RESOLVED = "resolved"
    _AMBIGUOUS = "ambiguous"
    _CLOSED = "closed"

    def __init__(
        self,
        domain: _ColorParamAckDomain,
        request: bytes,
        lock: Lock,
    ) -> None:
        self._domain = domain
        self._request = request
        self._param_id = request[:2]
        self._lock = lock
        self._state = self._PREPARED
        self._released = False

    @property
    def emitted(self) -> bool:
        return self._state in (self._EMITTED, self._RESOLVED, self._AMBIGUOUS)

    @property
    def param_id_prefix(self) -> bytes:
        return self._param_id

    def __enter__(self) -> "_ColorParamAckTransaction":
        return self

    def mark_emitted(self) -> None:
        if self._state != self._PREPARED:
            raise ColorLedTransportError(
                "Color LED acknowledgement transaction is not prepared for emission"
            )
        try:
            self._domain.verify_epoch(poison_on_change=True)
        except Exception:
            self._state = self._AMBIGUOUS
            raise
        self._state = self._EMITTED

    def resolve_reply(self, reply: object) -> None:
        if self._state != self._EMITTED:
            raise ColorLedTransportError(
                "Color LED acknowledgement requires an emitted request"
            )
        try:
            self._domain.verify_epoch(poison_on_change=True)
            if isinstance(reply, bytearray):
                data = bytes(reply)
            elif isinstance(reply, bytes):
                data = reply
            else:
                raise ColorLedTransportError(
                    "Color LED PARAM acknowledgement must be bytes"
                )
            if data != self._request:
                raise ColorLedTransportError(
                    "Color LED PARAM acknowledgement does not exactly echo the request"
                )
        except Exception as exc:
            _poison_ack_epoch(self._domain.bound_connection_epoch, exc)
            self._state = self._AMBIGUOUS
            raise
        self._state = self._RESOLVED

    def _release(self) -> None:
        if not self._released:
            self._released = True
            self._lock.release()

    def close(self) -> None:
        if self._state == self._EMITTED:
            _poison_ack_epoch(
                self._domain.bound_connection_epoch,
                "emitted Color LED PARAM request closed without definitive acknowledgement",
            )
            self._state = self._AMBIGUOUS
        elif self._state in (self._PREPARED, self._RESOLVED, self._AMBIGUOUS):
            self._state = self._CLOSED
        self._release()

    def __exit__(self, exc_type, exc, traceback) -> bool:
        self.close()
        return False


@dataclass(frozen=True, slots=True)
class ColorLedEffectResult:
    accepted: bool
    status: int
    color: str
    wrgb8888: int


def _param_write_request(param_id: int, wrgb8888: int) -> bytes:
    if isinstance(param_id, bool) or not isinstance(param_id, int) or not 0 <= param_id <= 0xFFFF:
        raise ColorLedTransportError("Color LED parameter id is invalid")
    if (
        isinstance(wrgb8888, bool)
        or not isinstance(wrgb8888, int)
        or not 0 <= wrgb8888 <= 0xFFFFFFFF
    ):
        raise ColorLedTransportError("Color LED WRGB value is invalid")
    return struct.pack("<HL", param_id, wrgb8888)


def _param_read_request(param_id: int) -> bytes:
    if isinstance(param_id, bool) or not isinstance(param_id, int) or not 0 <= param_id <= 0xFFFF:
        raise ColorLedTransportError("Color LED parameter id is invalid")
    return struct.pack("<H", param_id)


def _default_packet_factory(channel: int, data: bytes) -> object:
    try:
        from cflib.crtp.crtpstack import CRTPPacket, CRTPPort
    except Exception as exc:
        raise ColorLedTransportError("pinned cflib CRTP packet types are unavailable") from exc
    if getattr(CRTPPort, "PARAM", None) != _PARAM_PORT:
        raise ColorLedTransportError("cflib PARAM port does not match pinned contract")
    packet = CRTPPacket()
    packet.set_header(CRTPPort.PARAM, channel)
    packet.data = data
    return packet


class TrustedBottomColorLedTransport:
    """Exact teacher-bound bottom Color LED effect with one-shot PARAM write."""

    def __init__(
        self,
        *,
        crazyflie: object,
        execution_domain: physical_execution_domain.PhysicalExecutionDomain,
        safelink_guard: safelink_precondition.LiveSafeLinkPrecondition,
        teacher_authorization: teacher_run_authorization.TeacherRunAuthorization,
        powered_session: powered_session_authority.EstablishedPoweredSession,
        watchdog_guard: watchdog_liveness.EmergencyWatchdogLivenessGuard,
        connection_epoch_reader: Callable[[], str],
        packet_factory: Callable[[int, bytes], object] = _default_packet_factory,
        reply_timeout_seconds: float = _DEFAULT_REPLY_TIMEOUT_SECONDS,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if crazyflie is None:
            raise ColorLedTransportError("exact live Crazyflie object is required")
        if type(execution_domain) is not physical_execution_domain.PhysicalExecutionDomain:
            raise ColorLedTransportError("exact process-wide PhysicalExecutionDomain is required")
        if type(safelink_guard) is not safelink_precondition.LiveSafeLinkPrecondition:
            raise ColorLedTransportError("exact LiveSafeLinkPrecondition is required")
        if type(teacher_authorization) is not teacher_run_authorization.TeacherRunAuthorization:
            raise ColorLedTransportError("exact TeacherRunAuthorization receipt is required")
        if type(powered_session) is not powered_session_authority.EstablishedPoweredSession:
            raise ColorLedTransportError("exact EstablishedPoweredSession is required")
        if (
            type(powered_session.watchdog_authority)
            is not powered_session_authority.EphemeralPoweredSessionWatchdogAuthority
        ):
            raise ColorLedTransportError("powered session lacks watchdog authority")
        if type(watchdog_guard) is not watchdog_liveness.EmergencyWatchdogLivenessGuard:
            raise ColorLedTransportError("exact active watchdog guard is required")

        self._cf = crazyflie
        self._execution = execution_domain
        self._safelink = safelink_guard
        self._teacher = teacher_authorization
        self._powered_session = powered_session
        self._watchdog = watchdog_guard
        self._epoch_reader = _require_callable(
            connection_epoch_reader, "Color LED connection epoch reader"
        )
        self._packet_factory = _require_callable(packet_factory, "Color LED packet factory")
        self._timeout = _positive_timeout(reply_timeout_seconds, "Color LED reply timeout")
        self._clock = _require_callable(clock, "Color LED monotonic clock")
        self._send_packet = _require_callable(
            getattr(crazyflie, "send_packet", None), "Crazyflie send_packet"
        )
        self._add_header_callback = _require_callable(
            getattr(crazyflie, "add_header_callback", None),
            "Crazyflie add_header_callback",
        )
        self._remove_header_callback = _require_callable(
            getattr(crazyflie, "remove_header_callback", None),
            "Crazyflie remove_header_callback",
        )

        epoch = _read_epoch(self._epoch_reader)
        if safelink_guard.bound_crazyflie is not crazyflie:
            raise ColorLedTransportError("SafeLink precondition is not bound to exact Crazyflie")
        if safelink_guard.bound_connection_epoch != epoch:
            raise ColorLedTransportError("SafeLink belongs to a different connection epoch")
        if teacher_authorization.binding.connection_epoch != epoch:
            raise ColorLedTransportError("teacher run belongs to a different connection epoch")
        if powered_session.connection_epoch != epoch:
            raise ColorLedTransportError("powered session belongs to a different connection epoch")
        if powered_session.session is not crazyflie:
            raise ColorLedTransportError("powered session is not bound to exact Crazyflie")
        if watchdog_guard.bound_connection_epoch != epoch:
            raise ColorLedTransportError("watchdog belongs to a different connection epoch")
        if watchdog_guard.bound_crazyflie is not crazyflie:
            raise ColorLedTransportError("watchdog is not bound to exact Crazyflie")
        if watchdog_guard.powered_session_identity != powered_session.watchdog_authority.identity:
            raise ColorLedTransportError("watchdog/powered-session identity changed")

        self._bound_connection_epoch = epoch
        self._ack = _ColorParamAckDomain(self._epoch_reader)
        if self._ack.bound_connection_epoch != epoch:
            raise ColorLedTransportError("Color LED acknowledgement domain epoch mismatch")

    @property
    def bound_connection_epoch(self) -> str:
        return self._bound_connection_epoch

    @property
    def teacher_binding(self) -> teacher_run_authorization.PhysicalRunBinding:
        return self._teacher.binding

    @property
    def execution_domain(self) -> physical_execution_domain.PhysicalExecutionDomain:
        return self._execution

    def _read_current_binding(self) -> teacher_run_authorization.PhysicalRunBinding:
        raise ColorLedTransportError(
            "current-program assertion is not bound to the trusted physical host"
        )

    def _require_connection_live(self) -> None:
        method = getattr(self._cf, "is_connected", None)
        if not callable(method):
            raise ColorLedTransportError("Crazyflie live connection state is unavailable")
        try:
            connected = method()
        except Exception as exc:
            raise ColorLedTransportError("Crazyflie live connection state became unavailable") from exc
        if connected is not True:
            raise ColorLedTransportError("Crazyflie disconnected during Color LED effect")
        if _read_epoch(self._epoch_reader) != self._bound_connection_epoch:
            raise ColorLedTransportError("connection epoch changed during Color LED effect")

    def _assert_run_binding(self, *, require_flying: bool) -> None:
        binding = self._read_current_binding()
        if type(binding) is not teacher_run_authorization.PhysicalRunBinding:
            raise ColorLedTransportError("exact current PhysicalRunBinding is required")
        self._teacher.assert_effect_binding(
            profile_id=binding.profile_id,
            ast_binding=binding.ast_binding,
            connection_epoch=binding.connection_epoch,
        )
        if binding.connection_epoch != self._bound_connection_epoch:
            raise ColorLedTransportError("current run binding belongs to a different epoch")
        if self._powered_session.connection_epoch != self._bound_connection_epoch:
            raise ColorLedTransportError("powered session connection epoch changed")
        if self._watchdog.powered_session_identity != self._powered_session.watchdog_authority.identity:
            raise ColorLedTransportError("watchdog/powered-session identity changed")
        self._watchdog.assert_live()
        self._require_connection_live()
        if require_flying:
            if self._execution.phase != physical_execution_domain.FLYING:
                raise ColorLedTransportError("Color LED effect requires established flying state")
        elif self._execution.phase != physical_execution_domain.AWAITING_COMPLETION:
            raise ColorLedTransportError("Color LED readback requires accepted pending effect")

    def _assert_current_authority(self) -> None:
        self._assert_run_binding(require_flying=True)

    def _assert_completion_authority(self) -> None:
        self._assert_run_binding(require_flying=False)

    def _resolve_parameter_id(self) -> int:
        platform = getattr(self._cf, "platform", None)
        getter = getattr(platform, "get_protocol_version", None)
        if not callable(getter):
            raise ColorLedTransportError("Crazyflie protocol version is unavailable")
        try:
            protocol = getter()
        except Exception as exc:
            raise ColorLedTransportError("Crazyflie protocol version read failed") from exc
        if isinstance(protocol, bool) or not isinstance(protocol, int) or protocol < 4:
            raise ColorLedTransportError("Color LED effect requires CRTP parameter protocol v2")

        param = getattr(self._cf, "param", None)
        toc = getattr(param, "toc", None)
        lookup = getattr(toc, "get_element_by_complete_name", None)
        if not callable(lookup):
            raise ColorLedTransportError("live parameter TOC is unavailable")
        try:
            element = lookup(_PARAM_NAME)
        except Exception as exc:
            raise ColorLedTransportError("bottom Color LED parameter lookup failed") from exc
        if element is None:
            raise ColorLedTransportError("bottom Color LED parameter is absent from live TOC")
        if getattr(element, "group", None) != "colorLedBot" or getattr(element, "name", None) != "wrgb8888":
            raise ColorLedTransportError("bottom Color LED TOC entry identity is malformed")
        if getattr(element, "ctype", None) != _PARAM_CTYPE or getattr(element, "pytype", None) != _PARAM_PYTYPE:
            raise ColorLedTransportError("bottom Color LED parameter is not exact uint32_t")
        readable = getattr(element, "get_readable_access", None)
        if not callable(readable) or readable() != "RW":
            raise ColorLedTransportError("bottom Color LED parameter is not writable")
        ident = getattr(element, "ident", None)
        if isinstance(ident, bool) or not isinstance(ident, int) or not 0 <= ident <= 0xFFFF:
            raise ColorLedTransportError("bottom Color LED parameter id is invalid")
        return ident

    def _assert_exact_parameter(self, param_id: int) -> None:
        if self._resolve_parameter_id() != param_id:
            raise ColorLedTransportError("bottom Color LED parameter identity changed")

    def _make_packet(self, channel: int, data: bytes) -> object:
        packet = self._packet_factory(channel, data)
        if getattr(packet, "port", None) != _PARAM_PORT:
            raise ColorLedTransportError("packet factory substituted non-PARAM port")
        if getattr(packet, "channel", None) != channel:
            raise ColorLedTransportError("packet factory substituted PARAM channel")
        try:
            actual = bytes(getattr(packet, "data"))
        except Exception as exc:
            raise ColorLedTransportError("packet factory returned unreadable PARAM data") from exc
        if actual != data:
            raise ColorLedTransportError("packet factory substituted PARAM request bytes")
        return packet

    def _wait_for_packet(
        self,
        event: Event,
        reply_reader: Callable[[], bytes | None],
        *,
        context: str,
    ) -> bytes:
        deadline = float(self._clock()) + self._timeout
        while True:
            if event.is_set():
                data = reply_reader()
                if data is None:
                    raise ColorLedTransportError(context + " event has no packet data")
                return data
            self._watchdog.assert_live()
            self._require_connection_live()
            remaining = deadline - float(self._clock())
            if remaining <= 0.0:
                raise ColorLedTransportError(context + " timeout")
            event.wait(min(_WAIT_SLICE_SECONDS, remaining))

    def _listen_for_param(
        self,
        channel: int,
        param_id_prefix: bytes,
        event: Event,
        reply_box: list[bytes | None],
        freshness_lock: RLock,
        armed: Event,
    ) -> Callable[[object], None]:
        def callback(packet: object) -> None:
            # The listener must exist before send so an immediate cflib callback
            # cannot be missed, but no packet observed before the current send
            # enters its transaction-local emission critical section is fresh.
            with freshness_lock:
                if not armed.is_set():
                    return
                try:
                    data = bytes(getattr(packet, "data"))
                except Exception:
                    return
                if data[:2] != param_id_prefix:
                    return
                if reply_box[0] is None:
                    reply_box[0] = data
                    event.set()

        self._add_header_callback(callback, _PARAM_PORT, channel)
        return callback

    def _remove_listener(self, callback: Callable[[object], None], channel: int) -> None:
        try:
            self._remove_header_callback(callback, _PARAM_PORT, channel)
        except Exception as exc:
            raise ColorLedTransportError("could not remove Color LED PARAM callback") from exc

    def _prove_readback(self, param_id: int, expected_wrgb: int) -> bool:
        self._assert_completion_authority()
        self._assert_exact_parameter(param_id)
        request = _param_read_request(param_id)
        packet = self._make_packet(_PARAM_READ_CHANNEL, request)
        event = Event()
        armed = Event()
        freshness_lock = RLock()
        reply_box: list[bytes | None] = [None]
        callback = self._listen_for_param(
            _PARAM_READ_CHANNEL,
            request,
            event,
            reply_box,
            freshness_lock,
            armed,
        )
        primary_error: Exception | None = None
        try:
            # Hold the same re-entrant lock used by the callback while arming and
            # invoking send_packet. A synchronous callback on this thread remains
            # possible, while a stale callback from another thread cannot cross
            # the freshness boundary before the current send has been invoked.
            with freshness_lock:
                armed.set()
                self._send_packet(packet)
            reply = self._wait_for_packet(
                event,
                lambda: reply_box[0],
                context="Color LED PARAM readback",
            )
            if len(reply) != _READ_REPLY_SIZE or reply[:2] != request:
                raise ColorLedTransportError("Color LED PARAM readback reply is malformed")
            if reply[2] != 0:
                raise ColorLedTransportError("Color LED PARAM readback returned an error")
            actual = struct.unpack("<L", reply[3:7])[0]
            if actual != expected_wrgb:
                raise ColorLedTransportError("Color LED PARAM readback value does not match effect")
            self._assert_completion_authority()
            self._assert_exact_parameter(param_id)
            return True
        except Exception as exc:
            primary_error = exc
            raise
        finally:
            try:
                self._remove_listener(callback, _PARAM_READ_CHANNEL)
            except Exception:
                if primary_error is None:
                    raise

    def send_color(self, *, color: object) -> ColorLedEffectResult:
        normalized = color if isinstance(color, str) else None
        wrgb = color_to_wrgb8888(normalized)
        param_id = self._resolve_parameter_id()
        request = _param_write_request(param_id, wrgb)
        packet = self._make_packet(_PARAM_WRITE_CHANNEL, request)
        event = Event()
        armed = Event()
        freshness_lock = RLock()
        reply_box: list[bytes | None] = [None]
        permit = None

        with self._ack.transaction(request) as acknowledgement:
            callback = self._listen_for_param(
                _PARAM_WRITE_CHANNEL,
                acknowledgement.param_id_prefix,
                event,
                reply_box,
                freshness_lock,
                armed,
            )
            listener_active = True
            primary_error: Exception | None = None
            try:
                with self._execution.effect_transaction(
                    self._assert_current_authority,
                    self._safelink.assert_ready,
                    lambda: self._assert_exact_parameter(param_id),
                ) as effect:
                    effect.mark_emitted()
                    acknowledgement.mark_emitted()
                    with freshness_lock:
                        armed.set()
                        self._send_packet(packet)
                    reply = self._wait_for_packet(
                        event,
                        lambda: reply_box[0],
                        context="Color LED PARAM acknowledgement",
                    )
                    acknowledgement.resolve_reply(reply)

                    # Listener cleanup is still fallible. It must complete before
                    # mark_accepted() mints the only completion permit; otherwise
                    # an exception could strand the process in AWAITING_COMPLETION
                    # with no caller able to recover that permit.
                    self._remove_listener(callback, _PARAM_WRITE_CHANNEL)
                    listener_active = False
                    permit = effect.mark_accepted()
            except Exception as exc:
                primary_error = exc
                raise
            finally:
                if listener_active:
                    try:
                        self._remove_listener(callback, _PARAM_WRITE_CHANNEL)
                    except Exception:
                        if primary_error is None:
                            raise

        if permit is None:
            raise ColorLedTransportError("Color LED accepted-effect permit is unavailable")
        self._execution.complete_accepted_effect(
            permit,
            physical_execution_domain.FLYING,
            lambda: self._prove_readback(param_id, wrgb),
        )
        return ColorLedEffectResult(
            accepted=True,
            status=0,
            color=normalized,
            wrgb8888=wrgb,
        )
