"""R2025a-only actual pause/WWI transport falsification. No flight control.

The real Robot Window must deliver a fresh resume command *after* a bounded
wall-clock hold while wb_robot_step(0) is used and simulated time stays exact.
A controller that hangs in step(0) fails the external hard timeout.
"""
import json
import time
from controller import Supervisor

TOKEN = 'wb-pause-native-r2025a-974'
PFX = 'GP_PAUSE_WWI_'
controller = Supervisor()
print(PFX + "CONTROLLER_START", flush=True)


def receive():
    messages = []
    message = controller.wwiReceiveText()
    while message:
        messages.append(message)
        message = controller.wwiReceiveText()
    return messages


def abort(reason):
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
print(PFX + 'STEP_32_AFTER_RESUME_REQUESTED', flush=True)
if controller.step(32) == -1:
    abort('nonzero-step-did-not-resume')
print(PFX + 'STEP_32_AFTER_RESUME_RETURNED', flush=True)
advanced_ms = round((controller.getTime() - frozen) * 1000.0)
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
print(PFX + 'PASS ' + json.dumps(proof, sort_keys=True), flush=True)
controller.simulationQuit(0)
