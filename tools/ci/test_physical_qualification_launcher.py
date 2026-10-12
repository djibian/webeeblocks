#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import socket
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


def test_wait_deadline_admission_precedes_all_host_and_teacher_exchange() -> None:
    from physical_dynamic_preflight import validate_bound_dynamic_program
    def binding(middle):
        ast = json.loads(canonical_dynamic_ast())
        ast["program"][1:-1] = middle
        return json.dumps(ast, separators=(",", ":"), sort_keys=True)

    wait = {"kind": "wait", "seconds": 5}
    for repeats in (6, 8):
        repeated = {"kind": "repeat", "count": repeats, "body": [wait]}
        for middle in ([repeated], [{"kind": "if", "condition": {"kind": "compare", "op": "GT",
                                     "left": {"kind": "range", "direction": "front", "unit": "m"},
                                     "right": {"kind": "number", "value": 0.8}},
                                     "then": [repeated], "else": []}]):
            ast = binding(middle)
            validate_bound_dynamic_program(ast)  # Otherwise valid physical paths.
            class Bridge:
                def request_preparation(self, **_kwargs):
                    return launcher.PreparedProgram("activity-1", ast, "epoch-before")
            session = launcher.PhysicalQualificationSession(uri="radio://test", webots_executable="unused")
            caller = _RecordingCaller()
            teacher = _ShutdownFailingTeacher()
            session._bridge, session._caller, session._teacher = Bridge(), caller, teacher
            try:
                session.prepare()
            except launcher.PhysicalQualificationLauncherError as exc:
                require("before teacher authorization" in str(exc), "wrong admission failure")
            else:
                raise AssertionError("waits exhausting the whole request were admitted")
            require(caller.messages == [] and teacher.messages == [], "rejection occurred after host/teacher exchange")
            require(not session._teacher_decision_attempted and session._prepared is None,
                    "failed admission established authority/preparation")

    # Separate static waits have separate deadlines; no aggregate static cap.
    launcher.validate_qualification_wait_budget(binding([wait] * 8))
    launcher.validate_qualification_wait_budget(canonical_dynamic_ast())
    launcher.validate_qualification_wait_budget(binding([
        {"kind": "repeat", "count": 5, "body": [wait]},
    ]))
    # Bound the structural proof without expanding repeats or evaluating branches.
    nested = wait
    for _ in range(18):
        nested = {"kind": "repeat", "count": 20, "body": [nested]}
    try:
        launcher.validate_qualification_wait_budget(binding([nested]))
    except launcher.PhysicalQualificationLauncherError:
        pass
    else:
        raise AssertionError("nested wait overflow admitted")


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


class _SendFailingTeacher:
    def __init__(self) -> None:
        self.send_calls = 0
        self.closed = False

    def sendall(self, _payload: bytes) -> None:
        self.send_calls += 1
        raise OSError("synthetic peer-close write failure")

    def shutdown(self, _how: int) -> None:
        return

    def close(self) -> None:
        self.closed = True


class _RecordingTeacher:
    def __init__(self) -> None:
        self.messages: list[bytes] = []
        self.closed = False

    def sendall(self, payload: bytes) -> None:
        self.messages.append(bytes(payload))

    def shutdown(self, _how: int) -> None:
        return

    def close(self) -> None:
        self.closed = True


class _RecordingCaller:
    def __init__(self) -> None:
        self.messages: list[bytes] = []
        self.closed = False

    def sendall(self, payload: bytes) -> None:
        self.messages.append(bytes(payload))

    def shutdown(self, _how: int) -> None:
        return

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
    caller = _RecordingCaller()
    session._prepared = prepared
    session._teacher = teacher  # type: ignore[assignment]
    session._caller = caller  # type: ignore[assignment]

    try:
        session.decide(proposal, approved=True)
    except launcher.PhysicalQualificationLauncherError as exc:
        require("decision was sent" in str(exc), "half-close error must preserve sent-decision outcome")
    else:
        raise AssertionError("synthetic teacher half-close failure unexpectedly succeeded")

    require(session._teacher_decision_attempted is True, "teacher decision attempt must be one-shot")
    require(session._teacher_sealed is False, "uncertain half-close must not establish a sealed exchange")
    require(session._teacher_approved is False, "uncertain half-close must not establish positive approval")
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
    try:
        session.execute_approved_program(timeout_seconds=0.1)
    except launcher.PhysicalQualificationLauncherError:
        pass
    else:
        raise AssertionError("uncertain teacher half-close unexpectedly enabled execution")
    require(caller.messages == [], "uncertain half-close must emit no ordinary execution request")
    session.close()
    require(teacher.closed, "session cleanup must still close uncertain teacher channel")


def test_failed_teacher_decision_write_is_terminal_and_not_retriable() -> None:
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
    teacher = _SendFailingTeacher()
    caller = _RecordingCaller()
    session._prepared = prepared
    session._teacher = teacher  # type: ignore[assignment]
    session._caller = caller  # type: ignore[assignment]

    try:
        session.decide(proposal, approved=True)
    except launcher.PhysicalQualificationLauncherError as exc:
        require("outcome is ambiguous" in str(exc), "failed write must report ambiguous one-shot outcome")
    else:
        raise AssertionError("synthetic teacher write failure unexpectedly succeeded")

    require(session._teacher_decision_attempted is True, "failed write must consume the one-shot attempt")
    require(session._teacher_sealed is False, "failed write must not establish completed delivery")
    require(session._teacher_approved is False, "failed write must not establish positive approval")
    require(teacher.send_calls == 1, "ambiguous teacher write must be attempted exactly once")

    try:
        session.decide(proposal, approved=True)
    except launcher.PhysicalQualificationLauncherError:
        pass
    else:
        raise AssertionError("ambiguous teacher write unexpectedly allowed a retry")
    require(teacher.send_calls == 1, "ambiguous teacher write must never be retried")

    try:
        session.execute_approved_program(timeout_seconds=0.1)
    except launcher.PhysicalQualificationLauncherError:
        pass
    else:
        raise AssertionError("ambiguous approval write unexpectedly enabled execution")
    require(caller.messages == [], "no ordinary execution request may follow ambiguous teacher approval")
    session.close()


