#!/usr/bin/env python3
"""Fresh, fail-closed read-only Crazyflie supervisor-state observation.

cflib Supervisor convenience properties may return a cached bitfield when a
fresh request times out. That behavior is not a sufficient freshness oracle for
WebeeBlocks physical command completion. This module therefore owns a bounded
read-only supervisor transaction, binds it to a reconnect-sensitive connection
epoch and permanently poisons that reader after any ambiguous read failure.

The reader deliberately exposes no arming, watchdog keepalive, setpoint,
high-level commander or other physical-effect operation.
"""

from __future__ import annotations

from threading import Event, Lock
from typing import Callable, NamedTuple

SUPERVISOR_CH_INFO = 0
CMD_GET_STATE_BITFIELD = 0x0C
CMD_GET_STATE_BITFIELD_RESPONSE = CMD_GET_STATE_BITFIELD | 0x80
MIN_SUPERVISOR_PROTOCOL_VERSION = 12

BIT_CAN_BE_ARMED = 0
BIT_IS_ARMED = 1
BIT_IS_AUTO_ARMED = 2
BIT_CAN_FLY = 3
BIT_IS_FLYING = 4
BIT_IS_TUMBLED = 5
BIT_IS_LOCKED = 6
BIT_IS_CRASHED = 7
BIT_HL_CONTROL_ACTIVE = 8
BIT_HL_TRAJ_FINISHED = 9
BIT_HL_CONTROL_DISABLED = 10
BIT_DECK_FAULT = 11
KNOWN_STATE_MASK = (1 << (BIT_DECK_FAULT + 1)) - 1


class SupervisorReadError(RuntimeError):
    """Fail-closed error for unavailable or ambiguous fresh supervisor state."""


class SupervisorState(NamedTuple):
    protocol_version: int
    bitfield: int
    can_be_armed: bool
    is_armed: bool
    is_auto_armed: bool
    can_fly: bool
    is_flying: bool
    is_tumbled: bool
    is_locked: bool
    is_crashed: bool
    hl_control_active: bool
    hl_traj_finished: bool
    hl_control_disabled: bool
    deck_fault: bool
    blocking_fault: bool


def _bit(value: int, position: int) -> bool:
    return bool((value >> position) & 0x01)


def decode_supervisor_state(protocol_version: int, bitfield: int) -> SupervisorState:
    if protocol_version < MIN_SUPERVISOR_PROTOCOL_VERSION:
        raise SupervisorReadError(
            "supervisor state requires CRTP protocol version 12 or later"
        )
    if bitfield < 0:
        raise SupervisorReadError("supervisor bitfield must be non-negative")
    unknown_bits = bitfield & ~KNOWN_STATE_MASK
    if unknown_bits:
        raise SupervisorReadError(
            f"unknown supervisor state bits set: 0x{unknown_bits:x}"
        )

    is_tumbled = _bit(bitfield, BIT_IS_TUMBLED)
    is_locked = _bit(bitfield, BIT_IS_LOCKED)
    is_crashed = _bit(bitfield, BIT_IS_CRASHED)
    hl_control_disabled = _bit(bitfield, BIT_HL_CONTROL_DISABLED)
    deck_fault = _bit(bitfield, BIT_DECK_FAULT)
    return SupervisorState(
        protocol_version=protocol_version,
        bitfield=bitfield,
        can_be_armed=_bit(bitfield, BIT_CAN_BE_ARMED),
        is_armed=_bit(bitfield, BIT_IS_ARMED),
        is_auto_armed=_bit(bitfield, BIT_IS_AUTO_ARMED),
        can_fly=_bit(bitfield, BIT_CAN_FLY),
        is_flying=_bit(bitfield, BIT_IS_FLYING),
        is_tumbled=is_tumbled,
        is_locked=is_locked,
        is_crashed=is_crashed,
        hl_control_active=_bit(bitfield, BIT_HL_CONTROL_ACTIVE),
        hl_traj_finished=_bit(bitfield, BIT_HL_TRAJ_FINISHED),
        hl_control_disabled=hl_control_disabled,
        deck_fault=deck_fault,
        blocking_fault=(
            is_tumbled
            or is_locked
            or is_crashed
            or hl_control_disabled
            or deck_fault
        ),
    )


def _read_protocol_version(cf: object) -> int:
    try:
        value = cf.platform.get_protocol_version()
        protocol_version = int(value)
    except Exception as exc:
        raise SupervisorReadError(
            "Crazyflie protocol version is unavailable for supervisor state"
        ) from exc
    if protocol_version < MIN_SUPERVISOR_PROTOCOL_VERSION:
        raise SupervisorReadError(
            "supervisor state requires CRTP protocol version 12 or later"
        )
    return protocol_version


