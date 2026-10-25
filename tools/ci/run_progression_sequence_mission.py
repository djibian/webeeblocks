#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
NEUTRAL_START = os.environ.get('WEBEEBLOCKS_CI_NEUTRAL_START') == '1'
ARTIFACT_ROOT = ROOT / "ci-artifacts" / ("progression-neutral-start" if NEUTRAL_START else "progression-sequence-mission")
WEBOTS_IMAGE = "cyberbotics/webots@sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099"
TEMP_WORLD = ROOT / "worlds" / "ci_progression_sequence.wbt"
TEMP_PROJECT = ROOT / "worlds" / ".ci_progression_sequence.wbproj"


def instrument_position(source: str) -> str:
    """Observe GPS versus Supervisor coordinates without changing flight rules."""
    if 'sequence_ci_position' in source:
        raise ValueError('sequence position instrumentation already present')
    helper = r'''
#include <sys/time.h>

static long long sequence_ci_wall_ms(void) {
  struct timeval tv;
  if (gettimeofday(&tv, NULL) != 0)
    return -1;
  return (long long)tv.tv_sec * 1000 + tv.tv_usec / 1000;
}

static void sequence_ci_position(const char *phase, int request_id,
                                 WbNodeRef self, WbDeviceTag gps,
                                 WbFieldRef translation) {
  const double *value = wb_gps_get_values(gps);
  const double gps_copy[3] = {value[0], value[1], value[2]};
  value = wb_supervisor_node_get_position(self);
  const double world_copy[3] = {value[0], value[1], value[2]};
  value = wb_supervisor_field_get_sf_vec3f(translation);
  printf("WEBEEBLOCKS_SEQUENCE_CI_POSITION phase=%s request=%d time=%.9f node=%d gps=%.9f,%.9f,%.9f world=%.9f,%.9f,%.9f translation=%.9f,%.9f,%.9f\n",
         phase, request_id, wb_robot_get_time(), wb_supervisor_node_get_id(self),
         gps_copy[0], gps_copy[1], gps_copy[2],
         world_copy[0], world_copy[1], world_copy[2], value[0], value[1], value[2]);
  fflush(stdout);
}


static void sequence_ci_native_land(int request_id, double now, WbNodeRef self) {
  // Read-only Supervisor observations: contact locations are not contact forces.
  // Keep the on-line volume bounded; a partial array is explicitly labelled.
  const double *observed_velocity = wb_supervisor_node_get_velocity(self);
  double velocity[6] = {NAN, NAN, NAN, NAN, NAN, NAN};
  // Webots may reuse API-owned memory; snapshot velocity before reading contacts.
  if (observed_velocity != NULL)
    for (int i = 0; i < 6; ++i)
      velocity[i] = observed_velocity[i];
  int contact_count = -1;
  WbContactPoint *points = wb_supervisor_node_get_contact_points(self, true, &contact_count);
  const int shown = contact_count < 6 ? contact_count : 6;
  int valid = observed_velocity != NULL && contact_count >= 0 &&
              (contact_count == 0 || points != NULL);
  if (valid) {
    for (int i = 0; i < 6; ++i)
      if (!isfinite(velocity[i]))
        valid = 0;
    for (int i = 0; i < shown; ++i)
      for (int axis = 0; axis < 3; ++axis)
        if (!isfinite(points[i].point[axis]))
          valid = 0;
  }
  printf("WEBEEBLOCKS_SEQUENCE_CI_LAND_NATIVE id=%d t=%.9f status=%s contacts=%d shown=%d",
         request_id, now, valid ? "OBSERVED" : "UNPROVEN", contact_count, shown);
  if (valid) {
    printf(" velocity=%.9f,%.9f,%.9f,%.9f,%.9f,%.9f",
           velocity[0], velocity[1], velocity[2],
           velocity[3], velocity[4], velocity[5]);
    for (int i = 0; i < shown; ++i)
      printf(" cp%d=%d:%.9f,%.9f,%.9f", i, points[i].node_id,
             points[i].point[0], points[i].point[1], points[i].point[2]);
  }
  printf("\n");
  fflush(stdout);
}

'''
    edits = (
        ('int main(void) {', helper + 'int main(void) {'),
        ('  send_text(PREFIX " READY");',
         '  printf("WEBEEBLOCKS_SEQUENCE_CI_STARTUP legacy=%d evaluators=%d sequence=%d\\n",\n'
         '         wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_SCENE") != 0,\n'
         '         wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_EVALUATORS") != 0,\n'
         '         wb_supervisor_node_get_from_def("WEBEEBLOCKS_SEQUENCE_SCENE") != 0);\n'
         '  sequence_ci_position("ready", -1, self_node, gps, translation_field);\n'
         '  send_text(PREFIX " READY");'),
        ('      request_t request = parse_request(message);',
         '      request_t request = parse_request(message);\n'
         '      sequence_ci_position(message, request.id, self_node, gps, translation_field);'),
        ('          if (request.scene_nonce[0]) {',
         '          sequence_ci_position("scene-selected", request.id, self_node, gps, translation_field);\n'
         '          if (request.scene_nonce[0]) {'),
        # CI-only observations of the unchanged LAND controller, sampled at
        # 128 ms in free descent and every 8 ms near the ground. These are
        # *commanded* motor values, not measured thrust or contact forces.
        ('  double reset_max_stable = 0.0;',
         '  double reset_max_stable = 0.0;\n'
         '  unsigned long sequence_ci_land_samples = 0;\n'
         '  unsigned long sequence_ci_move_samples = 0;'),
        # CI-only paired clocks for the already-active MOVE: never change
        # simulated deadlines, student behavior, response codes or oracles.
        ('        command = CMD_MOVE;\n        stable_since = -1.0;',
         '        command = CMD_MOVE;\n'
         '        sequence_ci_move_samples = 0;\n'
         '        stable_since = -1.0;'),
        ('    if (command != CMD_IDLE && command != CMD_RESET &&',
         '    if (command == CMD_MOVE && sequence_ci_move_samples++ % 128 == 0) {\n'
         '      printf("WEBEEBLOCKS_SEQUENCE_CI_MOVE id=%d sim=%.9f elapsed_sim=%.9f wall_ms=%lld x=%.9f y=%.9f z=%.9f roll=%.9f pitch=%.9f\\n",\n'
         '             active_id, now, now - action_start, sequence_ci_wall_ms(), x, y, z,\n'
         '             actual.roll, actual.pitch);\n'
         '      fflush(stdout);\n'
         '    }\n'
         '    if (command != CMD_IDLE && command != CMD_RESET &&'),
        # The first sample belongs to this LAND request, including after RESET.
        # Without a reset, later LAND attempts can miss their initial 128 ms window.
        ('        command = CMD_LAND;\n        stable_since = -1.0;',
         '        command = CMD_LAND;\n'
         '        sequence_ci_land_samples = 0;\n'
         '        stable_since = -1.0;'),
        ('      wb_motor_set_velocity(m4, motor_power(power.m4));',
         '      wb_motor_set_velocity(m4, motor_power(power.m4));\n'
         '      if (command == CMD_LAND &&\n'
         '          (z <= origin_z + 0.15 || sequence_ci_land_samples % 16 == 0)) {\n'
         '        printf("WEBEEBLOCKS_SEQUENCE_CI_LAND id=%d t=%.9f x=%.9f y=%.9f z=%.9f vx=%.9f vy=%.9f vz=%.9f roll=%.9f pitch=%.9f des_vx=%.9f des_vy=%.9f des_z=%.9f motor1=%.9f motor2=%.9f motor3=%.9f motor4=%.9f\\n",\n'
         '               active_id, now, x, y, z, vx_global, vy_global, vz,\n'
         '               actual.roll, actual.pitch, desired.vx, desired.vy,\n'
         '               desired.altitude, -motor_power(power.m1),\n'
         '               motor_power(power.m2), -motor_power(power.m3),\n'
         '               motor_power(power.m4));\n'
         '        fflush(stdout);\n'
         '        sequence_ci_native_land(active_id, now, self_node);\n'
         '      }\n'
         '      if (command == CMD_LAND)\n'
         '        ++sequence_ci_land_samples;'),
        ('          trace_land();',
         '          sequence_ci_position("land-stop", active_id, self_node, gps, translation_field);\n'
         '          trace_land();'),
    )
    for before, after in edits:
        if source.count(before) != 1:
            raise ValueError('ambiguous sequence position instrumentation: ' + before)
        source = source.replace(before, after, 1)
    return source


