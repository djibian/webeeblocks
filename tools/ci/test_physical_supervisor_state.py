#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "physical" / "supervisor_state.py"

spec = importlib.util.spec_from_file_location("webeeblocks_supervisor_state", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load supervisor-state reader")
supervisor_state = importlib.util.module_from_spec(spec)
spec.loader.exec_module(supervisor_state)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_error(callable_, pattern: str) -> None:
    try:
        callable_()
    except supervisor_state.SupervisorReadError as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError(f"expected SupervisorReadError containing {pattern!r}")


class FakeCaller:
    def __init__(self) -> None:
        self.callbacks = []

    def add_callback(self, callback) -> None:
        self.callbacks.append(callback)

    def remove_callback(self, callback) -> None:
        self.callbacks.remove(callback)

    def call(self, *args) -> None:
        for callback in list(self.callbacks):
            callback(*args)


class FakePlatform:
    def __init__(self, protocol_version: int) -> None:
        self.protocol_version = protocol_version

    def get_protocol_version(self) -> int:
        return self.protocol_version


class FakeCRTPPort:
    SUPERVISOR = 14


class FakeCRTPPacket:
    def __init__(self) -> None:
        self.port = None
        self.channel = None
        self.data = bytearray()

    def set_header(self, port: int, channel: int) -> None:
        self.port = port
        self.channel = channel


class FakeCf:
    def __init__(self, response: bytes | None, protocol_version: int = 12) -> None:
        self.platform = FakePlatform(protocol_version)
        self.disconnected = FakeCaller()
        self.response = response
        self.callback = None
        self.callback_port = None
        self.removed = False
        self.sent = []
        self.disconnect_on_send = False
        self.send_unrelated_first = False

    def add_port_callback(self, port: int, callback) -> None:
        self.callback_port = port
        self.callback = callback

    def remove_port_callback(self, port: int, callback) -> None:
        require(port == self.callback_port, "supervisor callback cleanup port")
        require(callback is self.callback, "supervisor callback cleanup identity")
        self.removed = True

    def send_packet(self, packet) -> None:
        self.sent.append((packet.port, packet.channel, bytes(packet.data)))
        if self.disconnect_on_send:
            self.disconnected.call("radio://test")
            return
        if self.send_unrelated_first:
            self.callback(
                type(
                    "Packet",
                    (),
                    {
                        "channel": supervisor_state.SUPERVISOR_CH_INFO,
                        "data": bytearray((0x81, 0x00, 0x00)),
                    },
                )()
            )
        if self.response is not None:
            self.callback(
                type(
                    "Packet",
                    (),
                    {
                        "channel": supervisor_state.SUPERVISOR_CH_INFO,
                        "data": bytearray(self.response),
                    },
                )()
            )


CRTP_TYPES = (FakeCRTPPacket, FakeCRTPPort)


def read(cf: FakeCf, timeout_seconds: float = 0.01):
    return supervisor_state.read_fresh_supervisor_state(
        cf,
        timeout_seconds=timeout_seconds,
        crtp_types=CRTP_TYPES,
    )


def test_success_and_decode() -> None:
    bitfield = (
        (1 << supervisor_state.BIT_CAN_BE_ARMED)
        | (1 << supervisor_state.BIT_IS_AUTO_ARMED)
        | (1 << supervisor_state.BIT_CAN_FLY)
        | (1 << supervisor_state.BIT_HL_TRAJ_FINISHED)
    )
    cf = FakeCf(
        bytes(
            (
                supervisor_state.CMD_GET_STATE_BITFIELD_RESPONSE,
                bitfield & 0xFF,
                (bitfield >> 8) & 0xFF,
            )
        )
    )
    cf.send_unrelated_first = True
    state = read(cf)
    require(
        cf.sent
        == [
            (
                FakeCRTPPort.SUPERVISOR,
                supervisor_state.SUPERVISOR_CH_INFO,
                bytes((supervisor_state.CMD_GET_STATE_BITFIELD,)),
            )
        ],
        "reader must send only one GET_STATE_BITFIELD request",
    )
    require(state.protocol_version == 12, "protocol version")
    require(state.bitfield == bitfield, "bitfield round trip")
    require(state.can_be_armed, "can-be-armed bit")
    require(state.is_auto_armed, "auto-armed configuration bit")
    require(state.can_fly, "can-fly bit")
    require(state.hl_traj_finished, "trajectory-finished bit")
    require(not state.is_armed and not state.is_locked and not state.is_crashed, "unset bits")
    require(cf.removed, "supervisor callback cleanup")
    require(cf.disconnected.callbacks == [], "disconnect callback cleanup")


def test_timeout_never_reuses_previous_state() -> None:
    finished = 1 << supervisor_state.BIT_HL_TRAJ_FINISHED
    cf = FakeCf(
        bytes(
            (
                supervisor_state.CMD_GET_STATE_BITFIELD_RESPONSE,
                finished & 0xFF,
                (finished >> 8) & 0xFF,
            )
        )
    )
    first = read(cf)
    require(first.hl_traj_finished, "first fresh state")
    cf.response = None
    cf.removed = False
    expect_error(lambda: read(cf, timeout_seconds=0.001), "timed out")
    require(cf.removed, "timeout callback cleanup")
    require(
        len(cf.sent) == 2,
        "second read must issue a new request instead of consulting cached state",
    )


def test_malformed_response_fails_closed() -> None:
    cf = FakeCf(bytes((supervisor_state.CMD_GET_STATE_BITFIELD_RESPONSE, 0x01)))
    expect_error(lambda: read(cf), "malformed supervisor state response")
    require(cf.removed, "malformed response callback cleanup")


def test_disconnect_fails_closed() -> None:
    cf = FakeCf(None)
    cf.disconnect_on_send = True
    expect_error(lambda: read(cf), "disconnected during supervisor state read")
    require(cf.removed, "disconnect callback cleanup")


def test_protocol_boundary() -> None:
    legacy = FakeCf(None, protocol_version=11)
    expect_error(lambda: read(legacy), "protocol version 12 or later")
    require(legacy.sent == [], "legacy protocol must not emit supervisor request")
    require(legacy.callback is None, "legacy protocol must fail before callback registration")


def test_timeout_argument() -> None:
    cf = FakeCf(None)
    expect_error(lambda: read(cf, timeout_seconds=0), "timeout must be positive")
    require(cf.sent == [], "invalid timeout must not emit a request")


def main() -> int:
    test_success_and_decode()
    test_timeout_never_reuses_previous_state()
    test_malformed_response_fails_closed()
    test_disconnect_fails_closed()
    test_protocol_boundary()
    test_timeout_argument()

    source = MODULE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "send_arming_request",
        "send_emergency_stop",
        "send_emergency_stop_watchdog",
        "high_level_commander",
        "send_setpoint",
        "send_hover_setpoint",
        "send_velocity_world_setpoint",
    ):
        require(forbidden not in source, f"supervisor reader exposes authority surface: {forbidden}")

    print(
        "PASS fresh supervisor-state read fails closed on timeout/disconnect without execution authority"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