def test_denied_teacher_decision_never_enables_execution() -> None:
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
    teacher = _RecordingTeacher()
    caller = _RecordingCaller()
    session._prepared = prepared
    session._teacher = teacher  # type: ignore[assignment]
    session._caller = caller  # type: ignore[assignment]

    session.decide(proposal, approved=False)
    require(session._teacher_sealed is True, "DENY must consume the exact teacher decision")
    require(session._teacher_approved is False, "DENY must never establish positive approval")
    try:
        session.execute_approved_program(timeout_seconds=0.1)
    except launcher.PhysicalQualificationLauncherError as exc:
        require("positively approved" in str(exc), "DENY must fail before ordinary execution IPC")
    else:
        raise AssertionError("DENY unexpectedly enabled physical execution requests")
    require(caller.messages == [], "DENY must emit no ordinary execution request")
    session.close()


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


def test_execution_write_is_one_shot_even_when_delivery_is_ambiguous():
    session = launcher.PhysicalQualificationSession(uri="radio://test", webots_executable="unused")
    session._prepared = launcher.PreparedProgram("activity-1", canonical_static_ast(), "epoch")
    session._teacher_sealed = session._teacher_approved = True
    caller = _RecordingCaller()
    writes = []
    def fail(payload):
        writes.append(payload)
        raise OSError("partial send")
    caller.sendall = fail
    session._caller = caller
    for _ in range(2):
        try:
            session.execute_approved_program(timeout_seconds=0.01)
        except launcher.PhysicalQualificationLauncherError:
            pass
        else:
            raise AssertionError("ambiguous execution write succeeded")
    require(len(writes) == 1, "ordinary execution request was retried")
    session.close()


def test_socket_deadline_is_total_and_finite():
    class Drip:
        def __init__(self): self.now = 0; self.timeouts = []
        def gettimeout(self): return None
        def settimeout(self, value): self.timeouts.append(value)
        def recv(self, _size): self.now += 0.4; return b" "
    drip = Drip()
    original = launcher.monotonic
    launcher.monotonic = lambda: drip.now
    try:
        try:
            launcher._read_socket_line(drip, timeout_seconds=1.0)
        except launcher.PhysicalQualificationLauncherError:
            pass
        require(len(drip.timeouts) == 4 and drip.timeouts[-1] is None,
                "per-byte timeout extended the total message deadline")
        for value in (True, float("nan"), float("inf"), "1"):
            try:
                launcher._read_socket_line(drip, timeout_seconds=value)
            except launcher.PhysicalQualificationLauncherError:
                pass
            else:
                raise AssertionError("invalid timeout accepted")
    finally:
        launcher.monotonic = original


def test_teardown_never_kills_a_possibly_authorized_host():
    events = []
    class Process:
        def __init__(self, name, pending=False): self.name=name; self.pending=pending
        def poll(self): return None
        def wait(self, timeout):
            events.append((self.name, "wait", timeout))
            if self.pending: raise launcher.subprocess.TimeoutExpired(self.name, timeout)
            return 0
        def terminate(self): events.append((self.name, "terminate"))
        def kill(self): raise AssertionError("forced kill")
    session = launcher.PhysicalQualificationSession(uri="radio://test", webots_executable="unused")
    session._teacher_decision_attempted = True
    session._host = Process("host", pending=True)
    session._webots = Process("webots")
    try:
        session.close()
    except launcher.PhysicalQualificationLauncherError as exc:
        require("unresolved" in str(exc), "timeout falsely claimed teardown")
    else:
        raise AssertionError("pending authorized host falsely reaped")
    require(events == [("host", "wait", 10.0)], "timeout killed flight/provenance owner")
    pending_host = session._host
    session._host.pending = False
    try:
        session.close()
    except launcher.PhysicalQualificationLauncherError as exc:
        require("previously failed" in str(exc) and exc.__cause__ is not None,
                "unresolved host teardown was silently retried or lost its cause")
    else:
        raise AssertionError("second cleanup silently reused a timed-out wait")
    require(events == [("host", "wait", 10.0)]
            and session._host is pending_host and session._webots is not None,
            "failed cleanup retried host wait or destroyed safety-support resources")


def test_caller_loss_is_observed_during_a_blocking_operation():
    import socket
    from caller_lifetime import CallerLifetime
    host, peer = socket.socketpair()
    reader = host.makefile("r", encoding="utf-8")
    lifetime = CallerLifetime(reader, max_message_bytes=128)
    try:
        peer.sendall(b'{"op":"execute-next-inflight"}\n')
        require(next(iter(lifetime)).startswith('{"op"'), "request lost")
        lifetime.assert_open()
        peer.shutdown(socket.SHUT_WR)
        # The main host thread is occupied by this modeled backend operation;
        # EOF must be observed without waiting for its request loop to resume.
        require(lifetime._closed.wait(1), "blocking execution hid caller EOF")
        try:
            lifetime.assert_open()
        except RuntimeError as exc:
            require("revoked" in str(exc), "EOF did not revoke ordinary execution")
        else:
            raise AssertionError("caller EOF retained ordinary execution")
    finally:
        lifetime.stop(); peer.close(); host.shutdown(socket.SHUT_RD); reader.close(); host.close()


def test_failed_host_exit_cleans_resources_and_never_reports_success():
    events = []
    class Host:
        def wait(self, timeout):
            events.append("host finished")
            return 7
        def terminate(self):
            raise AssertionError("completed host was terminated again")
    class Resource:
        def close(self):
            events.append("resource closed")
    session = launcher.PhysicalQualificationSession(uri="radio://test", webots_executable="unused")
    session._host = Host()
    session._bridge = Resource()
    session._ephemeral = Resource()
    try:
        session.close()
    except launcher.PhysicalQualificationLauncherError as exc:
        require("unsuccessfully: 7" in str(exc), "host failure code was lost")
    else:
        raise AssertionError("failed host exit became successful qualification")
    require(events == ["host finished", "resource closed", "resource closed"],
            "known host failure prevented safe remaining cleanup")
    require(session._host is None and session._bridge is None and session._ephemeral is None,
            "completed cleanup retained resources")


def test_teardown_failure_preserves_original_execution_diagnostic():
    session = launcher.PhysicalQualificationSession(uri="radio://test", webots_executable="unused")
    def fail(): raise launcher.PhysicalQualificationLauncherError("host teardown unresolved")
    session.close = fail
    original = launcher.PhysicalQualificationLauncherError("HOST_DIAGNOSTIC root cause")
    try:
        session.__exit__(type(original), original, None)
    except launcher.PhysicalQualificationLauncherError as exc:
        require("HOST_DIAGNOSTIC root cause" in str(exc) and "host teardown unresolved" in str(exc),
                "teardown masked the initiating diagnostic")
        require(exc.__cause__ is original, "original exception identity lost")
    else:
        raise AssertionError("teardown failure was hidden")