def run(command: list[str], *, cwd: Path = ROOT, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        check=False,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )


def fail(message: str, detail: str | None = None) -> int:
    print(f"FAIL progression mission evidence: {message}", file=sys.stderr)
    if detail:
        print(detail, file=sys.stderr)
    return 1


def cleanup_temp_world() -> None:
    for path in (TEMP_WORLD, TEMP_PROJECT):
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def main() -> int:
    if shutil.which("docker") is None:
        return fail("docker is unavailable")
    cleanup_temp_world()
    shutil.rmtree(ARTIFACT_ROOT, ignore_errors=True)
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)

    checks = [
        ["python3", "tools/ci/test_progression_land_instrumentation.py"],
        ["python3", "tools/ci/test_land_contact_summary.py"],
        ["node", "tools/ci/test_progression_sequence_contract.js"],
        ["node", "--check", "plugins/robot_windows/sequence_probe/sequence_probe.js"],
    ]
    for command in checks:
        result = run(command, capture=True)
        if result.returncode:
            return fail("progression mission source validation failed", result.stdout)

    world_name = 'crazyflie_classroom_start.wbt' if NEUTRAL_START else 'crazyflie_runtime_v2.wbt'
    source_world = (ROOT / "worlds" / world_name).read_text(encoding="utf-8")
    if source_world.count('window "blockly_v2"') != 1:
        return fail("Runtime v2 world Robot Window identity is ambiguous")
    markers = (
        "WEBEEBLOCKS_SEQUENCE_MISSION_V1_BEGIN",
        "WEBEEBLOCKS_PRECISE_MOVEMENT_MISSION_V1_BEGIN",
        'name "Crazyflie WebeeBlocks"',
        'name "Progression sequence evaluator"',
        '"sequence-evaluator-v1"',
        'name "Progression precise movement evaluator"',
        '"precise-evaluator-v1"',
    ) if not NEUTRAL_START else (
        'DEF WEBEEBLOCKS_CLASSROOM_START_WORLD WorldInfo {',
        'name "Crazyflie WebeeBlocks"', 'name "Progression sequence evaluator"',
        '"sequence-evaluator-v1"',
    )
    for marker in markers:
        if marker not in source_world:
            return fail(f"missing progression world marker: {marker}")
    probe = 'sequence_neutral_probe' if NEUTRAL_START else 'sequence_probe'
    TEMP_WORLD.write_text(source_world.replace('window "blockly_v2"', f'window "{probe}"', 1), encoding="utf-8")
    TEMP_PROJECT.write_text(
        "Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n",
        encoding="utf-8",
    )

    try:
        pull = run(["docker", "pull", WEBOTS_IMAGE], capture=True)
        if pull.returncode:
            return fail("pinned Webots image could not be prepared", pull.stdout)

        controller = ROOT / "controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c"
        original = controller.read_bytes()
        diagnostic = instrument_position(original.decode("utf-8")).encode("utf-8")
        (ARTIFACT_ROOT / "runtime-original.c").write_bytes(original)
        (ARTIFACT_ROOT / "runtime-instrumented.c").write_bytes(diagnostic)
        (ARTIFACT_ROOT / "runtime-source-sha256.json").write_text(json.dumps({
            "original": hashlib.sha256(original).hexdigest(),
            "instrumented": hashlib.sha256(diagnostic).hexdigest(),
        }, indent=2) + "\n", encoding="utf-8")
        try:
            controller.write_bytes(diagnostic)
            built = run([
                "docker", "run", "--rm",
                "-v", f"{ROOT}:/workspace",
                "-w", "/workspace/controllers/crazyflie_runtime_v2",
                WEBOTS_IMAGE,
                "bash", "-lc", "make clean && make",
            ], capture=True)
        finally:
            controller.write_bytes(original)
        (ARTIFACT_ROOT / "build.log").write_text(built.stdout or "", encoding="utf-8")
        if built.returncode:
            return fail("Runtime v2/progression evaluators build failed", (built.stdout or "")[-6000:])

        inner = r'''
set -e
apt-get update >/dev/null
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends wget ca-certificates >/dev/null
wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
DEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/google-chrome.deb >/dev/null
chmod +x /workspace/tools/ci/webots_runtime_v2_browser.sh
mkdir -p /workspace/ci-artifacts/progression-sequence-mission /root/.config/Cyberbotics
printf "%s\n" \
  "[RobotWindow]" \
  "browser=/workspace/tools/ci/webots_runtime_v2_browser.sh" \
  "newBrowserWindow=false" \
  > /root/.config/Cyberbotics/Webots-R2025a.conf
python3 /workspace/tools/ci/runtime_wwi_event_server.py \
  --output /workspace/ci-artifacts/progression-sequence-mission/browser-events.jsonl &
server=$!
trap "kill $server 2>/dev/null || true" EXIT
sleep 0.5
timeout -k 5s 260s xvfb-run -a webots --stdout --stderr --batch --mode=realtime /workspace/worlds/ci_progression_sequence.wbt
'''.strip()
        inner = inner.replace('progression-sequence-mission', ARTIFACT_ROOT.name)

        env = os.environ.copy()
        run_result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-e", "LIBGL_ALWAYS_SOFTWARE=true",
                "-e", "WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE=true",
                "-e", f"WEBEEBLOCKS_CI_ARTIFACT_DIR=/workspace/ci-artifacts/{ARTIFACT_ROOT.name}",
                "-v", f"{ROOT}:/workspace",
                "-w", "/workspace",
                WEBOTS_IMAGE,
                "bash", "-lc", inner,
            ],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        webots_log = run_result.stdout or ""
        (ARTIFACT_ROOT / "webots.log").write_text(webots_log, encoding="utf-8")
        (ARTIFACT_ROOT / "exit-code.txt").write_text(str(run_result.returncode) + "\n", encoding="utf-8")
        if run_result.returncode not in (0, 124):
            return fail(f"Webots progression mission exited with {run_result.returncode}", webots_log[-14000:])
        if NEUTRAL_START and webots_log.count('WEBEEBLOCKS_SEQUENCE_CI_STARTUP legacy=0 evaluators=0 sequence=0') != 1:
            return fail('neutral launch did not prove absence of preloaded native scenarios', webots_log[-14000:])

        event_path = ARTIFACT_ROOT / "browser-events.jsonl"
        if not event_path.exists() or event_path.stat().st_size == 0:
            return fail("missing browser progression evidence", webots_log[-14000:])
        try:
            events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except Exception as exc:
            return fail(f"invalid browser progression evidence: {exc}")

        errors = [event for event in events if event.get("event") in ("ERROR", "WINDOW_ERROR", "UNHANDLED_REJECTION")]
        if errors:
            detail = json.dumps(errors[0], ensure_ascii=False) + "\n--- Webots tail ---\n" + webots_log[-14000:]
            return fail("browser progression probe reported an error", detail)
        names = [event.get("event") for event in events]
        required = (
            "SEQUENCE_PROBE_READY",
            "SEQUENCE_SCENE_ISOLATED",
            "LEGACY_SCENE_RESTORED",
            "LEGACY_SCENE_REATTACHED",
            "SEQUENCE_SCENE_REATTACHED",
            "SEQUENCE_REATTACHED_RANGE",
            "SEQUENCE_ACHIEVED",
            "SEQUENCE_RESET_FRESH",
            "SEQUENCE_REPEAT_ACHIEVED",
            "SEQUENCE_REPEAT_RESET_FRESH",
            "SEQUENCE_NOT_ACHIEVED",
            "SEQUENCE_SECOND_RESET_FRESH",
            "SEQUENCE_ALTERNATIVE_ACHIEVED",
            "SEQUENCE_MISSION_TEST_COMPLETE",
            "ELAPSED_TIME_WEBOTS",
            "PRECISE_INITIAL_RESET_FRESH",
            "PRECISE_ACHIEVED",
            "PRECISE_RESET_FRESH",
            "PRECISE_UNDERSHOOT_NOT_ACHIEVED",
            "PRECISE_UNDERSHOOT_RESET_FRESH",
            "PRECISE_OVERSHOOT_NOT_ACHIEVED",
            "PRECISE_OVERSHOOT_RESET_FRESH",
            "PRECISE_LATERAL_NOT_ACHIEVED",
            "PRECISE_LATERAL_RESET_FRESH",
            "PRECISE_COLLISION_NOT_ACHIEVED",
            "PRECISE_COLLISION_RESET_FRESH",
            "PRECISE_ALTERNATIVE_ACHIEVED",
            "PRECISE_MISSION_TEST_COMPLETE",
        )
        missing = [name for name in required if name not in names]
        if missing:
            return fail(f"missing causal progression events: {missing}", json.dumps(names))

        details = {name: next(event["detail"] for event in events if event.get("event") == name) for name in required}
        if NEUTRAL_START:
            refusals = [event for event in events if event.get('event') == 'NEUTRAL_TAKEOFF_REFUSED']
            if len(refusals) != 1 or refusals[0]['detail'] != {'code':'SCENE_UNAVAILABLE'}:
                return fail('missing exact native TAKEOFF refusal before scene preparation')
            if names.index('NEUTRAL_TAKEOFF_REFUSED') > names.index('SEQUENCE_SCENE_ISOLATED'):
                return fail('neutral TAKEOFF refusal did not precede scene selection')
        if details['SEQUENCE_SCENE_ISOLATED'] != {'scene':'sequence-v1'} or details['LEGACY_SCENE_RESTORED'] != {'scene':'legacy-v1'}:
            return fail('missing physical scene switch evidence')
        for event, scene in (("LEGACY_SCENE_REATTACHED", "legacy-v1"), ("SEQUENCE_SCENE_REATTACHED", "sequence-v1")):
            if details[event] != {"scene": scene, "requests": 1}:
                return fail(f"missing native reattachment acknowledgement: {event}")
        if abs(details["SEQUENCE_REATTACHED_RANGE"].get("front", -1) - 2.0) > 0.01:
            return fail("reattached Activity 1 did not restore isolated sensing")
        for name in ("SEQUENCE_ACHIEVED", "SEQUENCE_REPEAT_ACHIEVED", "SEQUENCE_ALTERNATIVE_ACHIEVED",
                     "PRECISE_ACHIEVED", "PRECISE_ALTERNATIVE_ACHIEVED"):
            if details[name] != {"status": "achieved"}:
                return fail(f"unexpected achieved event {name}: {details[name]}")
        for name in ("SEQUENCE_NOT_ACHIEVED", "PRECISE_UNDERSHOOT_NOT_ACHIEVED",
                     "PRECISE_OVERSHOOT_NOT_ACHIEVED", "PRECISE_LATERAL_NOT_ACHIEVED"):
            if details[name] != {"status": "not-achieved"}:
                return fail(f"unexpected negative event {name}: {details[name]}")
        if details["PRECISE_COLLISION_NOT_ACHIEVED"] != {
            "status":"not-achieved", "runtime_code":"UNSAFE_OR_TIMEOUT", "completion_preserved":True
        }:
            return fail(f"unexpected collision event: {details['PRECISE_COLLISION_NOT_ACHIEVED']}")
        for name in ("SEQUENCE_RESET_FRESH", "SEQUENCE_REPEAT_RESET_FRESH", "SEQUENCE_SECOND_RESET_FRESH",
                     "PRECISE_INITIAL_RESET_FRESH", "PRECISE_RESET_FRESH", "PRECISE_UNDERSHOOT_RESET_FRESH",
                     "PRECISE_OVERSHOOT_RESET_FRESH", "PRECISE_LATERAL_RESET_FRESH", "PRECISE_COLLISION_RESET_FRESH"):
            if details[name] != {"code": "OUTCOME_UNAVAILABLE"}:
                return fail(f"outcome survived reset at {name}: {details[name]}")
        if details["SEQUENCE_MISSION_TEST_COMPLETE"] != {
            "canonical": "achieved", "repeat": "achieved", "negative": "not-achieved", "alternative": "achieved"
        }:
            return fail(f"unexpected sequence mission summary: {details['SEQUENCE_MISSION_TEST_COMPLETE']}")
        if details["PRECISE_MISSION_TEST_COMPLETE"] != {
            "canonical": "achieved", "undershoot": "not-achieved", "overshoot": "not-achieved",
            "lateral": "not-achieved", "collision": "not-achieved", "alternative": "achieved"
        }:
            return fail(f"unexpected precise mission summary: {details['PRECISE_MISSION_TEST_COMPLETE']}")

        for marker in (
            "WEBEEBLOCKS_SEQUENCE_RESULT attempt=1 status=achieved",
            "WEBEEBLOCKS_SEQUENCE_RESULT attempt=2 status=achieved",
            "WEBEEBLOCKS_SEQUENCE_RESULT attempt=3 status=not-achieved",
            "WEBEEBLOCKS_SEQUENCE_RESULT attempt=4 status=achieved",
            "WEBEEBLOCKS_PRECISE_RESULT attempt=5 status=achieved",
            "WEBEEBLOCKS_PRECISE_RESULT attempt=6 status=not-achieved",
            "WEBEEBLOCKS_PRECISE_RESULT attempt=7 status=not-achieved",
            "WEBEEBLOCKS_PRECISE_RESULT attempt=8 status=not-achieved",
            "WEBEEBLOCKS_PRECISE_COLLISION attempt=9",
            "WEBEEBLOCKS_PRECISE_RESULT attempt=9 status=not-achieved",
            "WEBEEBLOCKS_PRECISE_RESULT attempt=10 status=achieved",
        ):
            if marker not in webots_log:
                return fail(f"missing Webots progression marker: {marker}", webots_log[-14000:])
        if "ERROR:" in webots_log:
            return fail("Webots emitted an ERROR line", webots_log[-14000:])

        print("PASS progression missions: Activity 1 sequencing plus Activity 2 whole-craft precision, undershoot, overshoot, lateral miss, collision fail-safe, alternative decomposition and reset freshness in real R2025a")
        return 0
    finally:
        cleanup_temp_world()


if __name__ == "__main__":
    raise SystemExit(main())
