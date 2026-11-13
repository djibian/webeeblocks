#!/usr/bin/env python3
"""Adversarial verification of the real native PAUSE/WWI sidecar gate.

Synthetic data exercises the *collector*, never substitutes for Webots R2025a
in the separate mandatory native runtime job.
"""
import copy
import json
from pathlib import Path
import tempfile

from pause_wwi_evidence import verify_native_pause_evidence


SCHEMA = "webeeblocks-webots-pause-controller-sidecar-v1"
STAGES = [
    "CONTROLLER_ENTRY", "SUPERVISOR_CONSTRUCTED", "BEFORE_STEP_32",
    "AFTER_STEP_32", "SIMULATED_TIME_AFTER_STEP_32", "NATIVE_PASS",
    "PYTHON_ATEXIT",
]
BROWSER = (
    "BROWSER_LAUNCHED args=http://localhost:1234/robot_windows/"
    "ci_webots_pause_wwi/ci_webots_pause_wwi.html\\?name=Webots"
)
STDOUT = "\n".join("GP_PAUSE_WWI_" + line for line in [
    "CONTROLLER_START", "READY_SENT", "BEGIN_RECEIVED",
    "PAUSE_REQUESTED", "PAUSE_ATTESTED", "RESUME_RECEIVED",
    "STALE_RESUME_REJECTED count=1",
    "CLOCK_PRE_RESUME frozen_ms=128 now_ms=128 wall_seconds=1.576",
    "MODE_REALTIME_REQUESTED", "MODE_REALTIME_CALL_RETURNED",
    "STEP_ZERO_AFTER_RESUME_REQUESTED", "STEP_ZERO_AFTER_RESUME_RETURNED",
    "MODE_REALTIME_ATTESTED", "STEP_32_AFTER_RESUME_REQUESTED",
]) + "\nINFO: ci_webots_pause_wwi: Terminating.\n"
PROOF = {
    "schema": "webeeblocks-webots-pause-wwi-v1",
    "simulated_frozen_ms": 128, "frozen_delta_ms": 0,
    "pause_wall_seconds": 1.576, "resumed_simulated_ms": 32,
    "resume_via_robot_window_wwi": True, "wrong_token_rejected": 1,
    "steps_while_paused": 0, "simulation": "isolated-r2025a-only",
}


def trace():
    records = [
        {"schema": SCHEMA, "stage": stage,
         "wall_monotonic_seconds": 10.0 + index * 0.17}
        for index, stage in enumerate(STAGES)
    ]
    records[2].update(frozen_simulated_ms=128, mode=1)
    records[3].update(return_code=0)
    records[4].update(delta_ms=32, mode=1)
    records[5].update(delta_ms=32, proof=copy.deepcopy(PROOF))
    return records


def write_sidecar(path, records):
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n"
                for record in records), encoding="utf-8")


def check_case(label, path, records=None, console=STDOUT,
               browser=BROWSER, code=0, accepted=False, raw=None):
    if raw is not None:
        path.write_bytes(raw)
    else:
        write_sidecar(path, trace() if records is None else records)
    try:
        proof = verify_native_pause_evidence(path, console, browser, code)
    except (ValueError, OSError, UnicodeError, TypeError, KeyError) as error:
        if accepted:
            raise AssertionError("valid evidence rejected: " + label) from error
    else:
        if not accepted:
            raise AssertionError("forged/invalid evidence accepted: " + label)
        if proof != PROOF:
            raise AssertionError("not the exact native proof: " + label)


def main():
    with tempfile.TemporaryDirectory(prefix="wb-pause-verifier-") as tmp:
        path = Path(tmp) / "controller-sidecar.jsonl"
        check_case("valid native fsync proof, stdout PASS absent", path,
                   accepted=True)
        check_case("valid stdout PASS consistent with sidecar", path,
                   console=STDOUT + "GP_PAUSE_WWI_PASS " +
                   json.dumps(PROOF, sort_keys=True) + "\n",
                   accepted=True)
        bad = trace()
        bad[3]["return_code"] = -1
        check_case("negative step(32)", path, records=bad)
        bad = trace()
        bad[4]["delta_ms"] = 0
        check_case("clock did not resume", path, records=bad)
        bad = trace()
        bad[4]["mode"] = 0
        check_case("still PAUSED after resume", path, records=bad)
        bad = trace()
        bad[5]["proof"]["resumed_simulated_ms"] = 64
        check_case("different time in canonical proof", path, records=bad)
        bad = trace()
        bad[5].pop("proof")
        check_case("bare NATIVE_PASS marker", path, records=bad)
        bad = trace()
        bad[5]["proof"]["pause_wall_seconds"] = 0.01
        check_case("not frozen for 1 wall second", path, records=bad)
        bad = trace()
        bad[5]["proof"]["wrong_token_rejected"] = 0
        check_case("wrong-token rejection absent", path, records=bad)
        bad = trace()
        bad[4], bad[3] = bad[3], bad[4]
        check_case("reordered steps", path, records=bad)
        bad = trace()
        bad.append(copy.deepcopy(bad[5]))
        check_case("replayed duplicate PASS", path, records=bad)
        bad = trace()
        bad[5]["stage"] = "ABORT"
        check_case("controller aborted", path, records=bad)
        bad = trace()
        bad[5]["wall_monotonic_seconds"] = 10.1
        check_case("nonmonotonic stage timestamps", path, records=bad)
        check_case("missing prior native pause", path,
                   console=STDOUT.replace("GP_PAUSE_WWI_PAUSE_ATTESTED\n", ""))
        check_case("stale resume was never rejected", path,
                   console=STDOUT.replace("STALE_RESUME_REJECTED count=1",
                                          "STALE_RESUME_REJECTED count=0"))
        check_case("incorrect frozen clock", path,
                   console=STDOUT.replace("now_ms=128", "now_ms=160"))
        check_case("duplicated console PAUSE", path,
                   console=STDOUT + "GP_PAUSE_WWI_PAUSE_ATTESTED\n")
        check_case("contradictory stdout", path,
                   console=STDOUT + "GP_PAUSE_WWI_STEP_32_AFTER_RESUME_RETURNED garbage\n")
        check_case("different stdout PASS", path,
                   console=STDOUT + "GP_PAUSE_WWI_PASS {}\n")
        check_case("native reported error", path,
                   console=STDOUT + "GP_PAUSE_WWI_FAIL unsafe\n")
        check_case("no actual browser", path, browser="CHROME_PATH_UNKNOWN")
        check_case("unreliable Webots exit", path, code=-15)
        check_case("empty sidecar", path, raw=b"")
        check_case("truncated sidecar", path,
                   raw=b'{"stage":"CONTROLLER_ENTRY"}')
        check_case("malformed JSON duplicate keys", path,
                   raw=b'{"stage":"A","stage":"B"}\n' * 7)
    print("PASS native PAUSE evidence collector: strict stage/clock/WWI/step(32), independent fsync source, adversarial negative cases")


if __name__ == "__main__":
    main()
