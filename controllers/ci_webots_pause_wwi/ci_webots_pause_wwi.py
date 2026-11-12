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
while time.monotonic() < init_deadline:
    if controller.step(32) == -1:
        abort('terminated-before-wwi-begin')
    controller.wwiSendText(PFX + 'READY ' + TOKEN)
    for message in receive():
        if message == PFX + 'BEGIN ' + TOKEN:
            begun = True
            break
    if begun:
        break
if not begun:
    abort('robot-window-begin-missing')

frozen = controller.getTime()
controller.simulationSetMode(Supervisor.SIMULATION_MODE_PAUSE)
pause_started = time.monotonic()
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
if not resumed_by_wwi:
    abort('robot-window-resume-unavailable-during-pause')
if rejected_token < 1:
    abort('missing-adversarial-stale-resume')

wall_elapsed = time.monotonic() - pause_started
if wall_elapsed < 1.0 or controller.getTime() != frozen:
    abort('pause-duration-or-clock-invalid')
controller.simulationSetMode(Supervisor.SIMULATION_MODE_REAL_TIME)
if controller.step(0) == -1:
    abort('step-zero-cannot-acknowledge-resume')
if controller.simulationGetMode() != Supervisor.SIMULATION_MODE_REAL_TIME:
    abort('realtime-mode-unattested')
if controller.step(32) == -1:
    abort('nonzero-step-did-not-resume')
advanced_ms = round((controller.getTime() - frozen) * 1000.0)
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
