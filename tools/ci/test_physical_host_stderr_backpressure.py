#!/usr/bin/env python3
"""Exercise the real physical-host main with saturated/closed OS stderr pipes.

Runs the existing fake Crazyflie/teacher/AST integration harness in child
processes: inherited stderr is an actual blocking pipe with no reader, not
StringIO or a mocked write. No hardware, teacher approval or flight is used.
"""
from __future__ import annotations

import faulthandler
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
from time import monotonic

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / "tools" / "ci"
PHYSICAL = ROOT / "tools" / "physical"
for directory in (CI, PHYSICAL):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import test_dynamic_run_activation as dynamic  # noqa: E402
import test_physical_host_activation as base  # noqa: E402
import test_physical_host_inflight_sequence as host  # noqa: E402
from host_diagnostics import HostDiagnostics  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def saturate_stderr(*, close_reader: bool) -> int:
    reader, writer = os.pipe()
    os.set_blocking(writer, False)
    filled = 0
    while True:
        try:
            filled += os.write(writer, b"x" * 4096)
        except BlockingIOError:
            break
    require(filled > 0, "OS pipe was not saturated")
    os.set_blocking(writer, True)
    if close_reader:
        os.close(reader)
    os.dup2(writer, 2)  # Actual sys.stderr.fileno(), not a test double.
    os.close(writer)
    if not close_reader:
        # Leave reader open but unread: the writer must never gain capacity.
        # The child owns the reader for the remainder of this test process.
        require(reader >= 3, "pipe reader unexpectedly overlaps stdio")
    return filled


def child(case: str) -> None:
    filled = saturate_stderr(close_reader=(case == "broken"))
    base.EVENTS.clear()
    if case == "test-channel":
        raise AssertionError("independent child diagnostics survive full OS stderr")
    if case in {"no-teacher", "broken"}:
        base.install_fakes()
        base.run_host(teacher_enabled=False)
        require("power-cycle" not in base.EVENTS,
                "unapproved caller unexpectedly obtained teacher authority")
    elif case == "activation":
        dynamic.install_dynamic_fakes()
        replies = host.run_host_sequence(dynamic.language_invalid_ast(), steps=1)
        require(replies[0]["ok"] is True and replies[2]["ok"] is False,
                "language-invalid AST did not fail closed")
        require(replies[2]["diagnostic"]["bindingStage"] == "staged",
                "activation failure lost staged diagnostic correlation")
        require("power-cycle" not in base.EVENTS,
                "activation failure escaped into physical preparation")
    elif case in {"execution", "lost-reply"}:
        dynamic.install_dynamic_fakes()
        dynamic.RANGE_FAIL = True
        replies = host.run_host_sequence(
            dynamic.dynamic_ast(),
            steps=1 if case == "lost-reply" else 2,
            discard_execution_reply=(case == "lost-reply"),
        )
        require((len(replies) == 2 if case == "lost-reply" else
                 replies[2]["ok"] is False and replies[3]["ok"] is False),
                "causal execution failure or caller loss was not fail-closed")
        if case != "lost-reply":
            require(replies[2]["diagnostic"]["causes"][-1]["message"]
                    == "injected fresh range failure",
                    "stderr pressure replaced the actual range failure")
        require("watchdog-stop" in base.EVENTS,
                "saturated stderr blocked terminal watchdog recovery")
        require(any(isinstance(e, tuple) and e[0] == "teacher-close"
                    for e in base.EVENTS),
                "saturated stderr blocked teacher authority teardown")
        require(not any(isinstance(e, tuple) and e[0] in {
                    "dynamic-move", "dynamic-turn", "dynamic-vertical", "dynamic-land"
                } for e in base.EVENTS),
                "execution continued after failed range observation")
    elif case == "queue-full":
        diagnostics = HostDiagnostics(sys.stderr)
        start = monotonic()
        for index in range(2000):
            diagnostics.emit("HOST_DIAGNOSTIC", {"requestId": str(index)})
        diagnostics.finish()
        require(monotonic() - start < 1.0,
                "full stderr pipe delayed producer or bounded shutdown")
        require(diagnostics.dropped > 0,
                "saturated bounded queue did not record diagnostic loss")
    else:
        raise AssertionError("unknown test case")

    if case != "queue-full":
        require(("session-close", "epoch-before") in base.EVENTS or
                ("session-close", "epoch-after") in base.EVENTS,
                "saturated stderr blocked radio session close")
    print(json.dumps({"case": case, "pipe_bytes": filled, "passed": True}), flush=True)


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        # Keep test failures and timed-out thread stacks away from the deliberately
        # saturated production stderr fd. stdout is a separate captured OS pipe.
        faulthandler.enable(file=sys.stdout, all_threads=True)
        faulthandler.dump_traceback_later(5, file=sys.stdout)
        try:
            child(sys.argv[2])
        except BaseException:
            traceback.print_exc(file=sys.stdout)
            return 1
        finally:
            faulthandler.cancel_dump_traceback_later()
        return 0
    # Refute the old test-only failure mode before examining host behaviour:
    # an assertion after filling fd 2 must exit and report on independent stdout.
    probe = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--child", "test-channel"],
        cwd=ROOT, capture_output=True, text=True, timeout=8, check=False,
    )
    require(probe.returncode == 1 and
            "independent child diagnostics survive full OS stderr" in probe.stdout,
            "test oracle cannot expose its own exceptions under full OS stderr")
    for case in (
        "no-teacher", "activation", "execution", "lost-reply", "broken", "queue-full",
    ):
        try:
            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--child", case],
                cwd=ROOT, capture_output=True, text=True, timeout=8,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise AssertionError(
                f"{case}: child timed out under real OS stderr pressure; "
                f"independent stdout stacks: {(exc.stdout or b'')[-6000:]!r}"
            ) from exc
        require(result.returncode == 0,
                f"{case}: real-pipe host failed: {result.stdout[-600:]} "
                f"{result.stderr[-600:]}")
        lines = [line for line in result.stdout.splitlines() if line.startswith("{")]
        require(bool(lines), f"{case}: child did not complete recovery")
        record = json.loads(lines[-1])
        require(record == {
            "case": case, "pipe_bytes": record["pipe_bytes"], "passed": True,
        } and record["pipe_bytes"] > 0,
                f"{case}: OS pipe saturation or result was not established")
    print("PASS physical host OS stderr backpressure: activation, failure, "
          "lost caller, broken pipe, queue saturation, recovery and no authority")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