def test_host_failure_evidence_reaches_terminal_without_next_command() -> None:
    session = launcher.PhysicalQualificationSession(uri="radio://0/80/2M", webots_executable="unused")
    caller, host = socket.socketpair()
    session._caller = caller
    session._prepared = launcher.PreparedProgram("activity-1", canonical_static_ast(), "epoch-before")
    session._teacher_sealed = True
    session._teacher_approved = True
    received = []

    def fail():
        request = launcher._read_socket_line(host, timeout_seconds=1)
        received.append(request)
        launcher._write_socket_line(host, {
            "requestId": request["requestId"], "ok": False, "executionAuthority": False,
            "diagnostic": {"connectionEpoch": "epoch-after", "causes": [
                {"type": "RangeReadError", "message": "range.front raw_mm=8190"}
            ]},
        })

    thread = Thread(target=fail)
    thread.start()
    try:
        try:
            session.execute_approved_program(timeout_seconds=1)
        except launcher.PhysicalQualificationLauncherError as exc:
            require("HOST_DIAGNOSTIC" in str(exc) and "raw_mm=8190" in str(exc), "terminal masked cause")
            require("epoch-after" in str(exc), "terminal masked epoch")
        else:
            raise AssertionError("host failure accepted")
        thread.join(1)
        require(len(received) == 1, "failure must not advance the program")
    finally:
        caller.close()
        host.close()



def test_voluntary_abandon_is_one_shot_during_blocking_static_and_dynamic_request():
    from caller_lifetime import CallerLifetime
    from threading import Event
    class CallerProxy:
        def __init__(self, sock):
            self.sock = sock
            self.writes = []
            self.half_closes = []
        def __getattr__(self, name):
            return getattr(self.sock, name)
        def sendall(self, data):
            self.writes.append(data)
            self.sock.sendall(data)
        def shutdown(self, how):
            self.half_closes.append(how)
            self.sock.shutdown(how)

    for ast in (canonical_static_ast(), canonical_dynamic_ast()):
        for positive_reply in (False, True):
            caller, host = socket.socketpair()
            proxy = CallerProxy(caller)
            reader = host.makefile("r", encoding="utf-8")
            lifetime = CallerLifetime(reader, max_message_bytes=8192)
            session = launcher.PhysicalQualificationSession(uri="radio://test", webots_executable="unused")
            session._caller = proxy
            session._prepared = launcher.PreparedProgram("activity-1", ast, "epoch-before")
            session._teacher = _RecordingTeacher()
            session._teacher_sealed = session._teacher_approved = True
            received, outcomes, requests = [], {}, []
            request_seen = Event()
            def serve():
                try:
                    request = json.loads(next(iter(lifetime)))
                    received.append(request)
                    request_seen.set()
                    require(lifetime._closed.wait(2), "abandon was hidden by a blocking request")
                    launcher._write_socket_line(host, {
                        "requestId": request["requestId"], "ok": positive_reply,
                        "executionAuthority": False,
                        "diagnostic": {"causes": [{"message": "known host failure"}]},
                    })
                except Exception as exc:
                    outcomes["host_error"] = exc
            def execute():
                try:
                    session.execute_approved_program(timeout_seconds=2)
                    outcomes["success"] = True
                except Exception as exc:
                    outcomes["execution_error"] = exc
            worker, execution = Thread(target=serve), Thread(target=execute)
            worker.start()
            execution.start()
            try:
                require(request_seen.wait(2), "execution did not reach its blocked reply")
                signals = [Thread(target=lambda: requests.append(session.request_abandon())) for _ in range(8)]
                for thread in signals: thread.start()
                for thread in signals: thread.join(2)
                execution.join(2)
                worker.join(2)
                require(all(not thread.is_alive() for thread in [*signals, execution, worker]),
                        "abandon competed with blocking execution")
                require("host_error" not in outcomes and "execution_error" in outcomes
                        and "success" not in outcomes, "abandon was promoted to normal success")
                require(requests.count(True) == 1 and requests.count(False) == 7,
                        "concurrent gestures emitted duplicate signals")
                require(proxy.half_closes == [socket.SHUT_WR] and len(proxy.writes) == 1
                        and len(received) == 1, "abandon replayed or advanced ordinary execution")
                require(session._teacher.messages == [] and not session._execution_completed,
                        "abandon created teacher authority or false completion")
                if not positive_reply:
                    require("known host failure" in str(outcomes["execution_error"]),
                            "operator abandon masked host causal diagnostics")
                try:
                    session.execute_approved_program(timeout_seconds=0.1)
                except launcher.PhysicalQualificationLauncherError:
                    pass
                else:
                    raise AssertionError("abandoned execution remained replayable")
                require(len(proxy.writes) == 1, "second execution wrote IPC")
            finally:
                lifetime.stop()
                caller.close()
                host.shutdown(socket.SHUT_RD)
                lifetime._thread.join(1)
                reader.close()
                host.close()


def test_abandon_does_not_wait_for_send_and_unknown_signal_is_never_retried():
    from threading import Event
    entered, release, signalled = Event(), Event(), Event()
    class BlockedCaller:
        def __init__(self):
            self.sends = self.shutdowns = 0
        def sendall(self, _data):
            self.sends += 1
            entered.set()
            require(release.wait(2), "test sender not released")
            raise OSError("unknown partial IPC write")
        def shutdown(self, how):
            require(how == socket.SHUT_WR, "abandon closed read/reply direction")
            self.shutdowns += 1
            signalled.set()
            raise OSError("unknown shutdown outcome")
    session = launcher.PhysicalQualificationSession(uri="radio://test", webots_executable="unused")
    caller = BlockedCaller()
    session._caller = caller
    session._prepared = launcher.PreparedProgram("activity-1", canonical_static_ast(), "epoch-before")
    session._teacher_sealed = session._teacher_approved = True
    errors = []
    def execute():
        try: session.execute_approved_program(timeout_seconds=1)
        except Exception as exc: errors.append(exc)
    worker = Thread(target=execute)
    worker.start()
    try:
        require(entered.wait(1), "write did not start")
        try:
            session.request_abandon()
        except launcher.PhysicalQualificationLauncherError as exc:
            require("uncertain" in str(exc), "unknown signal became confirmed delivery")
        else:
            raise AssertionError("unknown signal falsely succeeded")
        require(signalled.is_set() and not release.is_set(),
                "signal waited for the outstanding IPC write")
        require(session.request_abandon() is False and caller.shutdowns == 1,
                "ambiguous signal was retried")
    finally:
        release.set()
        worker.join(2)
    require(not worker.is_alive() and errors and caller.sends == 1,
            "partial request was replayed")


