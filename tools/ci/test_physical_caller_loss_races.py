#!/usr/bin/env python3
"""Machine-only EOF races through host waits and real effect/recovery domains."""
from contextlib import redirect_stderr
from io import StringIO
import json
from pathlib import Path
import socket
import sys
from threading import Event
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools/ci"), str(ROOT / "tools/physical")]
import test_physical_host_inflight_sequence as host_tests
import dynamic_run_activation
import test_dynamic_run_activation as dynamic_tests
import test_physical_setpoint_hl_transport as effect_tests
import test_physical_controlled_landing_transport as landing_tests
import test_physical_abort_landing as recovery_tests
from caller_lifetime import CallerLifetime


def test_host_wait_completion_and_epoch_races():
    for dynamic in (False, True):
        for mode in ("first-slice", "after-final-helper-check", "epoch-and-EOF"):
            host_tests.base.EVENTS.clear()
            if dynamic:
                dynamic_tests.install_dynamic_fakes()
            else:
                host_tests.install_fakes()
            signal = Event()
            elapsed = [0.0]

            def wait(seconds, guard, epoch, bound, *, assert_run_open=None):
                def sleeper(delay):
                    elapsed[0] += delay
                    if mode != "after-final-helper-check":
                        signal.set()
                        assert assert_run_open.__self__._closed.wait(1)
                        if mode == "epoch-and-EOF":
                            host_tests.base.FakeSession.latest.epoch += "-lost"
                host_tests.REAL_EXACT_WAIT(seconds, guard, epoch, bound,
                    clock=lambda: elapsed[0], sleeper=sleeper,
                    assert_run_open=assert_run_open)
                if mode == "after-final-helper-check":
                    # Loss after the pacer returns must still fail its enclosing
                    # current-program assertion before cursor completion.
                    signal.set()
                    assert assert_run_open.__self__._closed.wait(1)

            ast = json.loads(host_tests.wait_ast())
            if dynamic:
                ast["program"].insert(1, {"kind": "set_variable",
                    "variable": {"id": "x", "name": "x"},
                    "value": {"kind": "number", "value": 1}})
            output = StringIO()
            with patch.object(host_tests.base.activation, "_execute_exact_wait", wait), \
                 patch.object(dynamic_run_activation, "_execute_exact_wait", wait), \
                 redirect_stderr(output):
                replies = host_tests.run_host_sequence(
                    json.dumps(ast, sort_keys=True, separators=(",", ":")),
                    steps=1, disconnect_when_waiting=signal)
            assert replies[2]["ok"] is False
            records = [json.loads(line.removeprefix("HOST_RECOVERY "))
                for line in output.getvalue().splitlines()
                if line.startswith("HOST_RECOVERY ")]
            assert len(records) == 1
            lands = [event for event in host_tests.base.EVENTS
                if isinstance(event, tuple) and event[0] in ("terminal-land", "dynamic-land")]
            known_epoch = mode != "epoch-and-EOF"
            assert len(lands) == (1 if known_epoch else 0)
            assert records[0]["outcome"].startswith("landed:") == known_epoch
            assert host_tests.base.EVENTS.count(("transport-send", "epoch-after")) == 1
            assert host_tests.base.EVENTS.count("watchdog-stop") == 1
            print("PASS host EOF race", "dynamic" if dynamic else "static", mode)


def test_effect_ack_and_completion_loss_never_resend():
    # Run in a fresh process after the host fixture monkeypatches: these are the
    # real authority, effect, acknowledgement and production recovery classes.
    for mode in ("ACK", "missing-ACK", "completion", "epoch-loss"):
        known_completion = mode in ("ACK", "completion")
        cf = effect_tests.FakeCrazyflie(reply_status=0 if known_completion else None)
        fixture = effect_tests.Fixture("EOF-effect-" + mode, cf)
        host, peer = socket.socketpair()
        stream = host.makefile("r", encoding="utf-8")
        lifetime = CallerLifetime(stream, max_message_bytes=8192)

        def lose():
            peer.shutdown(socket.SHUT_WR)
            assert lifetime._closed.wait(1), "real socket EOF not observed"

        try:
            original_binding = fixture.transport._read_current_binding
            def binding():
                lifetime.assert_open()
                current = original_binding()
                lifetime.assert_open()
                return current
            fixture.transport._read_current_binding = binding
            original_send = cf.send_packet
            def send(*args, **kwargs):
                if mode != "completion":
                    lose()
                    if mode == "epoch-loss":
                        fixture.epoch.value += "-lost"
                return original_send(*args, **kwargs)
            cf.send_packet = send
            original_read = fixture.supervisor_reader.read
            def supervisor(**kwargs):
                state = original_read(**kwargs)
                if mode == "completion" and not state.hl_traj_finished:
                    lose()
                return state
            fixture.supervisor_reader.read = supervisor
            result = error = None
            try:
                result = fixture.transport.send_turn(angle_deg=20,
                    timing_policy=effect_tests.timing.HighLevelTimingPolicy(),
                    reply_timeout_seconds=0.03)
            except Exception as exc:
                error = exc
            assert len(cf.send_calls) == 1
            if known_completion:
                assert result.accepted and fixture.domain.phase == effect_tests.execution.FLYING
            else:
                assert error and fixture.domain.phase == effect_tests.execution.RECOVERY_REQUIRED
            try:
                fixture.transport.send_turn(angle_deg=20,
                    timing_policy=effect_tests.timing.HighLevelTimingPolicy())
            except Exception:
                pass
            else:
                raise AssertionError("caller loss permitted another ordinary effect")
            assert len(cf.send_calls) == 1
            cf.send_packet = original_send
            cf.reply_status = 0
            owner = recovery_tests.controller_for(fixture)
            owner.bind_completed_altitude(lambda: 0.8)
            fixture.supervisor_reads.clear()
            landing_tests.queue_pre_land(fixture, completion=effect_tests.state(
                is_flying=False, hl_control_active=False, hl_traj_finished=True))
            with redirect_stderr(StringIO()):
                owner.shutdown()
                owner.shutdown()
            assert not fixture.authorization.active
            assert len(cf.send_calls) == (2 if known_completion else 1)
            assert owner.recovery_outcome.startswith("landed:") == known_completion
            print("PASS real effect/ACK/completion EOF race", mode)
        finally:
            peer.close()
            lifetime.stop()
            lifetime._thread.join(1)
            stream.close()
            host.close()
            fixture.close()


if __name__ == "__main__":
    # Fixture substitutions are process-global. Keep the real-domain group
    # isolated rather than accidentally validating the host's fake transports.
    if sys.argv[1:] == ["--effects"]:
        test_effect_ack_and_completion_loss_never_resend()
    elif not sys.argv[1:]:
        import subprocess
        test_host_wait_completion_and_epoch_races()
        subprocess.run([sys.executable, str(Path(__file__).resolve()), "--effects"], check=True)
    else:
        raise SystemExit("unsupported machine-oracle arguments")
