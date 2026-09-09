#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import threading

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


def frame(bitfield: int) -> bytes:
    return bytes(
        (
            supervisor_state.CMD_GET_STATE_BITFIELD_RESPONSE,
            bitfield & 0xFF,
            (bitfield >> 8) & 0xFF,
        )
    )


class EpochSource:
    def __init__(self, value: str) -> None:
        self.value = value
        self.error = None

    def __call__(self) -> str:
        if self.error is not None:
            raise self.error
        return self.value


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
        self.pending_late_response = None
        self.callback = None
        self.callback_port = None
        self.removed = False
        self.sent = []
        self.request_sent = threading.Event()
        self.second_request_sent = threading.Event()
        self.disconnect_on_send = False
        self.fail_on_send = False
        self.send_unrelated_first = False

    def add_port_callback(self, port: int, callback) -> None:
        self.callback_port = port
        self.callback = callback

    def remove_port_callback(self, port: int, callback) -> None:
        require(port == self.callback_port, "supervisor callback cleanup port")
        require(callback is self.callback, "supervisor callback cleanup identity")
        self.removed = True
        self.callback = None

    def _emit(self, response: bytes) -> None:
        if self.callback is None:
            return
        self.callback(
            type(
                "Packet",
                (),
                {
                    "channel": supervisor_state.SUPERVISOR_CH_INFO,
                    "data": bytearray(response),
                },
            )()
        )

    def send_packet(self, packet) -> None:
        self.sent.append((packet.port, packet.channel, bytes(packet.data)))
        if len(self.sent) == 1:
            self.request_sent.set()
        elif len(self.sent) >= 2:
            self.second_request_sent.set()
        if self.disconnect_on_send:
            self.disconnected.call("radio://test")
            return
        if self.fail_on_send:
            raise RuntimeError("radio send failed")
        if self.send_unrelated_first:
            self._emit(bytes((0x81, 0x00, 0x00)))
        if self.pending_late_response is not None:
            pending = self.pending_late_response
            self.pending_late_response = None
            self._emit(pending)
            return
        if self.response is not None:
            self._emit(self.response)


CRTP_TYPES = (FakeCRTPPacket, FakeCRTPPort)


def make_reader(cf: FakeCf, epoch: EpochSource):
    return supervisor_state.FreshSupervisorStateReader(
        cf,
        epoch,
        crtp_types=CRTP_TYPES,
    )


def test_success_and_decode() -> None:
    bitfield = (
        (1 << supervisor_state.BIT_CAN_BE_ARMED)
        | (1 << supervisor_state.BIT_IS_AUTO_ARMED)
        | (1 << supervisor_state.BIT_CAN_FLY)
        | (1 << supervisor_state.BIT_HL_TRAJ_FINISHED)
    )
    cf = FakeCf(frame(bitfield))
    cf.send_unrelated_first = True
    epoch = EpochSource("epoch-success")
    reader = make_reader(cf, epoch)
    state = reader.read(timeout_seconds=0.01)

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
    require(state.is_auto_armed, "auto-armed bit")
    require(state.can_fly, "can-fly bit")
    require(state.hl_traj_finished, "trajectory-finished bit")
    require(not state.deck_fault and not state.blocking_fault, "healthy state")
    require(not reader.poisoned, "successful read must not poison epoch")
    require(cf.removed, "supervisor callback cleanup")
    require(cf.disconnected.callbacks == [], "disconnect callback cleanup")


def test_deck_fault_is_preserved_and_blocks() -> None:
    bitfield = (
        (1 << supervisor_state.BIT_CAN_FLY)
        | (1 << supervisor_state.BIT_DECK_FAULT)
    )
    reader = make_reader(FakeCf(frame(bitfield)), EpochSource("epoch-deck"))
    state = reader.read(timeout_seconds=0.01)
    require(state.bitfield == bitfield, "raw deck-fault bitfield")
    require(state.deck_fault, "deck fault bit must be decoded")
    require(state.blocking_fault, "deck fault must be evaluated as blocking")