def test_abandon_before_approval_and_after_completion_preserves_authority():
    from unittest.mock import patch
    def prepared_session():
        session = launcher.PhysicalQualificationSession(uri="radio://test", webots_executable="unused")
        session._caller = _RecordingCaller()
        session._teacher = _RecordingTeacher()
        session._prepared = launcher.PreparedProgram("activity-1", canonical_dynamic_ast(), "epoch-before")
        return session
    session = prepared_session()
    require(session.request_abandon(), "pre-approval cancellation did not consume signal")
    try:
        session.decide({}, approved=True)
    except launcher.PhysicalQualificationLauncherError:
        pass
    else:
        raise AssertionError("abandon permitted later approval")
    require(session._teacher.messages == [] and not session._teacher_decision_attempted,
            "abandon emitted approval")
    session = prepared_session()
    session._teacher_sealed = session._teacher_approved = True
    def reply(*_args, **_kwargs):
        sent = json.loads(session._caller.messages[-1])
        return {"requestId": sent["requestId"], "ok": True, "executionAuthority": False}
    with patch.object(launcher, "_read_socket_line", reply):
        session.execute_approved_program()
    require(session._execution_completed and session.request_abandon() is False
            and not session._abandon_requested.is_set(), "late gesture reopened completed execution")



def test_abandon_preempts_unclaimed_positive_decision_on_real_host_channels():
    """Block validation before approval commitment, then observe terminal intent."""
    from threading import Event
    from unittest.mock import patch
    from caller_lifetime import CallerLifetime
    from post_reset_teacher_decision import PostResetTeacherDecisionChannel
    from teacher_run_authorization import PhysicalRunBinding, TrustedTeacherAuthorizer

    for unknown_shutdown in (False, True):
        launcher_teacher, host_teacher = socket.socketpair()
        launcher_caller, host_caller = socket.socketpair()
        read_file = host_caller.makefile("r", encoding="utf-8")
        lifetime = CallerLifetime(read_file, max_message_bytes=8192)
        prepared = launcher.PreparedProgram("activity-1", canonical_static_ast(), "epoch-before")
        binding = PhysicalRunBinding(prepared.profile_id, prepared.ast_binding, "epoch-after")
        channel = PostResetTeacherDecisionChannel(
            host_teacher, lambda: "epoch-after", challenge_id_factory=lambda: "challenge-race"
        )
        authorizer = TrustedTeacherAuthorizer()
        session = launcher.PhysicalQualificationSession(uri="radio://test", webots_executable="unused")
        session._teacher = launcher_teacher
        session._prepared = prepared
        approval_in_preparation, resume_approval = Event(), Event()
        signal_entered, release_signal = Event(), Event()
        approvals, abandonments, host_outcomes = [], [], []

        class SlowCaller:
            def __init__(self, real):
                self.real = real
                self.shutdown_calls = []
            def shutdown(self, how):
                self.shutdown_calls.append(how)
                signal_entered.set()
                require(release_signal.wait(3), "abandon signal never released")
                if unknown_shutdown:
                    raise OSError("undelivered or unknown caller half-close")
                return self.real.shutdown(how)
            def close(self):
                return self.real.close()

        caller = SlowCaller(launcher_caller)
        session._caller = caller
        def host_receive():
            try:
                host_outcomes.append(channel.receive_authorization_for_binding(
                    authorizer, binding, decision_timeout_seconds=1.0
                ))
            except Exception as exc:
                host_outcomes.append(exc)

        actual_proposal = launcher._teacher_proposal
        def delayed_proposal(value, exact):
            approval_in_preparation.set()
            require(resume_approval.wait(3), "approval preparation not released")
            return actual_proposal(value, exact)

        def decide():
            try:
                session.decide(proposal, approved=True)
                approvals.append("approved")
            except Exception as exc:
                approvals.append(exc)

        def abandon():
            try:
                abandonments.append(session.request_abandon())
            except Exception as exc:
                abandonments.append(exc)

        host_worker = Thread(target=host_receive)
        host_worker.start()
        try:
            proposal = launcher._read_socket_line(launcher_teacher, timeout_seconds=2)
            with patch.object(launcher, "_teacher_proposal", delayed_proposal):
                approving = Thread(target=decide)
                approving.start()
                require(approval_in_preparation.wait(2), "approval did not reach pre-commit gate")
                abandoning = Thread(target=abandon)
                abandoning.start()
                require(signal_entered.wait(2) and session._abandon_requested.is_set(),
                        "abandonment intent was not consumed before approval commitment")
                require(not session._teacher_decision_attempted,
                        "test missed the pre-commit teacher decision window")
                resume_approval.set()
                approving.join(2)
                require(not approving.is_alive(), "approval blocked on an unrelated half-close")
                require(len(approvals) == 1 and isinstance(
                    approvals[0], launcher.PhysicalQualificationLauncherError
                ), "positive approval escaped after an earlier abandonment intent")
                require(not session._teacher_decision_attempted and not session._teacher_approved,
                        "abandonment still allowed teacher commitment")
                require(not authorizer.has_active_run, "positive authority minted after abandonment")

            release_signal.set()
            abandoning.join(2)
            require(not abandoning.is_alive(), "abandon signal did not complete")
            require(caller.shutdown_calls == [socket.SHUT_WR], "signal was repeated")
            if unknown_shutdown:
                require(len(abandonments) == 1 and "uncertain" in str(abandonments[0]),
                        "unknown signal incorrectly certified as delivered")
            else:
                require(abandonments == [True] and lifetime._closed.wait(2),
                        "delivered EOF failed to revoke real caller lifetime")
            session.close()
            host_worker.join(3)
            require(not host_worker.is_alive() and len(host_outcomes) == 1
                    and isinstance(host_outcomes[0], Exception)
                    and not authorizer.has_active_run, "real host minted a late receipt")
        finally:
            resume_approval.set()
            release_signal.set()
            launcher_teacher.close()
            launcher_caller.close()
            lifetime.stop()
            host_caller.shutdown(socket.SHUT_RD)
            lifetime._thread.join(2)
            read_file.close()
            host_caller.close()
            host_teacher.close()
            host_worker.join(2)


