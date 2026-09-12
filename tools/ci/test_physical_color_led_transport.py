#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
sys.path.insert(0, str(PHYSICAL))

import color_led_transport as color  # noqa: E402
import physical_execution_domain as execution  # noqa: E402
import powered_session_authority as powered  # noqa: E402
import safelink_precondition as safelink  # noqa: E402
import supervisor_state  # noqa: E402
import teacher_run_authorization as teacher  # noqa: E402
import watchdog_liveness as watchdog  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_error(callable_, error_type, pattern: str) -> None:
    try:
        callable_()
    except error_type as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError(f"expected {error_type.__name__} containing {pattern!r}")


class Epoch:
    def __init__(self, value: str) -> None:
        self.value = value

    def __call__(self) -> str:
        return self.value


class Link:
    def __init__(self) -> None:
        self.needs_resending = False


class Packet:
    def __init__(self, data=b"", *, port=0x02, channel=0) -> None:
        self.port = port
        self.channel = channel
        self.data = bytearray(data)


class CallbackBus:
    def __init__(self) -> None:
        self.callbacks: list = []

    def add_callback(self, callback) -> None:
        if callback not in self.callbacks:
            self.callbacks.append(callback)

    def remove_callback(self, callback) -> None:
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    def call(self, value) -> None:
        for callback in tuple(self.callbacks):
            callback(value)


class GateLock:
    """Deterministically hold callback processing after entry freshness capture."""

    def __init__(self) -> None:
        self.entered = Event()
        self.release = Event()

    def __enter__(self):
        self.entered.set()
        require(
            self.release.wait(1.0),
            "threaded stale callback was not released",
        )
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False


class Platform:
    def get_protocol_version(self):
        return 12


class Supervisor:
    def __init__(self) -> None:
        self.watchdog_sends = 0

    def send_emergency_stop_watchdog(self) -> None:
        self.watchdog_sends += 1


class ParamElement:
    def __init__(
        self,
        *,
        ident=0x1234,
        ctype="uint32_t",
        pytype="<L",
        access="RW",
    ) -> None:
        self.ident = ident
        self.group = "colorLedBot"
        self.name = "wrgb8888"
        self.ctype = ctype
        self.pytype = pytype
        self._access = access

    def get_readable_access(self):
        return self._access


class ParamToc:
    def __init__(self, element) -> None:
        self.element = element

    def get_element_by_complete_name(self, name):
        if name != "colorLedBot.wrgb8888":
            return None
        return self.element


class FakeCrazyflie:
    def __init__(
        self,
        *,
        element=None,
        write_reply=True,
        read_reply=True,
        stale_write_value=None,
        stale_read_value=None,
        fail_remove_write=False,
    ) -> None:
        self.link_uri = "radio://0/80/2M/E7E7E7E7E7"
        self.link = Link()
        self.connected = True
        self.platform = Platform()
        self.supervisor = Supervisor()
        self.param = SimpleNamespace(
            toc=ParamToc(ParamElement() if element is None else element)
        )
        self.packet_sent = CallbackBus()
        self.write_reply = write_reply
        self.read_reply = read_reply
        self.stale_write_value = stale_write_value
        self.stale_read_value = stale_read_value
        self.fail_remove_write = fail_remove_write
        self.header_callbacks: dict[tuple[int, int], list] = {}
        self.port_callbacks: dict[int, list] = {}
        self.send_calls: list[tuple[Packet, dict]] = []
        self.current_value = 0

    def is_connected(self):
        return self.connected

    def add_port_callback(self, port, callback):
        self.port_callbacks.setdefault(port, []).append(callback)

    def remove_port_callback(self, port, callback):
        callbacks = self.port_callbacks.get(port, [])
        if callback in callbacks:
            callbacks.remove(callback)

    def add_header_callback(self, callback, port, channel):
        self.header_callbacks.setdefault((port, channel), []).append(callback)
        ident = 0x1234
        if channel == 2 and self.stale_write_value is not None:
            callback(
                Packet(
                    struct.pack("<HL", ident, self.stale_write_value),
                    port=port,
                    channel=channel,
                )
            )
        elif channel == 1 and self.stale_read_value is not None:
            callback(
                Packet(
                    struct.pack("<HBL", ident, 0, self.stale_read_value),
                    port=port,
                    channel=channel,
                )
            )

    def remove_header_callback(self, callback, port, channel):
        if channel == 2 and self.fail_remove_write:
            raise RuntimeError("forced write-listener removal failure")
        callbacks = self.header_callbacks.get((port, channel), [])
        if callback in callbacks:
            callbacks.remove(callback)

    def _emit_header(self, packet: Packet) -> None:
        for callback in tuple(
            self.header_callbacks.get((packet.port, packet.channel), ())
        ):
            callback(packet)

    def send_packet(self, *args, **kwargs):
        require(len(args) == 1, "Color LED transport must send one packet argument")
        require(not kwargs, "Color LED transport must not use expected_reply/retry kwargs")
        packet = args[0]
        require(isinstance(packet, Packet), "test packet factory must remain exact")
        self.send_calls.append((packet, kwargs))
        data = bytes(packet.data)
        if packet.channel == 2:
            require(len(data) == 6, "write request must be exact uint32 PARAM write")
            self.current_value = struct.unpack("<L", data[2:6])[0]
        elif packet.channel == 1:
            require(len(data) == 2, "read request must carry only exact parameter id")
        else:
            raise AssertionError("unexpected PARAM channel")

        # Match pinned cflib: packet_sent is called only after link.send_packet()
        # returns and before an independently delivered incoming PARAM callback is
        # accepted by this deterministic fake.
        self.packet_sent.call(packet)

        if packet.channel == 2 and self.write_reply:
            self._emit_header(Packet(data, port=packet.port, channel=packet.channel))
        elif packet.channel == 1 and self.read_reply:
            reply = data + bytes((0,)) + struct.pack("<L", self.current_value)
            self._emit_header(Packet(reply, port=packet.port, channel=packet.channel))