def test_timeout_poison_blocks_delayed_reply_until_epoch_rotates() -> None:
    finished = 1 << supervisor_state.BIT_HL_TRAJ_FINISHED
    cf = FakeCf(frame(finished))
    epoch = EpochSource("epoch-timeout")
    reader = make_reader(cf, epoch)

    first = reader.read(timeout_seconds=0.01)
    require(first.hl_traj_finished, "first fresh state")

    cf.response = None
    expect_error(
        lambda: reader.read(timeout_seconds=0.001),
        "fresh supervisor state request timed out",
    )
    require(reader.poisoned, "timeout must poison the connection epoch")
    sent_after_timeout = len(cf.sent)

    # Model the old untagged reply arriving on the next request. A poisoned
    # reader must refuse before sending, so that reply can never be accepted.
    cf.pending_late_response = frame(finished)
    expect_error(
        lambda: reader.read(timeout_seconds=0.01),
        "poisoned until reconnect",
    )
    require(
        len(cf.sent) == sent_after_timeout,
        "poisoned epoch must not send a retry that could consume a delayed reply",
    )
    require(
        cf.pending_late_response is not None,
        "delayed reply should remain unconsumed because no retry was emitted",
    )

    expect_error(
        lambda: make_reader(cf, epoch),
        "poisoned until reconnect",
    )

    reconnected = FakeCf(frame(finished))
    new_epoch = EpochSource("epoch-timeout-reconnected")
    recovered = make_reader(reconnected, new_epoch)
    require(
        recovered.read(timeout_seconds=0.01).hl_traj_finished,
        "rotated reconnect epoch must permit a new freshness domain",
    )


def test_two_readers_share_epoch_guard_and_waiter_fails_after_poison() -> None:
    cf = FakeCf(None)
    epoch = EpochSource("epoch-two-readers")
    first = make_reader(cf, epoch)
    second = make_reader(cf, epoch)
    require(
        first._read_lock is second._read_lock,
        "readers on one connection epoch must share one serialization guard",
    )

    errors = []

    def run(reader) -> None:
        try:
            reader.read(timeout_seconds=1.0)
        except supervisor_state.SupervisorReadError as exc:
            errors.append(str(exc))

    first_thread = threading.Thread(target=run, args=(first,), daemon=True)
    first_thread.start()
    require(cf.request_sent.wait(1.0), "first reader must emit one supervisor request")

    second_thread = threading.Thread(target=run, args=(second,), daemon=True)
    second_thread.start()
    require(
        not cf.second_request_sent.wait(0.05),
        "second reader must not emit a concurrent untagged supervisor request",
    )

    cf.disconnected.call("radio://test")
    first_thread.join(1.0)
    second_thread.join(1.0)
    require(not first_thread.is_alive(), "first reader must terminate after poison")
    require(not second_thread.is_alive(), "waiting reader must terminate after poison")
    require(len(cf.sent) == 1, "waiting reader must fail closed without sending")
    require(len(errors) == 2, "both readers must fail closed")
    require(
        any("disconnected during supervisor state read" in error for error in errors),
        "first read must establish the poison reason",
    )
    require(
        any("poisoned until reconnect" in error for error in errors),
        "waiting reader must re-check epoch poison after acquiring the shared guard",
    )


def test_malformed_framing_poison() -> None:
    short_cf = FakeCf(
        bytes((supervisor_state.CMD_GET_STATE_BITFIELD_RESPONSE, 0x01))
    )
    short_reader = make_reader(short_cf, EpochSource("epoch-short"))
    expect_error(
        lambda: short_reader.read(timeout_seconds=0.01),
        "malformed supervisor state response",
    )
    require(short_reader.poisoned, "short response must poison epoch")

    extended_cf = FakeCf(
        bytes(
            (
                supervisor_state.CMD_GET_STATE_BITFIELD_RESPONSE,
                0x01,
                0x00,
                0x00,
            )
        )
    )
    extended_reader = make_reader(extended_cf, EpochSource("epoch-extended"))
    expect_error(
        lambda: extended_reader.read(timeout_seconds=0.01),
        "malformed supervisor state response",
    )
    require(extended_reader.poisoned, "extended response must poison epoch")