class FreshSupervisorStateReader:
    """One connection-bound supervisor freshness domain.

    A timeout, disconnect, malformed response, protocol incompatibility or
    connection-epoch change permanently poisons the instance. Since the
    supervisor GET_STATE command has no transaction identifier, the caller must
    reconnect and construct a new reader after poison; retrying on the same
    connection could misclassify a delayed old reply as fresh evidence.
    """

    def __init__(
        self,
        cf: object,
        connection_epoch_reader: Callable[[], str],
        *,
        crtp_types: tuple[object, object] | None = None,
    ) -> None:
        self._cf = cf
        self._connection_epoch_reader = connection_epoch_reader
        self._crtp_types = crtp_types
        self._read_lock = Lock()
        self._state_lock = Lock()
        self._poisoned = False
        self._poison_reason: str | None = None
        self._bound_connection_epoch = self._read_epoch()

    @property
    def bound_connection_epoch(self) -> str:
        return self._bound_connection_epoch

    @property
    def poisoned(self) -> bool:
        with self._state_lock:
            return self._poisoned

    def _read_epoch(self) -> str:
        try:
            epoch = self._connection_epoch_reader()
        except Exception as exc:
            raise SupervisorReadError(
                "connection epoch is unavailable for supervisor state"
            ) from exc
        if not isinstance(epoch, str) or not epoch.strip():
            raise SupervisorReadError("connection epoch is invalid for supervisor state")
        return epoch

    def _poison(self, reason: str) -> None:
        with self._state_lock:
            if not self._poisoned:
                self._poisoned = True
                self._poison_reason = reason

    def _raise_if_poisoned(self) -> None:
        with self._state_lock:
            if self._poisoned:
                raise SupervisorReadError(
                    "supervisor freshness is poisoned until reconnect: "
                    + (self._poison_reason or "ambiguous prior read")
                )

    def _verify_connection_epoch(self) -> None:
        self._raise_if_poisoned()
        current_epoch = self._read_epoch()
        if current_epoch != self._bound_connection_epoch:
            reason = "connection epoch changed during supervisor freshness domain"
            self._poison(reason)
            raise SupervisorReadError(reason)

    def read(self, *, timeout_seconds: float = 0.2) -> SupervisorState:
        if timeout_seconds <= 0:
            raise SupervisorReadError("supervisor read timeout must be positive")

        with self._read_lock:
            self._verify_connection_epoch()
            try:
                state = self._read_once(timeout_seconds)
                self._verify_connection_epoch()
                return state
            except SupervisorReadError as exc:
                self._poison(str(exc))
                raise

    def _resolve_crtp_types(self) -> tuple[object, object]:
        if self._crtp_types is not None:
            return self._crtp_types
        try:
            from cflib.crtp.crtpstack import CRTPPacket, CRTPPort
        except ImportError as exc:
            raise SupervisorReadError("cflib CRTP packet support is unavailable") from exc
        return CRTPPacket, CRTPPort

    def _read_once(self, timeout_seconds: float) -> SupervisorState:
        protocol_version = _read_protocol_version(self._cf)
        CRTPPacket, CRTPPort = self._resolve_crtp_types()

        done = Event()
        result_lock = Lock()
        result: dict[str, object] = {}

        def finish(
            *,
            bitfield: int | None = None,
            error: SupervisorReadError | None = None,
        ) -> None:
            with result_lock:
                if done.is_set():
                    return
                if error is not None:
                    result["error"] = error
                else:
                    result["bitfield"] = bitfield
                done.set()

        def supervisor_callback(packet: object) -> None:
            try:
                if packet.channel != SUPERVISOR_CH_INFO:
                    return
                data = bytes(packet.data)
                if not data or data[0] != CMD_GET_STATE_BITFIELD_RESPONSE:
                    return
                # Pinned 2026.08 firmware responds with one command byte plus a
                # uint16 supervisor bitfield. Anything else is incompatible.
                if len(data) != 3:
                    finish(
                        error=SupervisorReadError(
                            "malformed supervisor state response"
                        )
                    )
                    return
                finish(bitfield=int.from_bytes(data[1:3], byteorder="little"))
            except Exception as exc:
                finish(
                    error=SupervisorReadError(
                        f"malformed supervisor state response: {exc}"
                    )
                )

        def disconnected(_uri: str) -> None:
            reason = "Crazyflie disconnected during supervisor state read"
            self._poison(reason)
            finish(error=SupervisorReadError(reason))

        disconnect_callbacks = getattr(self._cf, "disconnected", None)
        disconnect_registered = False
        self._cf.add_port_callback(CRTPPort.SUPERVISOR, supervisor_callback)
        try:
            if (
                disconnect_callbacks is not None
                and hasattr(disconnect_callbacks, "add_callback")
                and hasattr(disconnect_callbacks, "remove_callback")
            ):
                disconnect_callbacks.add_callback(disconnected)
                disconnect_registered = True

            try:
                packet = CRTPPacket()
                packet.set_header(CRTPPort.SUPERVISOR, SUPERVISOR_CH_INFO)
                packet.data = (CMD_GET_STATE_BITFIELD,)
                self._cf.send_packet(packet)
            except Exception as exc:
                raise SupervisorReadError(
                    f"fresh supervisor state request failed: {exc}"
                ) from exc

            if not done.wait(timeout_seconds):
                raise SupervisorReadError("fresh supervisor state request timed out")
        finally:
            if disconnect_registered:
                try:
                    disconnect_callbacks.remove_callback(disconnected)
                except ValueError:
                    pass
            self._cf.remove_port_callback(CRTPPort.SUPERVISOR, supervisor_callback)

        error = result.get("error")
        if isinstance(error, SupervisorReadError):
            raise error
        bitfield = result.get("bitfield")
        if not isinstance(bitfield, int):
            raise SupervisorReadError("fresh supervisor state response is unavailable")
        return decode_supervisor_state(protocol_version, bitfield)