def packet_factory(channel: int, data: bytes):
    return Packet(data, port=0x02, channel=channel)


_counter = 0


def unique(label: str) -> str:
    global _counter
    _counter += 1
    return f"color-{label}-{_counter}"


def state(
    *,
    blocking_fault=False,
    is_flying=True,
    hl_control_active=True,
    hl_traj_finished=True,
):
    return SimpleNamespace(
        bitfield=0,
        blocking_fault=blocking_fault,
        is_flying=is_flying,
        hl_control_active=hl_control_active,
        hl_traj_finished=hl_traj_finished,
    )


def ensure_flying() -> execution.PhysicalExecutionDomain:
    domain = execution.PhysicalExecutionDomain()
    require(
        domain.phase != execution.AWAITING_COMPLETION,
        "fixture must never inherit a stranded accepted effect",
    )
    if domain.phase == execution.RECOVERY_REQUIRED:
        domain.run_reset_establishment(lambda: object())
    if domain.phase == execution.INACTIVE:
        with domain.effect_transaction(lambda: None) as effect:
            effect.mark_emitted()
            permit = effect.mark_accepted()
        domain.complete_accepted_effect(permit, execution.FLYING, lambda: True)
    require(domain.phase == execution.FLYING, "fixture must establish flying phase")
    return domain


def make_supervisor_reader(cf: FakeCrazyflie, epoch: Epoch):
    reader = supervisor_state.FreshSupervisorStateReader(
        cf,
        epoch,
        crtp_types=(Packet, SimpleNamespace(SUPERVISOR=0x0E)),
    )

    def read(*, timeout_seconds=0.2):
        del timeout_seconds
        return state()

    reader.read = read
    return reader


def mint_powered_session(cf: FakeCrazyflie, epoch: Epoch):
    factory = powered.TrustedPoweredSessionFactory(
        require_flight_known_inactive=lambda: True,
        invalidate_prior_evidence=lambda: None,
        stm_deck_power_cycle=lambda: None,
        open_post_reset_session=lambda: cf,
        close_post_reset_session=lambda _session: None,
        read_connection_epoch=lambda _session: epoch(),
        read_capabilities=lambda _session: {
            "connected": True,
            "executionAuthority": False,
            "identity": {
                "model": "crazyflie-2.1",
                "modelEvidence": "verified",
            },
            "evidence": {
                "systemSelfTestPassed": True,
                "protocolVersion": 12,
            },
        },
        assert_bound_preflight=lambda _session, _epoch: True,
        read_fresh_supervisor=lambda _session, _epoch: SimpleNamespace(
            blocking_fault=False
        ),
        identity_factory=lambda: unique("powered"),
    )
    return factory.establish()


class HostBoundColorTransport(color.TrustedBottomColorLedTransport):
    def _read_current_binding(self):
        return self.teacher_binding