def test_abandon_and_cleanup_share_one_half_close_claim():
    """Both scheduling orders preserve one SHUT_WR even after an unknown outcome."""
    from threading import Event
    for abandon_first in (True, False):
        for unknown_shutdown in (False, True):
            entered, release = Event(), Event()
            calls, results = [], []
            session = launcher.PhysicalQualificationSession(uri="radio://test", webots_executable="unused")
            class DelayedCaller:
                def shutdown(self, how):
                    calls.append(how)
                    entered.set()
                    require(release.wait(3), "scheduled shutdown never released")
                    if unknown_shutdown:
                        raise OSError("unknown half-close outcome")
                def close(self):
                    results.append("closed")
            session._caller = DelayedCaller()
            def abandon():
                try:
                    results.append(session.request_abandon())
                except Exception as exc:
                    results.append(exc)
            def cleanup():
                try:
                    session.close()
                except Exception as exc:
                    results.append(exc)
            first = Thread(target=abandon if abandon_first else cleanup)
            second = Thread(target=cleanup if abandon_first else abandon)
            first.start()
            try:
                require(entered.wait(2), "initial shutdown was not reached")
                second.start()
                second.join(2)
                require(not second.is_alive(),
                        "second actor waited for a blocking socket shutdown")
                release.set()
                first.join(2)
                require(not first.is_alive(), "initial shutdown blocked after release")
                require(calls == [socket.SHUT_WR],
                        "cleanup repeated the abandonment IPC half-close")
                require(session._caller_write_half_close_attempted and session._caller is None,
                        "cleanup did not consume and detach the one-shot channel")
                if abandon_first:
                    require(session._abandon_requested.is_set(),
                            "cleanup lost already-consumed operator intent")
                    if unknown_shutdown:
                        require(any("uncertain" in str(value) for value in results),
                                "ambiguous abandonment was falsely certified")
            finally:
                release.set()
                first.join(2)
                if second.ident is not None:
                    second.join(2)


def test_abandon_preempts_unclaimed_ordinary_execution_request():
    """Expensive non-emitting request preparation must not escape terminal intent."""
    from threading import Event
    from unittest.mock import patch
    entered, release = Event(), Event()
    session = launcher.PhysicalQualificationSession(uri="radio://test", webots_executable="unused")
    caller = _RecordingCaller()
    session._caller = caller
    session._prepared = launcher.PreparedProgram("activity-1", canonical_static_ast(), "epoch-before")
    session._teacher_sealed = session._teacher_approved = True
    outcomes = []
    actual_count = launcher.execution_request_count
    def delayed_real_count(binding):
        entered.set()
        require(release.wait(2), "request preparation never released")
        return actual_count(binding)
    def execute():
        try:
            session.execute_approved_program(timeout_seconds=0.2)
            outcomes.append("executed")
        except Exception as exc:
            outcomes.append(exc)
    with patch.object(launcher, "execution_request_count", delayed_real_count):
        worker = Thread(target=execute)
        worker.start()
        try:
            require(entered.wait(2), "execution did not reach pre-commit window")
            require(session.request_abandon(), "abandonment before execution was not accepted")
            release.set()
            worker.join(2)
            require(not worker.is_alive(), "late execution waited on terminal IPC")
            require(len(outcomes) == 1 and isinstance(
                outcomes[0], launcher.PhysicalQualificationLauncherError
            ), "unclaimed ordinary execution committed after abandonment")
            require(not session._execution_attempted and not caller.messages,
                    "ordinary IPC was sent after abandonment intent")
        finally:
            release.set()
            worker.join(2)


def test_operator_console_is_armed_before_approval_and_never_waits_for_output():
    from io import StringIO
    from threading import Event
    # A real socket proves the console gesture reaches the existing EOF reader.
    from caller_lifetime import CallerLifetime
    for command in ("ABANDON\n", "", "ignored\nABANDON\n"):
        caller, host = socket.socketpair()
        reader = host.makefile("r", encoding="utf-8")
        lifetime = CallerLifetime(reader, max_message_bytes=8192)
        session = launcher.PhysicalQualificationSession(uri="radio://test", webots_executable="unused")
        session._caller = caller
        console = launcher._OperatorAbandonConsole(session, StringIO(command))
        try:
            console.start()
            console._thread.join(1)
            require(console._armed.is_set() and lifetime._closed.wait(1)
                    and session._abandon_requested.is_set(), "gesture/input loss failed to reach host")
            require(not session._teacher_decision_attempted and not session._execution_attempted,
                    "operator console minted approval or execution")
        finally:
            console.stop()
            caller.close()
            lifetime.stop()
            host.shutdown(socket.SHUT_RD)
            lifetime._thread.join(1)
            reader.close()
            host.close()
    entered, release = Event(), Event()
    class DelayedInput:
        def readline(self):
            entered.set()
            require(release.wait(2), "late test input was not released")
            return "ABANDON\n"
    session = launcher.PhysicalQualificationSession(uri="radio://test", webots_executable="unused")
    session._caller = _RecordingCaller()
    console = launcher._OperatorAbandonConsole(session, DelayedInput())
    console.start()
    require(entered.wait(1), "console reader did not start")
    console.stop()
    release.set()
    console._thread.join(1)
    require(not console._thread.is_alive() and not session._abandon_requested.is_set(),
            "stopped input console changed a settled run")


def test_actual_cli_arms_input_before_approval_and_signals_during_execution():
    from contextlib import redirect_stdout, redirect_stderr
    from io import StringIO
    from threading import Event
    from unittest.mock import patch
    entered, release, abandoned = Event(), Event(), Event()
    events = []
    class Input:
        def readline(self):
            entered.set()
            require(release.wait(2), "CLI test input not released")
            return "ABANDON\n"
    class Session:
        def __enter__(self): return self
        def __exit__(self, *_args): events.append("cleanup")
        def prepare(self):
            return (launcher.PreparedProgram("activity-1", canonical_dynamic_ast(), "epoch-before"),
                    {"connectionEpoch": "epoch-after"})
        def decide(self, _proposal, *, approved):
            require(approved and entered.wait(1), "CLI approved before live input was armed")
            events.append("approve")
        def execute_approved_program(self):
            events.append("execute")
            release.set()
            require(abandoned.wait(1), "blocking CLI execution hid voluntary input")
            raise launcher.PhysicalQualificationLauncherError("operator abandonment requested")
        def request_abandon(self):
            events.append("signal")
            abandoned.set()
            return True
    output = StringIO()
    with patch.object(launcher, "PhysicalQualificationSession", lambda **_kwargs: Session()), \
         patch("builtins.input", side_effect=["PREPARE", "APPROVE"]), \
         patch.object(launcher.sys, "stdin", Input()), \
         redirect_stdout(output), redirect_stderr(output):
        result = launcher.main(["--uri", "radio://test"])
    require(result == 1 and events == ["approve", "execute", "signal", "cleanup"],
            "CLI did not preserve approval/execution/signal/cleanup ordering")
    require("Programme physique exact terminé" not in output.getvalue(),
            "voluntary abandonment became successful qualification")



