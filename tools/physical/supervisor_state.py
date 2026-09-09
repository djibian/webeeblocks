#!/usr/bin/env python3
"""Fresh, fail-closed read-only Crazyflie supervisor-state observation.

This module deliberately exposes no arming, watchdog, setpoint, high-level
commander or other physical-effect operation. It exists only to obtain one fresh
supervisor state reply for a future separately authorized physical execution
consumer.

cflib's Supervisor convenience properties may return a cached bitfield when a
fresh request times out. That behavior is useful for general UI polling but is
not a sufficient freshness oracle for WebeeBlocks physical command completion.
This reader therefore owns one bounded read transaction and raises on timeout or
disconnect instead of falling back to an earlier value.
"""

from __future__ import annotations

from threading import Event, Lock
from typing import NamedTuple

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


class SupervisorReadError(RuntimeError):
    """Fail-closed error for unavailable or malformed fresh supervisor state."""


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


def _bit(value: int, position: int) -> bool:
    return bool((value >> position) & 0x01)


def decode_supervisor_state(protocol_version: int, bitfield: int) -> SupervisorState:
    if protocol_version < MIN_SUPERVISOR_PROTOCOL_VERSION:
        raise SupervisorReadError(
            "supervisor state requires CRTP protocol version 12 or later"
        )
    if bitfield < 0:
        raise SupervisorReadError("supervisor bitfield must be non-negative")
    return SupervisorState(
        protocol_version=protocol_version,
        bitfield=bitfield,
        can_be_armed=_bit(bitfield, BIT_CAN_BE_ARMED),
        is_armed=_bit(bitfield, BIT_IS_ARMED),
        is_auto_armed=_bit(bitfield, BIT_IS_AUTO_ARMED),
        can_fly=_bit(bitfield, BIT_CAN_FLY),
        is_flying=_bit(bitfield, BIT_IS_FLYING),
        is_tumbled=_bit(bitfield, BIT_IS_TUMBLED),
        is_locked=_bit(bitfield, BIT_IS_LOCKED),
        is_crashed=_bit(bitfield, BIT_IS_CRASHED),
        hl_control_active=_bit(bitfield, BIT_HL_CONTROL_ACTIVE),
        hl_traj_finished=_bit(bitfield, BIT_HL_TRAJ_FINISHED),
        hl_control_disabled=_bit(bitfield, BIT_HL_CONTROL_DISABLED),
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


def read_fresh_supervisor_state(
    cf: object,
    *,
    timeout_seconds: float = 0.2,
    crtp_types: tuple[object, object] | None = None,
) -> SupervisorState:
    """Read one fresh supervisor bitfield without any cached fallback.

    The function accepts an already-connected cflib Crazyflie object. It sends
    only the supervisor GET_STATE_BITFIELD information request, waits for the
    next matching response while its callback is installed, and fails closed on
    timeout, disconnect or malformed matching response.

    The supervisor protocol has no transaction identifier, so the future
    physical-effect session must serialize these reads and must not issue
    concurrent supervisor-state requests through another path.
    """
    if timeout_seconds <= 0:
        raise SupervisorReadError("supervisor read timeout must be positive")

    protocol_version = _read_protocol_version(cf)

    if crtp_types is None:
        try:
            from cflib.crtp.crtpstack import CRTPPacket, CRTPPort
        except ImportError as exc:
            raise SupervisorReadError("cflib CRTP packet support is unavailable") from exc
    else:
        CRTPPacket, CRTPPort = crtp_types

    done = Event()
    lock = Lock()
    result: dict[str, object] = {}

    def finish(*, bitfield: int | None = None, error: Exception | None = None) -> None:
        with lock:
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
            # Current supervisor state uses a uint16 bitfield. Accept additional
            # future bytes conservatively while requiring all currently defined
            # bits to be present.
            if len(data) < 3:
                finish(error=SupervisorReadError("malformed supervisor state response"))
                return
            finish(bitfield=int.from_bytes(data[1:], byteorder="little"))
        except Exception as exc:
            finish(error=SupervisorReadError(f"malformed supervisor state response: {exc}"))

    def disconnected(_uri: str) -> None:
        finish(error=SupervisorReadError("Crazyflie disconnected during supervisor state read"))

    disconnect_callbacks = getattr(cf, "disconnected", None)
    disconnect_registered = False
    cf.add_port_callback(CRTPPort.SUPERVISOR, supervisor_callback)
    try:
        if (
            disconnect_callbacks is not None
            and hasattr(disconnect_callbacks, "add_callback")
            and hasattr(disconnect_callbacks, "remove_callback")
        ):
            disconnect_callbacks.add_callback(disconnected)
            disconnect_registered = True

        packet = CRTPPacket()
        packet.set_header(CRTPPort.SUPERVISOR, SUPERVISOR_CH_INFO)
        packet.data = (CMD_GET_STATE_BITFIELD,)
        cf.send_packet(packet)

        if not done.wait(timeout_seconds):
            raise SupervisorReadError("fresh supervisor state request timed out")
    finally:
        if disconnect_registered:
            try:
                disconnect_callbacks.remove_callback(disconnected)
            except ValueError:
                pass
        cf.remove_port_callback(CRTPPort.SUPERVISOR, supervisor_callback)

    error = result.get("error")
    if isinstance(error, Exception):
        raise error
    bitfield = result.get("bitfield")
    if not isinstance(bitfield, int):
        raise SupervisorReadError("fresh supervisor state response is unavailable")
    return decode_supervisor_state(protocol_version, bitfield)
