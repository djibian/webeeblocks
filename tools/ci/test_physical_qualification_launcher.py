#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import socket
import sys
import tempfile
from threading import Thread

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "physical" / "launch_physical_qualification.py"
spec = importlib.util.spec_from_file_location("physical_qualification_launcher", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("qualification launcher module unavailable")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def static_ast() -> str:
    return json.dumps(
        {
            "program": [
                {"height_m": 0.6, "kind": "takeoff"},
                {"direction": "forward", "distance_m": 0.2, "kind": "move"},
                {"kind": "land"},
            ],
            "semantics": "webeeblocks-ast-v1",
            "version": 1,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def test_bootstrap_is_exact_non_authority_loopback() -> None:
    value = {
        "baseUrl": "http://127.0.0.1:8765",
        "token": "read-token",
        "preflightResponderToken": "responder-token",
        "executionAuthority": False,
    }
    require(launcher.validate_host_bootstrap(value) == value, "exact host bootstrap must be retained")
    for bad in (
        dict(value, executionAuthority=True),
        dict(value, baseUrl="http://example.com:8765"),
        {**value, "teacherFd": 9},
    ):
        try:
            launcher.validate_host_bootstrap(bad)
        except launcher.QualificationLaunchError:
            pass
        else:
            raise AssertionError("malformed/authority bootstrap was accepted")


def test_static_caller_turns_have_no_semantic_parameters() -> None:
    host, peer = socket.socketpair()
    caller = launcher.TrustedCaller(peer)
    seen: list[dict[str, object]] = []

    def fake_host() -> None:
        reader = host.makefile("r", encoding="utf-8", newline="\n")
        try:
            for _ in range(3):
                request = json.loads(reader.readline())
                seen.append(request)
                launcher._json_line(
                    host,
                    {
                        "requestId": request["requestId"],
                        "ok": True,
                        "executionAuthority": False,
                    },
                )
        finally:
            reader.close()
            host.close()

    worker = Thread(target=fake_host)
    worker.start()
    launcher.execute_bound_run(
        caller,
        profile_id="activity-1",
        ast_binding=static_ast(),
        connection_epoch="epoch-before",
    )
    caller.close()
    worker.join(timeout=2.0)
    require(not worker.is_alive(), "fake host must finish")
    require(seen[0]["op"] == "validate-run-context", "first caller request validates exact run")
    require(seen[0]["astBinding"] == static_ast(), "validation carries exact canonical AST")
    require(len(seen) == 3, "takeoff plus two post-takeoff statements must use two exact turns")
    for request in seen[1:]:
        require(set(request) == {"op", "requestId"}, "in-flight caller leaked semantic parameters")
        require(request["op"] == "execute-next-inflight", "only parameter-free in-flight operation is allowed")


def test_teacher_peer_echoes_only_exact_host_binding() -> None:
    host, peer = socket.socketpair()
    proposal = {
        "op": "teacher-run-binding-proposal",
        "requestId": "request-1",
        "challengeId": "challenge-1",
        "profileId": "activity-1",
        "astBinding": static_ast(),
        "connectionEpoch": "epoch-after",
        "executionAuthority": False,
    }
    worker = Thread(target=launcher.serve_teacher_decision, args=(peer, lambda value: value == proposal))
    worker.start()
    launcher._json_line(host, proposal)
    reader = host.makefile("r", encoding="utf-8", newline="\n")
    reply = json.loads(reader.readline())
    require(reply["op"] == "teacher-run-decision-result", "teacher reply operation")
    require(reply["approved"] is True, "explicit decision callback must control approval")
    require(reply["executionAuthority"] is False, "teacher transport remains non-authority data")
    for key in ("requestId", "challengeId", "profileId", "astBinding", "connectionEpoch"):
        require(reply[key] == proposal[key], "teacher reply changed exact host binding: " + key)
    worker.join(timeout=2.0)
    require(not worker.is_alive(), "teacher peer must close after one decision")
    reader.close()
    host.close()


def test_overlay_wires_actual_preflight_without_teacher_channel() -> None:
    bootstrap = {
        "baseUrl": "http://127.0.0.1:8765",
        "token": "read-token",
        "preflightResponderToken": "responder-token",
        "executionAuthority": False,
    }
    script = launcher._browser_runtime_script(
        bootstrap,
        "http://127.0.0.1:8766",
        "caller-token",
    )
    require("WebeeBlocksPhysicalPreflight.configure(config.host)" in script, "actual Robot Window must configure live preflight")
    require("preflightCurrentProgram()" in script, "actual workspace must cross exact preflight before run")
    require("/v1/run" in script, "actual Robot Window must use bounded one-shot caller bridge")
    require("execute-next-inflight" not in script, "browser must not own physical step cursor")
    require("teacher-fd" not in script and "teacherFd" not in script, "teacher channel leaked to browser overlay")
    require("executionAuthority: false" in script, "browser run context must remain non-authority")


def test_runtime_challenge_refresh_is_exact_ast_fail_closed() -> None:
    source = (ROOT / "plugins" / "robot_windows" / "blockly_v2" / "physical_preflight_runtime.js").read_text(encoding="utf-8")
    require("refreshCurrentProgramForChallenge" in source, "post-reset host challenge needs fresh preflight refresh")
    require("expectedAstBinding = boundAstBinding" in source, "refresh must remember exact pre-reset AST")
    require("refreshed.astBinding !== expectedAstBinding" in source, "refresh must reject changed AST")
    require("current program changed during fresh physical preflight" in source, "changed program must fail closed")
    require("executionAuthority: false" in source, "challenge assertions must remain non-authority")


def main() -> int:
    test_bootstrap_is_exact_non_authority_loopback()
    test_static_caller_turns_have_no_semantic_parameters()
    test_teacher_peer_echoes_only_exact_host_binding()
    test_overlay_wires_actual_preflight_without_teacher_channel()
    test_runtime_challenge_refresh_is_exact_ast_fail_closed()
    print("PASS trusted physical qualification launcher composition contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