def test_two_close_calls_cannot_observe_a_detached_teacher_socket():
    """Production close() reproducer for the third independent NO_GO.

    Suspend the owner immediately before the actual teacher-socket close;
    another close must fail closed, not detach/close the same handle. Threads
    execute production methods on real socketpair without starting the host.
    """
    import inspect
    from threading import Event, current_thread
    teacher, peer = socket.socketpair()
    session = launcher.PhysicalQualificationSession(uri="radio://unused", webots_executable="unused")
    session._teacher = teacher
    sources, first_line = inspect.getsourcelines(launcher.PhysicalQualificationSession.close)
    candidates = [
        first_line + i for i, source in enumerate(sources)
        if "self._teacher.close()" in source or "teacher.close()" in source
    ]
    require(len(candidates) == 1, "production teacher cleanup instruction changed")
    paused, resume = Event(), Event()
    outcomes = []

    def trace_close(frame, event, _arg):
        if (current_thread().name == "close-owner" and event == "line"
                and frame.f_code is launcher.PhysicalQualificationSession.close.__code__
                and frame.f_lineno == candidates[0]):
            paused.set()
            require(resume.wait(3), "owner remained suspended")
        return trace_close

    def owner():
        sys.settrace(trace_close)
        try:
            session.close()
            outcomes.append("owner-complete")
        except BaseException as exc:
            outcomes.append(exc)
        finally:
            sys.settrace(None)

    worker = Thread(target=owner, name="close-owner", daemon=True)
    worker.start()
    try:
        require(paused.wait(3), "production close never reached teacher resource")
        try:
            session.close()
        except launcher.PhysicalQualificationLauncherError as exc:
            require("in progress" in str(exc),
                    "second close did not expose unresolved first cleanup")
        else:
            raise AssertionError("second close silently finished during first cleanup")
    finally:
        resume.set()
        worker.join(3)
        peer.close()
    require(not worker.is_alive() and outcomes == ["owner-complete"],
            "concurrent cleanup raised or failed to release single owner: " + repr(outcomes))
    require(teacher.fileno() == -1 and session._teacher is None,
            "teacher resource not closed by original owner")



def test_terminal_cleanup_is_one_owner_even_when_host_wait_blocks_or_fails():
    """Real socket EOF and deterministic resource/host races; no radio or Webots."""
    from threading import Event
    for host_exit, fail_bridge in ((0, False), (7, False), (0, True)):
        host_waiting, release_host = Event(), Event()
        events, results, second_results = [], [], []
        class Socket:
            def __init__(self, raw, name):
                self.raw, self.name, self.closes, self.shutdowns = raw, name, 0, 0
            def shutdown(self, how):
                self.shutdowns += 1
                require(how == socket.SHUT_WR, "not an ordinary caller half-close")
                self.raw.shutdown(how)
            def close(self):
                self.closes += 1
                events.append(self.name + "-close")
                self.raw.close()
        class Host:
            def __init__(self):
                self.waits = 0
            def wait(self, timeout):
                self.waits += 1
                events.append("host-wait")
                require(timeout == 10, "unexpected second/extended host wait")
                host_waiting.set()
                require(release_host.wait(3), "host wait was never released")
                return host_exit
            def terminate(self): raise AssertionError("possibly authorized host terminated")
            def kill(self): raise AssertionError("possibly authorized host killed")
        class Webots:
            def __init__(self): self.terminations = self.waits = 0
            def poll(self): return None
            def terminate(self):
                self.terminations += 1
                events.append("webots-terminate")
            def wait(self, timeout):
                self.waits += 1
                require(timeout == 5, "unexpected Webots wait")
                return 0
            def kill(self): raise AssertionError("Webots killed despite confirmed termination")
        class Asset:
            def __init__(self, name): self.name, self.closes = name, 0
            def close(self):
                self.closes += 1
                events.append(self.name + "-close")
                if self.name == "bridge" and fail_bridge:
                    raise OSError("synthetic unknown bridge close")
        caller_raw, caller_peer = socket.socketpair()
        teacher_raw, teacher_peer = socket.socketpair()
        caller_peer.settimeout(2.0)  # absent EOF must fail, never hang the CI job
        session = launcher.PhysicalQualificationSession(uri="radio://unused", webots_executable="unused")
        caller, teacher = Socket(caller_raw, "caller"), Socket(teacher_raw, "teacher")
        host, webots, bridge, ephemeral = Host(), Webots(), Asset("bridge"), Asset("ephemeral")
        session._caller, session._teacher = caller, teacher
        session._host, session._webots = host, webots
        session._bridge, session._ephemeral = bridge, ephemeral
        session._teacher_decision_attempted = True  # conservatively possibly authorized

        def first_close():
            try:
                session.close()
                results.append("closed")
            except BaseException as exc:
                results.append(exc)
        def second_close():
            try:
                session.close()
                second_results.append("closed")
            except BaseException as exc:
                second_results.append(exc)
        owner = Thread(target=first_close, daemon=True)
        contender = Thread(target=second_close, daemon=True)
        owner.start()
        try:
            require(host_waiting.wait(2), "real production close did not reach host wait")
            require(caller_peer.recv(1) == b"", "ordinary real-socket EOF was not delivered")
            contender.start()
            contender.join(1)
            require(not contender.is_alive() and len(second_results) == 1
                    and isinstance(second_results[0], launcher.PhysicalQualificationLauncherError)
                    and "in progress" in str(second_results[0]),
                    "concurrent close masked or waited for unresolved host teardown")
            require(session.request_abandon() is True and session._abandon_requested.is_set(),
                    "terminal operator intent was lost behind host wait / caller detachment")
            require(caller.shutdowns == 1 and caller.closes == 1 and teacher.closes == 1,
                    "blocked host wait led to repeated or incomplete socket cleanup")
            require(webots.terminations == 0 and bridge.closes == 0 and ephemeral.closes == 0,
                    "dependent resources were destroyed before host outcome")
        finally:
            release_host.set()
            owner.join(3)
            contender.join(3)
            caller_peer.close()
            teacher_peer.close()
        require(not owner.is_alive() and host.waits == 1 and webots.terminations == 1
                and webots.waits == 1 and bridge.closes == 1 and ephemeral.closes == 1,
                "terminal owner did not finalize independent resources exactly once")
        if host_exit or fail_bridge:
            require(len(results) == 1 and isinstance(results[0], launcher.PhysicalQualificationLauncherError),
                    "host/bridge failure disappeared from original owner")
            cause = results[0]
            try:
                session.close()
            except launcher.PhysicalQualificationLauncherError as exc:
                require("previously failed" in str(exc) and exc.__cause__ is cause,
                        "later close lost exact causal exception")
            else:
                raise AssertionError("failed close was silently converted to success")
            if fail_bridge:
                require(session._bridge is bridge and session._ephemeral is None,
                        "uncertain bridge discarded or independent ephemeral skipped")
        else:
            require(results == ["closed"], "clean first close failed")
            session.close()  # completed idempotence cannot repeat an effect
        require(host.waits == 1 and caller.shutdowns == 1 and caller.closes == 1
                and teacher.closes == 1 and bridge.closes == 1 and ephemeral.closes == 1,
                "later close retried an effect with known or unknown prior outcome")