class Fixture:
    def __init__(self, label: str, cf: FakeCrazyflie) -> None:
        self.cf = cf
        self.epoch = Epoch(unique(label))
        self.domain = ensure_flying()
        self.powered = mint_powered_session(cf, self.epoch)
        self.reader = make_supervisor_reader(cf, self.epoch)
        self.watchdog = watchdog.EmergencyWatchdogLivenessGuard(
            cf,
            self.epoch,
            self.reader,
            self.powered.watchdog_authority,
            keepalive_interval_seconds=0.2,
            max_host_gap_seconds=0.7,
        )
        self.watchdog.activate(supervisor_timeout_seconds=0.05)
        self.binding = teacher.PhysicalRunBinding(
            profile_id="activity-color",
            ast_binding=unique("ast"),
            connection_epoch=self.epoch(),
        )
        self.authorizer = teacher.TrustedTeacherAuthorizer()
        self.authorization = self.authorizer.authorize_run(
            self.binding,
            lambda _binding: True,
        )
        self.safelink = safelink.LiveSafeLinkPrecondition(cf, self.epoch)
        self.kwargs = dict(
            crazyflie=cf,
            execution_domain=self.domain,
            safelink_guard=self.safelink,
            teacher_authorization=self.authorization,
            powered_session=self.powered,
            watchdog_guard=self.watchdog,
            connection_epoch_reader=self.epoch,
            packet_factory=packet_factory,
            reply_timeout_seconds=0.03,
        )
        self.transport = HostBoundColorTransport(**self.kwargs)

    def close(self) -> None:
        try:
            self.watchdog.stop_for_terminal_reboot(join_timeout_seconds=0.2)
        except watchdog.WatchdogLivenessError:
            pass


def test_exact_palette_mapping() -> None:
    expected = {
        "off": 0x00000000,
        "red": 0x00FF0000,
        "green": 0x0000FF00,
        "blue": 0x000000FF,
        "yellow": 0x00FFFF00,
        "white": 0xFF000000,
    }
    for name, wrgb in expected.items():
        require(color.color_to_wrgb8888(name) == wrgb, f"wrong WRGB mapping for {name}")
    for invalid in (None, 1, "purple", "White"):
        expect_error(
            lambda invalid=invalid: color.color_to_wrgb8888(invalid),
            color.ColorLedTransportError,
            "unsupported",
        )


def test_success_is_one_write_then_fresh_readback_without_retry() -> None:
    cf = FakeCrazyflie()
    fixture = Fixture("success", cf)
    try:
        result = fixture.transport.send_color(color="red")
        require(result.accepted is True and result.status == 0, "exact write must succeed")
        require(result.wrgb8888 == 0x00FF0000, "result retains exact WRGB intent")
        require(len(cf.send_calls) == 2, "success must emit one write and one readback")
        require(
            [call[0].channel for call in cf.send_calls] == [2, 1],
            "effect must be write then causal readback",
        )
        require(
            all(not kwargs for _, kwargs in cf.send_calls),
            "no send may use generic cflib resend/expected_reply kwargs",
        )
        require(fixture.domain.phase == execution.FLYING, "causal readback restores flying")
    finally:
        fixture.close()


def _prove_callback_started_before_send_stays_stale(*, channel: int) -> None:
    is_write = channel == 2
    cf = FakeCrazyflie(write_reply=not is_write, read_reply=is_write)
    fixture = Fixture("threaded-write" if is_write else "threaded-read", cf)
    try:
        if is_write:
            request = struct.pack("<HL", 0x1234, 0x00FF0000)
            stale_reply = request
        else:
            request = struct.pack("<H", 0x1234)
            stale_reply = request + bytes((0,)) + struct.pack("<L", 0x00FF0000)
            cf.current_value = 0x00FF0000
        packet = packet_factory(channel, request)
        event = Event()
        reply_box: list[bytes | None] = [None]
        gate = GateLock()
        listener = fixture.transport._listen_for_param(
            channel,
            request[:2],
            packet,
            event,
            reply_box,
            gate,
        )
        worker = Thread(
            target=listener.header_callback,
            args=(Packet(stale_reply, port=0x02, channel=channel),),
            daemon=True,
        )
        worker.start()
        require(
            gate.entered.wait(1.0),
            "stale callback must enter before the current send",
        )

        # This exact send advances packet_sent only after the stale callback has
        # already snapshotted freshness=False. The callback resumes afterwards.
        cf.send_packet(packet)
        gate.release.set()
        worker.join(timeout=1.0)
        require(not worker.is_alive(), "stale callback must finish deterministically")
        require(
            not event.is_set() and reply_box[0] is None,
            "pre-send callback must not become fresh after packet_sent",
        )
        fixture.transport._remove_listener(listener)
    finally:
        fixture.close()


def test_threaded_pre_emission_write_reply_cannot_authorize_effect() -> None:
    _prove_callback_started_before_send_stays_stale(channel=2)


def test_threaded_pre_emission_read_reply_cannot_prove_completion() -> None:
    _prove_callback_started_before_send_stays_stale(channel=1)


