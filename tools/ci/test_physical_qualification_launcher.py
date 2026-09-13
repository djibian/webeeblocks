#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from threading import Thread
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
sys.path.insert(0, str(PHYSICAL))

import launch_physical_qualification as launcher  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def canonical_static_ast() -> str:
    return json.dumps(
        {
            "version": 1,
            "semantics": "webeeblocks-ast-v1",
            "program": [
                {"kind": "takeoff", "height_m": 0.8},
                {"kind": "move", "direction": "forward", "distance_m": 0.2},
                {"kind": "land"},
            ],
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_dynamic_ast() -> str:
    return json.dumps(
        {
            "version": 1,
            "semantics": "webeeblocks-ast-v1",
            "program": [
                {"kind": "takeoff", "height_m": 0.8},
                {"kind": "repeat", "count": 2, "body": [{"kind": "wait", "seconds": 0.2}]},
                {"kind": "land"},
            ],
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _request_json(url: str, token: str, *, method: str = "GET", payload=None):
    data = None
    headers = {"Authorization": "Bearer " + token, "Cache-Control": "no-store"}
    if payload is not None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    with urlopen(request, timeout=2.0) as response:
        return json.loads(response.read().decode("utf-8"))


def test_preparation_bridge_is_authenticated_one_shot_non_authority() -> None:
    bridge = launcher.QualificationPreparationBridge()
    try:
        outcome: dict[str, object] = {}

        def waiter() -> None:
            outcome["prepared"] = bridge.request_preparation(timeout_seconds=2.0)

        thread = Thread(target=waiter, daemon=True)
        thread.start()
        deadline = time.monotonic() + 2.0
        request_id = None
        while time.monotonic() < deadline:
            payload = _request_json(bridge.base_url + "/v1/prepare-request", bridge.token)
            require(payload["executionAuthority"] is False, "prepare polling must stay non-authority")
            request_id = payload["requestId"]
            if request_id is not None:
                break
            time.sleep(0.01)
        require(isinstance(request_id, str) and request_id, "launcher must mint one preparation request")
        ast = canonical_static_ast()
        reply = _request_json(
            bridge.base_url + "/v1/prepared",
            bridge.token,
            method="POST",
            payload={
                "requestId": request_id,
                "ok": True,
                "profileId": "activity-1",
                "astBinding": ast,
                "connectionEpoch": "epoch-before",
                "executionAuthority": False,
            },
        )
        require(reply == {"executionAuthority": False, "ok": True}, "bridge ack must remain non-authority")
        thread.join(timeout=2.0)
        require(not thread.is_alive(), "preparation waiter must settle")
        prepared = outcome["prepared"]
        require(prepared.profile_id == "activity-1", "exact profile must cross bridge")
        require(prepared.ast_binding == ast, "exact AST must cross bridge")
        require(prepared.connection_epoch == "epoch-before", "exact epoch must cross bridge")

        try:
            _request_json(bridge.base_url + "/v1/prepare-request", "wrong-token")
        except HTTPError as exc:
            require(exc.code == 401, "wrong bridge token must fail 401")
        else:
            raise AssertionError("wrong bridge token unexpectedly succeeded")
    finally:
        bridge.close()


def test_ephemeral_robot_window_injects_only_non_authority_bootstrap() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        robot_windows = root / "plugins" / "robot_windows"
        source = robot_windows / "blockly_v2"
        source.mkdir(parents=True)
        (source / "main.js").write_text("// main\n", encoding="utf-8")
        (source / "physical_preflight_runtime.js").write_text("// preflight\n", encoding="utf-8")
        (source / "blockly_v2.html").write_text(
            '<html><body><script src="physical_preflight_runtime.js"></script></body></html>\n',
            encoding="utf-8",
        )
        worlds = root / "worlds"
        worlds.mkdir()
        world = worlds / "base.wbt"
        world.write_text('Robot { window "blockly_v2" }\n', encoding="utf-8")
        helper = root / "helper.js"
        helper.write_text("// helper\n", encoding="utf-8")
        bootstrap = {
            "baseUrl": "http://127.0.0.1:43117",
            "token": "capability-token",
            "preflightResponderToken": "responder-token",
            "executionAuthority": False,
        }
        ephemeral = launcher.prepare_ephemeral_robot_window(
            source_plugin=source,
            source_world=world,
            helper_script=helper,
            launcher_base_url="http://127.0.0.1:42000",
            launcher_token="launcher-token",
            host_bootstrap=bootstrap,
        )
        try:
            entry = ephemeral.plugin_dir / (ephemeral.plugin_dir.name + ".html")
            stale_entry = ephemeral.plugin_dir / "blockly_v2.html"
            require(entry.is_file(), "ephemeral Robot Window must expose its exact Webots entry name")
            require(not stale_entry.exists(), "ephemeral Robot Window must not retain the stale source entry name")
            html = entry.read_text(encoding="utf-8")
            generated_world = ephemeral.world_path.read_text(encoding="utf-8")
            require("WebeeBlocksPhysicalQualificationConfig" in html, "physical config must enter actual Robot Window")
            require("physical_qualification_runtime.js" in html, "physical helper must enter actual Robot Window")
            require('"executionAuthority":false' in html, "generated browser config must be explicitly non-authority")
            require("teacher" not in html.lower(), "teacher channel must never enter browser configuration")
            require('window "blockly_v2"' not in generated_world, "ephemeral world must not reuse simulation window name")
            require(ephemeral.plugin_dir.name in generated_world, "world must bind exact ephemeral Robot Window")
        finally:
            plugin = ephemeral.plugin_dir
            generated = ephemeral.world_path
            ephemeral.close()
            require(not plugin.exists() and not generated.exists(), "ephemeral product paths must be cleaned")


def test_browser_helper_has_no_teacher_or_execution_channel() -> None:
    source = (PHYSICAL / "physical_qualification_runtime.js").read_text(encoding="utf-8")
    for required in (
        "WebeeBlocksPhysicalPreflight.configure(hostBootstrap)",
        "WebeeBlocksPhysicalPreflight.preflightCurrentProgram()",
        "/v1/prepare-request",
        "/v1/prepared",
        "executionAuthority: false",
    ):
        require(required in source, "browser helper missing non-authority preparation seam: " + required)
    for forbidden in ("teacher-run-binding-proposal", "teacher-run-decision-result", "execute-next-inflight"):
        require(forbidden not in source, "browser helper crossed trusted launcher boundary: " + forbidden)


def test_execution_request_count_uses_static_dynamic_host_boundary() -> None:
    require(launcher.execution_request_count(canonical_static_ast()) == 2, "static run must request move + terminal land")
    require(launcher.execution_request_count(canonical_dynamic_ast()) == 1, "dynamic interpreter run must be one parameter-free request")


class _FakeSocketResource:
    def __init__(self) -> None:
        self.closed = False
        self.shutdown_calls = 0

    def shutdown(self, _how: int) -> None:
        self.shutdown_calls += 1

    def close(self) -> None:
        self.closed = True


class _FakeHostProcess:
    def __init__(self) -> None:
        self.wait_calls = 0

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        self.wait_calls += 1
        return 0


class _ShutdownFailingTeacher:
    def __init__(self) -> None:
        self.messages: list[bytes] = []
        self.closed = False

    def sendall(self, payload: bytes) -> None:
        self.messages.append(bytes(payload))

    def shutdown(self, _how: int) -> None:
        raise OSError("synthetic half-close failure")

    def close(self) -> None:
        self.closed = True


def test_startup_failure_cleans_resources_acquired_before_bootstrap_failure() -> None:
    session = launcher.PhysicalQualificationSession(
        uri="radio://0/80/2M/E7E7E7E7E7",
        webots_executable="unused-webots",
    )
    host = _FakeHostProcess()
    caller = _FakeSocketResource()
    teacher = _FakeSocketResource()

    def fail_after_host_acquired() -> dict[str, object]:
        session._host = host
        session._caller = caller
        session._teacher = teacher
        raise launcher.PhysicalQualificationLauncherError("synthetic malformed host bootstrap")

    session._spawn_host = fail_after_host_acquired  # type: ignore[method-assign]
    try:
        session.start()
    except launcher.PhysicalQualificationLauncherError as exc:
        require("malformed host bootstrap" in str(exc), "startup failure cause must survive cleanup")
    else:
        raise AssertionError("startup failure unexpectedly succeeded")

    require(host.wait_calls == 1, "acquired trusted host must be reaped on startup failure")
    require(caller.closed and teacher.closed, "acquired trusted sockets must close on startup failure")
    require(
        session._host is None and session._caller is None and session._teacher is None,
        "failed startup must retain no trusted child/socket handles",
    )
    require(
        session._bridge is None and session._ephemeral is None and session._webots is None,
        "failed startup must retain no later-stage resources",
    )


def test_teacher_decision_send_is_irrevocable_before_fallible_half_close() -> None:
    session = launcher.PhysicalQualificationSession(
        uri="radio://0/80/2M/E7E7E7E7E7",
        webots_executable="unused-webots",
    )
    ast = canonical_static_ast()
    prepared = launcher.PreparedProgram(
        profile_id="activity-1",
        ast_binding=ast,
        connection_epoch="epoch-before",
    )
    proposal = {
        "op": "teacher-run-binding-proposal",
        "requestId": "teacher-1",
        "challengeId": "challenge-1",
        "profileId": "activity-1",
        "astBinding": ast,
        "connectionEpoch": "epoch-after",
        "executionAuthority": False,
    }
    teacher = _ShutdownFailingTeacher()
    session._prepared = prepared
    session._teacher = teacher  # type: ignore[assignment]

    try:
        session.decide(proposal, approved=True)
    except launcher.PhysicalQualificationLauncherError as exc:
        require("decision was sent" in str(exc), "half-close error must preserve sent-decision outcome")
    else:
        raise AssertionError("synthetic teacher half-close failure unexpectedly succeeded")

    require(session._teacher_sealed is True, "successful send must irrevocably consume the teacher decision")
    require(len(teacher.messages) == 1, "exactly one teacher decision may be transmitted")
    sent = json.loads(teacher.messages[0].decode("utf-8"))
    require(sent["approved"] is True, "first transmitted decision must preserve explicit approval")

    try:
        session.decide(proposal, approved=False)
    except launcher.PhysicalQualificationLauncherError:
        pass
    else:
        raise AssertionError("teacher decision retry unexpectedly remained available after successful send")
    require(len(teacher.messages) == 1, "half-close uncertainty must never permit a second teacher decision")
    session.close()
    require(teacher.closed, "session cleanup must still close uncertain teacher channel")


def _write_fake_host(path: Path, transcript: Path) -> None:
    path.write_text(
        '''#!/usr/bin/env python3
import argparse, json, os, socket
p=argparse.ArgumentParser(); p.add_argument('--uri'); p.add_argument('--caller-fd',type=int); p.add_argument('--browser-config-fd',type=int); p.add_argument('--teacher-fd',type=int); a=p.parse_args()
with os.fdopen(a.browser_config_fd,'w',encoding='utf-8',closefd=True) as out:
 out.write(json.dumps({'baseUrl':'http://127.0.0.1:43117','token':'cap-token','preflightResponderToken':'resp-token','executionAuthority':False},separators=(',',':'))+'\\n'); out.flush()
caller=socket.socket(fileno=a.caller_fd); teacher=socket.socket(fileno=a.teacher_fd); reader=caller.makefile('r',encoding='utf-8'); events=[]; approved=False
for line in reader:
 req=json.loads(line); events.append(req)
 if req.get('op')=='validate-run-context':
  caller.sendall((json.dumps({'requestId':req['requestId'],'ok':True,'executionAuthority':False},separators=(',',':'))+'\\n').encode())
  proposal={'op':'teacher-run-binding-proposal','requestId':'teacher-1','challengeId':'challenge-1','profileId':req['profileId'],'astBinding':req['astBinding'],'connectionEpoch':'epoch-after','executionAuthority':False}
  teacher.sendall((json.dumps(proposal,separators=(',',':'))+'\\n').encode())
  treader=teacher.makefile('r',encoding='utf-8'); decision=json.loads(treader.readline()); events.append(decision); approved=decision.get('approved') is True
 elif req.get('op')=='execute-next-inflight':
  caller.sendall((json.dumps({'requestId':req['requestId'],'ok':bool(approved),'executionAuthority':False},separators=(',',':'))+'\\n').encode())
open(r''' + repr(str(transcript)) + ''','w',encoding='utf-8').write(json.dumps(events,indent=2))
''',
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _write_fake_webots(path: Path, observed_world: Path) -> None:
    path.write_text(
        '''#!/usr/bin/env python3
import pathlib, re, sys, time
world = pathlib.Path(sys.argv[-1])
text = world.read_text(encoding='utf-8')
match = re.search(r'window "([^"]+)"', text)
if match is None:
 raise SystemExit(3)
name = match.group(1)
entry = world.parent.parent / 'plugins' / 'robot_windows' / name / (name + '.html')
if not entry.is_file():
 raise SystemExit(4)
pathlib.Path(r''' + repr(str(observed_world)) + ''').write_text(str(world),encoding='utf-8')
try:
 time.sleep(60)
except KeyboardInterrupt:
 pass
''',
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_full_launcher_composes_real_window_distinct_teacher_and_parameter_free_execution() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        robot_windows = root / "plugins" / "robot_windows"
        source = robot_windows / "blockly_v2"
        source.mkdir(parents=True)
        (source / "main.js").write_text("// main\n", encoding="utf-8")
        (source / "physical_preflight_runtime.js").write_text("// preflight\n", encoding="utf-8")
        (source / "blockly_v2.html").write_text(
            '<html><body><script src="physical_preflight_runtime.js"></script></body></html>\n',
            encoding="utf-8",
        )
        helper = root / "helper.js"
        helper.write_text("// helper\n", encoding="utf-8")
        worlds = root / "worlds"
        worlds.mkdir()
        world = worlds / "base.wbt"
        world.write_text('Robot { window "blockly_v2" }\n', encoding="utf-8")
        transcript = root / "host-events.json"
        observed_world = root / "webots-world.txt"
        fake_host = root / "fake_host.py"
        fake_webots = root / "fake_webots.py"
        _write_fake_host(fake_host, transcript)
        _write_fake_webots(fake_webots, observed_world)

        session = launcher.PhysicalQualificationSession(
            uri="radio://0/80/2M/E7E7E7E7E7",
            webots_executable=str(fake_webots),
            world_path=world,
            host_path=fake_host,
            source_plugin=source,
            helper_script=helper,
        )
        try:
            session.start()
            deadline = time.monotonic() + 2.0
            while not observed_world.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            require(observed_world.is_file(), "launcher must start Webots on generated physical world")
            require(session._bridge is not None, "launcher preparation bridge must exist")
            ast = canonical_static_ast()

            def fake_browser() -> None:
                bridge = session._bridge
                assert bridge is not None
                deadline = time.monotonic() + 3.0
                while time.monotonic() < deadline:
                    payload = _request_json(bridge.base_url + "/v1/prepare-request", bridge.token)
                    if payload["requestId"] is not None:
                        _request_json(
                            bridge.base_url + "/v1/prepared",
                            bridge.token,
                            method="POST",
                            payload={
                                "requestId": payload["requestId"],
                                "ok": True,
                                "profileId": "activity-1",
                                "astBinding": ast,
                                "connectionEpoch": "epoch-before",
                                "executionAuthority": False,
                            },
                        )
                        return
                    time.sleep(0.01)
                raise AssertionError("fake Robot Window never received prepare request")

            browser = Thread(target=fake_browser, daemon=True)
            browser.start()
            prepared, proposal = session.prepare(timeout_seconds=3.0)
            browser.join(timeout=3.0)
            require(prepared.ast_binding == ast, "launcher must retain exact browser AST")
            require(proposal["connectionEpoch"] == "epoch-after", "teacher proposal must be post-reset")
            session.decide(proposal, approved=True)
            session.execute_approved_program(timeout_seconds=3.0)
        finally:
            ephemeral_plugin = session._ephemeral.plugin_dir if session._ephemeral else None
            ephemeral_world = session._ephemeral.world_path if session._ephemeral else None
            session.close()

        deadline = time.monotonic() + 2.0
        while not transcript.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        require(transcript.is_file(), "fake host must retain deterministic channel transcript")
        events = json.loads(transcript.read_text(encoding="utf-8"))
        validate = events[0]
        decision = events[1]
        executes = [event for event in events if event.get("op") == "execute-next-inflight"]
        require(validate["op"] == "validate-run-context", "launcher must stage exact host validation")
        require(validate["astBinding"] == ast and validate["connectionEpoch"] == "epoch-before", "validation must preserve exact browser binding")
        require(decision["op"] == "teacher-run-decision-result" and decision["approved"] is True, "teacher peer must explicitly approve exact host proposal")
        require(decision["executionAuthority"] is False, "teacher transport data must remain non-authority")
        require(len(executes) == 2, "static move+land must produce exactly two ordinary execution requests")
        for request in executes:
            require(set(request) == {"op", "requestId"}, "ordinary execution must remain parameter-free")
        if ephemeral_plugin is not None:
            require(not ephemeral_plugin.exists(), "launcher must clean generated Robot Window")
        if ephemeral_world is not None:
            require(not ephemeral_world.exists(), "launcher must clean generated world")


def main() -> int:
    test_preparation_bridge_is_authenticated_one_shot_non_authority()
    test_ephemeral_robot_window_injects_only_non_authority_bootstrap()
    test_browser_helper_has_no_teacher_or_execution_channel()
    test_execution_request_count_uses_static_dynamic_host_boundary()
    test_startup_failure_cleans_resources_acquired_before_bootstrap_failure()
    test_teacher_decision_send_is_irrevocable_before_fallible_half_close()
    test_full_launcher_composes_real_window_distinct_teacher_and_parameter_free_execution()
    print(
        "PASS physical qualification launcher: real Robot Window bootstrap, distinct teacher channel, "
        "exact host binding, lifecycle fail-closed boundaries and parameter-free full-program execution"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())