def test_close_vetoes_new_decision_and_execution_without_extra_ordinary_ipc():
    from unittest.mock import patch
    session = launcher.PhysicalQualificationSession(uri="radio://unused", webots_executable="unused")
    caller, caller_peer = socket.socketpair()
    teacher, teacher_peer = socket.socketpair()
    caller_peer.settimeout(2.0)
    teacher_peer.settimeout(2.0)
    session._caller, session._teacher = caller, teacher
    session._prepared = launcher.PreparedProgram("activity-1", canonical_static_ast(), "epoch-before")
    proposal = {
        "op": "teacher-run-binding-proposal",
        "requestId": "teacher-1", "challengeId": "challenge-1", "profileId": "activity-1",
        "astBinding": canonical_static_ast(), "connectionEpoch": "epoch-after",
        "executionAuthority": False,
    }
    try:
        session.close()  # closing claim precedes teacher/execution commitment
        for attempt in (lambda: session.decide(proposal, approved=True),
                        lambda: session.execute_approved_program(timeout_seconds=0.2)):
            try:
                attempt()
            except launcher.PhysicalQualificationLauncherError:
                pass
            else:
                raise AssertionError("new irreversible authority escaped terminal cleanup")
        require(not session._teacher_decision_attempted and not session._execution_attempted,
                "closing state failed to prevent new program/teacher claims")
        require(caller_peer.recv(1) == b"" and teacher_peer.recv(1) == b"",
                "closed session sent unexpected authority or ordinary messages")
    finally:
        caller_peer.close()
        teacher_peer.close()



def test_close_after_committed_decision_preserves_uncertainty_and_host():
    """Close cannot undo a decision already committed before its short lock."""
    from threading import Event
    entered, release = Event(), Event()
    events = []
    class PendingHost:
        def wait(self, timeout):
            events.append(("host-wait", timeout))
            raise launcher.subprocess.TimeoutExpired("host", timeout)
        def terminate(self): raise AssertionError("in-flight approval led to host termination")
        def kill(self): raise AssertionError("in-flight approval led to host kill")
    class DelayedTeacher:
        def __init__(self, raw):
            self.raw, self.sends, self.closes = raw, 0, 0
        def sendall(self, payload):
            self.sends += 1
            entered.set()
            require(release.wait(3), "decision send not released")
            self.raw.sendall(payload)
        def shutdown(self, how): self.raw.shutdown(how)
        def close(self):
            self.closes += 1
            self.raw.close()
    session = launcher.PhysicalQualificationSession(uri="radio://unused", webots_executable="unused")
    raw, peer = socket.socketpair()
    teacher = DelayedTeacher(raw)
    session._teacher = teacher
    session._host = PendingHost()
    session._prepared = launcher.PreparedProgram("activity-1", canonical_static_ast(), "epoch-before")
    proposal = {
        "op": "teacher-run-binding-proposal",
        "requestId": "teacher-1", "challengeId": "challenge-1", "profileId": "activity-1",
        "astBinding": canonical_static_ast(), "connectionEpoch": "epoch-after",
        "executionAuthority": False,
    }
    decision_outcome = []
    def decide():
        try: session.decide(proposal, approved=True)
        except BaseException as exc: decision_outcome.append(exc)
        else: decision_outcome.append("sent")
    worker = Thread(target=decide, daemon=True)
    worker.start()
    try:
        require(entered.wait(2) and session._teacher_decision_attempted,
                "decision was not irrevocably committed before close")
        try:
            session.close()
        except launcher.PhysicalQualificationLauncherError as exc:
            require("host left alive" in str(exc), "unknown host recovery falsely settled")
        else:
            raise AssertionError("possibly authorized host was reaped during in-flight decision")
    finally:
        release.set()
        worker.join(3)
        peer.close()
    require(not worker.is_alive() and teacher.sends == 1 and teacher.closes == 1
            and events == [("host-wait", 10.0)]
            and len(decision_outcome) == 1 and not session._teacher_approved,
            "concurrent close minted authority, resent or killed the host")
    try:
        session.close()
    except launcher.PhysicalQualificationLauncherError as exc:
        require("previously failed" in str(exc), "uncertain host got another close attempt")
    else:
        raise AssertionError("unknown host wait became confirmed")


def test_close_during_committed_execution_does_not_retry_ipc():
    from threading import Event
    entered, release = Event(), Event()
    class DelayedCaller:
        def __init__(self, raw):
            self.raw, self.sends, self.shutdowns, self.closes = raw, 0, 0, 0
        def sendall(self, data):
            self.sends += 1
            entered.set()
            require(release.wait(3), "execution send not released")
            self.raw.sendall(data)
        def shutdown(self, how):
            self.shutdowns += 1
            self.raw.shutdown(how)
        def close(self):
            self.closes += 1
            self.raw.close()
    session = launcher.PhysicalQualificationSession(uri="radio://unused", webots_executable="unused")
    raw, peer = socket.socketpair()
    peer.settimeout(2.0)  # unknown EOF is a failed oracle, not unbounded wait
    caller = DelayedCaller(raw)
    session._caller = caller
    session._prepared = launcher.PreparedProgram("activity-1", canonical_static_ast(), "epoch-before")
    session._teacher_sealed = session._teacher_approved = True
    session._teacher_decision_attempted = True
    outcome = []
    def execute():
        try: session.execute_approved_program(timeout_seconds=0.2)
        except BaseException as exc: outcome.append(exc)
        else: outcome.append("executed")
    worker = Thread(target=execute, daemon=True)
    worker.start()
    try:
        require(entered.wait(2) and session._execution_attempted,
                "execution IPC had not committed before close")
        session.close()
        require(peer.recv(1) == b"", "ordinary caller EOF did not reach host socket")
        require(caller.shutdowns == 1 and caller.closes == 1,
                "close failed to use sole caller shutdown/close attempt")
    finally:
        release.set()
        worker.join(3)
        peer.close()
    require(not worker.is_alive() and len(outcome) == 1
            and isinstance(outcome[0], launcher.PhysicalQualificationLauncherError)
            and caller.sends == 1 and not session._execution_completed,
            "committed request outcome was hidden, replayed or certified as normal")
    session.close()
    require(caller.sends == 1 and caller.shutdowns == 1 and caller.closes == 1,
            "completed teardown retried ordinary IPC")