def test_unknown_state_bits_poison() -> None:
    unknown = 1 << 12
    reader = make_reader(FakeCf(frame(unknown)), EpochSource("epoch-unknown"))
    expect_error(
        lambda: reader.read(timeout_seconds=0.01),
        "unknown supervisor state bits set",
    )
    require(reader.poisoned, "unknown state semantics must poison epoch")


def test_disconnect_poison() -> None:
    cf = FakeCf(None)
    cf.disconnect_on_send = True
    reader = make_reader(cf, EpochSource("epoch-disconnect"))
    expect_error(
        lambda: reader.read(timeout_seconds=0.01),
        "disconnected during supervisor state read",
    )
    require(reader.poisoned, "disconnect must poison epoch")
    require(cf.removed, "disconnect callback cleanup")


def test_request_transport_failure_poison() -> None:
    cf = FakeCf(None)
    cf.fail_on_send = True
    reader = make_reader(cf, EpochSource("epoch-send-fail"))
    expect_error(
        lambda: reader.read(timeout_seconds=0.01),
        "fresh supervisor state request failed",
    )
    require(reader.poisoned, "ambiguous send failure must poison epoch")
    require(cf.removed, "send-failure callback cleanup")
    require(cf.disconnected.callbacks == [], "send-failure disconnect cleanup")


def test_connection_epoch_change_poison_and_recovery() -> None:
    cf = FakeCf(frame(0))
    epoch = EpochSource("epoch-before-change")
    reader = make_reader(cf, epoch)
    epoch.value = "epoch-after-change"
    expect_error(
        lambda: reader.read(timeout_seconds=0.01),
        "connection epoch changed",
    )
    require(reader.poisoned, "old epoch must be poisoned after rotation")
    require(cf.sent == [], "epoch mismatch must fail before supervisor request")

    replacement = make_reader(
        FakeCf(frame(0)),
        EpochSource("epoch-after-change"),
    )
    require(
        replacement.read(timeout_seconds=0.01).bitfield == 0,
        "new reconnect epoch must establish a separate freshness domain",
    )


def test_protocol_boundary_poison() -> None:
    cf = FakeCf(None, protocol_version=11)
    reader = make_reader(cf, EpochSource("epoch-legacy"))
    expect_error(
        lambda: reader.read(timeout_seconds=0.01),
        "protocol version 12 or later",
    )
    require(reader.poisoned, "unsupported supervisor protocol must poison epoch")
    require(cf.sent == [], "legacy protocol must not emit supervisor request")


def test_invalid_timeout_has_no_transport_effect() -> None:
    cf = FakeCf(frame(0))
    reader = make_reader(cf, EpochSource("epoch-invalid-timeout"))
    expect_error(
        lambda: reader.read(timeout_seconds=0),
        "timeout must be positive",
    )
    require(not reader.poisoned, "invalid local timeout must not poison connection")
    require(cf.sent == [], "invalid timeout must not emit a request")
    require(
        reader.read(timeout_seconds=0.01).bitfield == 0,
        "same epoch remains usable when no ambiguous transport occurred",
    )


def main() -> int:
    test_success_and_decode()
    test_deck_fault_is_preserved_and_blocks()
    test_timeout_poison_blocks_delayed_reply_until_epoch_rotates()
    test_two_readers_share_epoch_guard_and_waiter_fails_after_poison()
    test_malformed_framing_poison()
    test_unknown_state_bits_poison()
    test_disconnect_poison()
    test_request_transport_failure_poison()
    test_connection_epoch_change_poison_and_recovery()
    test_protocol_boundary_poison()
    test_invalid_timeout_has_no_transport_effect()

    source = MODULE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "send_arming_request",
        "send_emergency_stop",
        "send_emergency_stop_watchdog",
        "HighLevelCommander(",
        "send_setpoint",
        "send_hover_setpoint",
        "send_velocity_world_setpoint",
    ):
        require(
            forbidden not in source,
            f"supervisor reader exposes authority surface: {forbidden}",
        )

    print(
        "PASS connection-epoch supervisor freshness fails closed without execution authority"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