def test_pre_emission_matching_write_reply_cannot_authorize_effect() -> None:
    cf = FakeCrazyflie(
        write_reply=False,
        stale_write_value=0x00FF0000,
    )
    fixture = Fixture("stale-write", cf)
    try:
        expect_error(
            lambda: fixture.transport.send_color(color="red"),
            color.ColorLedTransportError,
            "acknowledgement timeout",
        )
        require(len(cf.send_calls) == 1, "stale write reply cannot skip current write")
        require(
            fixture.domain.phase == execution.RECOVERY_REQUIRED,
            "post-emission missing fresh acknowledgement requires recovery",
        )
    finally:
        fixture.close()


def test_pre_emission_matching_read_reply_cannot_prove_completion() -> None:
    cf = FakeCrazyflie(
        write_reply=True,
        read_reply=False,
        stale_read_value=0x00FF0000,
    )
    fixture = Fixture("stale-read", cf)
    try:
        expect_error(
            lambda: fixture.transport.send_color(color="red"),
            execution.PhysicalExecutionDomainError,
            "fresh effect-completion proof failed",
        )
        require(len(cf.send_calls) == 2, "fresh read request must still be emitted")
        require(
            fixture.domain.phase == execution.RECOVERY_REQUIRED,
            "missing fresh readback after accepted write requires recovery",
        )
    finally:
        fixture.close()


def test_ambiguous_readback_poison_blocks_same_epoch_reuse() -> None:
    cf = FakeCrazyflie(write_reply=True, read_reply=False)
    fixture = Fixture("read-poison", cf)
    try:
        expect_error(
            lambda: fixture.transport.send_color(color="red"),
            execution.PhysicalExecutionDomainError,
            "fresh effect-completion proof failed",
        )
        require(
            fixture.domain.phase == execution.RECOVERY_REQUIRED,
            "ambiguous readback must require physical recovery",
        )
        expect_error(
            lambda: HostBoundColorTransport(**fixture.kwargs),
            color.ColorLedTransportError,
            "poisoned",
        )
    finally:
        fixture.close()


def test_write_listener_cleanup_failure_cannot_strand_completion_permit() -> None:
    cf = FakeCrazyflie(write_reply=True, fail_remove_write=True)
    fixture = Fixture("cleanup", cf)
    try:
        expect_error(
            lambda: fixture.transport.send_color(color="red"),
            color.ColorLedTransportError,
            "could not remove",
        )
        require(len(cf.send_calls) == 1, "cleanup failure must occur before readback")
        require(
            fixture.domain.phase == execution.RECOVERY_REQUIRED,
            "cleanup failure before mark_accepted must require recovery",
        )
        require(
            fixture.domain.phase != execution.AWAITING_COMPLETION,
            "cleanup failure must never strand the unique completion permit",
        )
    finally:
        fixture.close()


def test_direct_importable_core_has_no_positive_provenance_path() -> None:
    cf = FakeCrazyflie()
    fixture = Fixture("unbound", cf)
    try:
        core = color.TrustedBottomColorLedTransport(**fixture.kwargs)
        expect_error(
            lambda: core.send_color(color="blue"),
            color.ColorLedTransportError,
            "trusted physical host",
        )
        require(not cf.send_calls, "unbound importable core must remain effect-free")
        require(fixture.domain.phase == execution.FLYING, "pre-effect provenance rejection is neutral")
    finally:
        fixture.close()


def test_toc_identity_and_type_fail_before_effect() -> None:
    for element in (
        ParamElement(ctype="int32_t"),
        ParamElement(pytype="<l"),
        ParamElement(access="RO"),
    ):
        cf = FakeCrazyflie(element=element)
        fixture = Fixture("bad-toc", cf)
        try:
            expect_error(
                lambda: fixture.transport.send_color(color="red"),
                color.ColorLedTransportError,
                "bottom Color LED parameter",
            )
            require(not cf.send_calls, "invalid TOC evidence must fail before emission")
            require(fixture.domain.phase == execution.FLYING, "pre-effect TOC failure is neutral")
        finally:
            fixture.close()


def main() -> int:
    test_exact_palette_mapping()
    test_success_is_one_write_then_fresh_readback_without_retry()
    test_threaded_pre_emission_write_reply_cannot_authorize_effect()
    test_threaded_pre_emission_read_reply_cannot_prove_completion()
    test_pre_emission_matching_write_reply_cannot_authorize_effect()
    test_pre_emission_matching_read_reply_cannot_prove_completion()
    test_ambiguous_readback_poison_blocks_same_epoch_reuse()
    test_write_listener_cleanup_failure_cannot_strand_completion_permit()
    test_direct_importable_core_has_no_positive_provenance_path()
    test_toc_identity_and_type_fail_before_effect()
    print(
        "PASS trusted bottom Color LED transport keeps exact palette/TOC authority, "
        "uses one no-retry write plus causal readback, classifies callback freshness at exact packet_sent, "
        "poisons ambiguous same-epoch readback, and cannot strand an accepted-effect completion permit"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