def test_failed_normal_half_close_retains_causal_error_without_retry():
    class UnknownCaller:
        def __init__(self):
            self.shutdowns = self.closes = 0
        def shutdown(self, how):
            require(how == socket.SHUT_WR, "unexpected half-close direction")
            self.shutdowns += 1
            raise OSError("unknown kernel shutdown result")
        def close(self):
            self.closes += 1
    session = launcher.PhysicalQualificationSession(uri="radio://unused", webots_executable="unused")
    caller = UnknownCaller()
    session._caller = caller
    try:
        session.close()
    except launcher.PhysicalQualificationLauncherError as exc:
        require("half-close outcome is uncertain" in str(exc)
                and isinstance(exc.__cause__, OSError),
                "failed normal cleanup masked uncertain first shutdown")
        original = exc
    else:
        raise AssertionError("failed caller shutdown falsely certified cleanup")
    try:
        session.close()
    except launcher.PhysicalQualificationLauncherError as exc:
        require("previously failed" in str(exc) and exc.__cause__ is original,
                "second cleanup lost causal error")
    else:
        raise AssertionError("unknown SHUT_WR outcome was hidden by second cleanup")
    require(caller.shutdowns == 1 and caller.closes == 1,
            "unknown half-close led to a second shutdown or socket cleanup")



def test_failed_startup_cause_survives_failed_one_shot_teardown():
    session = launcher.PhysicalQualificationSession(uri="radio://unused", webots_executable="unused")
    original = launcher.PhysicalQualificationLauncherError("original startup evidence")
    class FailingCleanupCaller:
        def shutdown(self, _how):
            raise OSError("unknown caller shutdown")
        def close(self): pass
    def broken_spawn():
        session._caller = FailingCleanupCaller()
        raise original
    session._spawn_host = broken_spawn
    try:
        session.start()
    except launcher.PhysicalQualificationLauncherError as exc:
        require(exc.__cause__ is original and "original startup evidence" in str(exc)
                and "terminal teardown also failed" in str(exc),
                "startup root cause was replaced by uncertain cleanup")
    else:
        raise AssertionError("startup failure/cleanup failure falsely passed")
    require(session._terminal_cleanup_state == "failed", "teardown uncertainty not retained")



def test_one_shot_teardown_prevents_restarting_and_leaking_new_resources():
    from unittest.mock import patch
    session = launcher.PhysicalQualificationSession(uri="radio://unused", webots_executable="unused")
    session.close()
    require(session._terminal_cleanup_state == "complete", "empty session did not finish cleanup")
    with patch.object(session, "_spawn_host", side_effect=AssertionError("restarted a closed host")):
        try:
            session.start()
        except launcher.PhysicalQualificationLauncherError as exc:
            require("closing" in str(exc) or "cannot restart" in str(exc),
                    "restarting a cleaned-up session did not fail closed")
        else:
            raise AssertionError("post-close start reacquired resources that cannot be cleaned")
    session.close()
    require(session._host is None and session._caller is None and session._teacher is None,
            "one-shot session acquired post-cleanup resources")


def main() -> int:
    test_one_shot_teardown_prevents_restarting_and_leaking_new_resources()
    test_failed_startup_cause_survives_failed_one_shot_teardown()
    test_close_after_committed_decision_preserves_uncertainty_and_host()
    test_close_during_committed_execution_does_not_retry_ipc()
    test_failed_normal_half_close_retains_causal_error_without_retry()
    test_terminal_cleanup_is_one_owner_even_when_host_wait_blocks_or_fails()
    test_close_vetoes_new_decision_and_execution_without_extra_ordinary_ipc()
    test_two_close_calls_cannot_observe_a_detached_teacher_socket()
    test_actual_cli_arms_input_before_approval_and_signals_during_execution()
    test_abandon_preempts_unclaimed_positive_decision_on_real_host_channels()
    test_abandon_and_cleanup_share_one_half_close_claim()
    test_abandon_preempts_unclaimed_ordinary_execution_request()
    test_voluntary_abandon_is_one_shot_during_blocking_static_and_dynamic_request()
    test_abandon_does_not_wait_for_send_and_unknown_signal_is_never_retried()
    test_abandon_before_approval_and_after_completion_preserves_authority()
    test_operator_console_is_armed_before_approval_and_never_waits_for_output()
    print("PASS voluntary operator abandonment: static/dynamic blocked replies, concurrent gestures, "
          "positive completion races, blocked/partial writes, unknown signal, pre-approval/late input")
    test_failed_host_exit_cleans_resources_and_never_reports_success()
    test_wait_deadline_admission_precedes_all_host_and_teacher_exchange()
    test_teardown_failure_preserves_original_execution_diagnostic()
    test_execution_write_is_one_shot_even_when_delivery_is_ambiguous()
    test_socket_deadline_is_total_and_finite()
    test_teardown_never_kills_a_possibly_authorized_host()
    test_caller_loss_is_observed_during_a_blocking_operation()
    test_preparation_bridge_is_authenticated_one_shot_non_authority()
    test_ephemeral_robot_window_injects_only_non_authority_bootstrap()
    test_browser_helper_has_no_teacher_or_execution_channel()
    test_execution_request_count_uses_static_dynamic_host_boundary()
    test_startup_failure_cleans_resources_acquired_before_bootstrap_failure()
    test_teacher_decision_send_is_irrevocable_before_fallible_half_close()
    test_failed_teacher_decision_write_is_terminal_and_not_retriable()
    test_denied_teacher_decision_never_enables_execution()
    test_full_launcher_composes_real_window_distinct_teacher_and_parameter_free_execution()
    test_host_failure_evidence_reaches_terminal_without_next_command()
    print(
        "PASS physical qualification launcher: real Robot Window bootstrap, distinct teacher channel, "
        "exact host binding, lifecycle fail-closed boundaries and parameter-free full-program execution"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
