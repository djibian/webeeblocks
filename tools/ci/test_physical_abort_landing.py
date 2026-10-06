#!/usr/bin/env python3
"""No hardware: production shutdown with real authority/transport/completion domains."""
from pathlib import Path
from contextlib import redirect_stderr
from hashlib import sha256
from io import StringIO
import json
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "physical"))
import production_takeoff_run as production
import physical_execution_domain as execution
import controlled_landing_transport as landing
import setpoint_hl_transport as transport
import test_physical_controlled_landing_transport as fixtures
import test_physical_setpoint_hl_transport as base


def require(value, message):
    if not value:
        raise AssertionError(message)


def controller_for(fixture):
    # The fixture establishes FLYING using the real execution domain and creates
    # real minted teacher/powered receipts, watchdog, SafeLink and ack domains.
    # Only the radio and fresh supervisor samples are injected.
    owner = object.__new__(production.ProductionTakeoffRunController)
    owner._active = production.ActivePhysicalTakeoffRun(
        fixture.cf, fixture.domain, fixture.ack, fixture.safelink,
        fixture.authorization, fixture.powered, fixture.watchdog, fixture.supervisor_reader,
    )
    owner._teacher_authorizer = fixture.authorizer
    owner._epoch_reader = fixture.epoch
    owner._altitude_reader = None
    owner._landing_started = False
    owner._recovery_outcome = "not-required"
    return owner


def shutdown_with_causal_log(owner, fixture):
    log = StringIO()
    with redirect_stderr(log):
        owner.shutdown()
        owner.shutdown()
    records = [json.loads(line.removeprefix("HOST_RECOVERY "))
               for line in log.getvalue().splitlines() if line.startswith("HOST_RECOVERY ")]
    require(len(records) == 1, "recovery outcome lost/duplicated independently of caller IPC")
    record = records[0]
    binding = fixture.authorization.binding
    require(record["outcome"] == owner.recovery_outcome and record["phase"] == fixture.domain.phase,
            "recovery log misreported outcome/physical phase")
    require(record["connectionEpoch"] == binding.connection_epoch
            and record["astSha256"] == sha256(binding.ast_binding.encode()).hexdigest(),
            "recovery log lost exact run correlation")


def test_lands_with_revoked_program_while_watchdog_is_live():
    fixture, _ = fixtures.make_fixture("abort-known-flight")
    owner = controller_for(fixture)
    owner.bind_completed_altitude(lambda: 0.7)
    # Browser/program authority may disappear; recovery needs no browser reply.
    fixture.authorization.invalidate("workspace/provenance lost")
    fixtures.queue_pre_land(fixture, completion=base.state(
        is_flying=False, hl_control_active=False, hl_traj_finished=True,
    ))
    original = fixture.cf.send_packet

    def send(*args, **kwargs):
        fixture.watchdog.assert_live()
        require(not fixture.authorization.active, "ordinary program authority survived abort")
        return original(*args, **kwargs)

    fixture.cf.send_packet = send
    try:
        shutdown_with_causal_log(owner, fixture)
        require(owner.recovery_outcome.startswith("landed:"), owner.recovery_outcome)
        request = bytes(fixture.cf.send_calls[0][0][0].data)
        command, group, descent, relative, yaw, use_yaw, speed = struct.unpack("<BBf?f?f", request)
        require(command == 10 and group == 0 and relative and use_yaw, "wrong safety landing semantics")
        require(abs(descent - 0.7) < 1e-6 and speed == 0.5 and yaw == 0, "landing lost completed altitude")
        require(fixture.domain.phase == execution.INACTIVE, "ack was mistaken for landed")
        require(not fixture.watchdog.active, "teardown did not terminate powered session after landing")
        owner.shutdown()
        require(len(fixture.cf.send_calls) == 1, "shutdown resent recovery landing")
    finally:
        fixture.close()


def test_uncertain_prerequisites_never_emit_or_retry():
    for scenario in ("epoch", "safelink", "fault", "ack", "landing-started", "altitude", "effect"):
        fixture, _ = fixtures.make_fixture("abort-" + scenario)
        owner = controller_for(fixture)
        try:
            if scenario == "epoch":
                fixture.epoch.value += "-changed"
            elif scenario == "safelink":
                fixture.cf.link.needs_resending = True
            elif scenario == "fault":
                fixture.supervisor_reads.append(base.state(blocking_fault=True))
            elif scenario == "ack":
                with fixture.ack.transaction(b"\x0c\0\x01") as claim:
                    claim.mark_emitted()  # unresolved prior effect poisons this epoch
            elif scenario == "landing-started":
                owner.mark_landing_started()
            elif scenario == "altitude":
                owner.bind_completed_altitude(lambda: float("nan"))
            elif scenario == "effect":
                with fixture.domain.effect_transaction(lambda: None) as effect:
                    effect.mark_emitted()  # no known effect outcome
            shutdown_with_causal_log(owner, fixture)
            require(not fixture.cf.send_calls, "uncertainty emitted recovery: " + scenario)
            require(not fixture.authorization.active, "uncertainty restored teacher authority")
            require(not owner.recovery_outcome.startswith("landed:"), "false landing claim")
        finally:
            fixture.close()


def test_failed_recovery_is_one_shot_and_does_not_claim_landing():
    for reply in (None, 1):
        fixture, _ = fixtures.make_fixture("abort-ambiguous-" + str(reply), reply_status=reply)
        owner = controller_for(fixture)
        fixtures.queue_pre_land(fixture)
        try:
            shutdown_with_causal_log(owner, fixture)
            require(len(fixture.cf.send_calls) == 1, "failed safety landing was retried")
            require(not owner.recovery_outcome.startswith("landed:"), "failed landing reported success")
            require(not fixture.authorization.active, "failed landing resurrected authority")
        finally:
            fixture.close()


def main():
    original = transport._default_packet_factory
    transport._default_packet_factory = base.Packet
    try:
        test_lands_with_revoked_program_while_watchdog_is_live()
        test_uncertain_prerequisites_never_emit_or_retry()
        test_failed_recovery_is_one_shot_and_does_not_claim_landing()
    finally:
        transport._default_packet_factory = original
    print("PASS terminal recovery: revoked program, live watchdog, one controlled landing, fresh completion; uncertainty and replay fail closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
