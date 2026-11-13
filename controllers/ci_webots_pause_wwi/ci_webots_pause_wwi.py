"""R2025a-only actual pause/WWI transport falsification. No flight control.

The real Robot Window must deliver a fresh resume command *after* a bounded
wall-clock hold while wb_robot_step(0) is used and simulated time stays exact.
A controller that hangs in step(0) fails the external hard timeout.
"""
import atexit
import json
import os
from pathlib import Path
import time
from controller import Supervisor

TOKEN = 'wb-pause-native-r2025a-974'
PFX = 'GP_PAUSE_WWI_'
# This intentionally independent sidecar outlives Webots' controller stdout:
# its console silently stops forwarding after the simulator asks for shutdown.
trace_dir = os.environ.get('WEBEEBLOCKS_CI_ARTIFACT_DIR')
if not trace_dir:
    raise RuntimeError('isolated PAUSE/WWI trace directory missing')
trace_path = Path(trace_dir) / 'controller-sidecar.jsonl'
trace_path.parent.mkdir(parents=True, exist_ok=True)


def trace(stage, **evidence):
    value = dict(schema='webeeblocks-webots-pause-controller-sidecar-v1',
                 stage=stage, wall_monotonic_seconds=round(time.monotonic(), 6),
                 **evidence)
    with trace_path.open('a', encoding='utf-8') as output:
        output.write(json.dumps(value, sort_keys=True) + '\n')
        output.flush()
        os.fsync(output.fileno())


atexit.register(trace, 'PYTHON_ATEXIT')
trace('CONTROLLER_ENTRY')
controller = Supervisor()
trace('SUPERVISOR_CONSTRUCTED')
print(PFX + "CONTROLLER_START", flush=True)


def receive():
    messages = []
    message = controller.wwiReceiveText()
    while message:
        messages.append(message)
        message = controller.wwiReceiveText()
    return messages


def abort(reason):
    trace('ABORT', reason=reason)
    print(PFX + 'FAIL ' + reason, flush=True)
    # Only this isolated test world may change the simulator mode.
    try:
        controller.simulationSetMode(Supervisor.SIMULATION_MODE_REAL_TIME)
        controller.simulationQuit(1)
    except Exception:
        pass
    raise RuntimeError(reason)


# An active GUI Robot Window, rather than a controller self-message, must
# initiate this test through the real WWI transport.
init_deadline = time.monotonic() + 20.0
begun = False
first_ready = False
while time.monotonic() < init_deadline:
    if controller.step(32) == -1:
        abort('terminated-before-wwi-begin')
    controller.wwiSendText(PFX + 'READY ' + TOKEN)
    if not first_ready:
        print(PFX + 'READY_SENT', flush=True)
        first_ready = True
    for message in receive():
        if message == PFX + 'BEGIN ' + TOKEN:
            begun = True
            break
    if begun:
        break
if not begun:
    abort('robot-window-begin-missing')
print(PFX + 'BEGIN_RECEIVED', flush=True)

frozen = controller.getTime()
controller.simulationSetMode(Supervisor.SIMULATION_MODE_PAUSE)
pause_started = time.monotonic()
print(PFX + 'PAUSE_REQUESTED', flush=True)
rejected_token = 0
resumed_by_wwi = False
paused_sent = False
# No positive-duration step can be issued here: that would deadlock on PAUSE.
while time.monotonic() - pause_started < 8.0:
    if controller.step(0) == -1:
        abort('step-zero-terminated')
    if controller.simulationGetMode() != Supervisor.SIMULATION_MODE_PAUSE:
        abort('pause-mode-unattested')
    if controller.getTime() != frozen:
        abort('simulation-clock-advanced-while-paused')
    if not paused_sent:
        paused_sent = True
        controller.wwiSendText(PFX + 'PAUSED ' + TOKEN)
        print(PFX + 'PAUSE_ATTESTED', flush=True)
    for message in receive():
        if message.startswith(PFX + 'RESUME '):
            if message != PFX + 'RESUME ' + TOKEN:
                rejected_token += 1
                continue
            if time.monotonic() - pause_started < 1.0:
                abort('resumed-before-one-wall-second')
            resumed_by_wwi = True
            break
    if resumed_by_wwi:
        break
    time.sleep(0.01)
if resumed_by_wwi:
    print(PFX + "RESUME_RECEIVED", flush=True)
if not resumed_by_wwi:
    abort('robot-window-resume-unavailable-during-pause')
if rejected_token < 1:
    abort('missing-adversarial-stale-resume')
print(PFX + 'STALE_RESUME_REJECTED count=' + str(rejected_token), flush=True)

wall_elapsed = time.monotonic() - pause_started
print(PFX + 'CLOCK_PRE_RESUME frozen_ms=' + str(round(frozen * 1000.0)) +
      ' now_ms=' + str(round(controller.getTime() * 1000.0)) +
      ' wall_seconds=' + str(round(wall_elapsed, 3)), flush=True)
if wall_elapsed < 1.0 or controller.getTime() != frozen:
    abort('pause-duration-or-clock-invalid')
print(PFX + 'MODE_REALTIME_REQUESTED', flush=True)
controller.simulationSetMode(Supervisor.SIMULATION_MODE_REAL_TIME)
print(PFX + 'MODE_REALTIME_CALL_RETURNED', flush=True)
print(PFX + 'STEP_ZERO_AFTER_RESUME_REQUESTED', flush=True)
if controller.step(0) == -1:
    abort('step-zero-cannot-acknowledge-resume')
print(PFX + 'STEP_ZERO_AFTER_RESUME_RETURNED', flush=True)
if controller.simulationGetMode() != Supervisor.SIMULATION_MODE_REAL_TIME:
    abort('realtime-mode-unattested')
print(PFX + 'MODE_REALTIME_ATTESTED', flush=True)
trace('BEFORE_STEP_32', frozen_simulated_ms=round(frozen * 1000),
      mode=int(controller.simulationGetMode()))
print(PFX + 'STEP_32_AFTER_RESUME_REQUESTED', flush=True)
first_step_result = controller.step(32)
# If Webots starts terminating controllers, their stdout may disappear before
# the Python branch runs. Persist the return code before any Webots calls.
trace('AFTER_STEP_32', return_code=int(first_step_result))
if first_step_result == -1:
    abort('nonzero-step-did-not-resume')
print(PFX + 'STEP_32_AFTER_RESUME_RETURNED', flush=True)
advanced_ms = round((controller.getTime() - frozen) * 1000.0)
trace('SIMULATED_TIME_AFTER_STEP_32', delta_ms=advanced_ms,
      mode=int(controller.simulationGetMode()))
print(PFX + 'CLOCK_RESUMED_DELTA_MS ' + str(advanced_ms), flush=True)
if not 32 <= advanced_ms <= 64:
    abort('resumed-simulation-clock-not-advanced-as-expected')

proof = {
    'schema': 'webeeblocks-webots-pause-wwi-v1',
    'simulated_frozen_ms': round(frozen * 1000.0),
    'frozen_delta_ms': 0,
    'pause_wall_seconds': round(wall_elapsed, 3),
    'resumed_simulated_ms': advanced_ms,
    'resume_via_robot_window_wwi': True,
    'wrong_token_rejected': rejected_token,
    'steps_while_paused': 0,
    'simulation': 'isolated-r2025a-only',
}
trace('NATIVE_PASS', delta_ms=advanced_ms, proof=proof)
print(PFX + 'PASS ' + json.dumps(proof, sort_keys=True), flush=True)
controller.simulationQuit(0)
