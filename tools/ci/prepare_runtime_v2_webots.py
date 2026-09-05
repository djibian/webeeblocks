#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
html_path = ROOT / 'plugins/robot_windows/blockly_v2/blockly_v2.html'
controller_path = ROOT / 'controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c'
fixture = (ROOT / 'controllers/Blockly_Programs/CrazyflieReactiveV2.xml').read_text(encoding='utf-8')
html = html_path.read_text(encoding='utf-8')

# CI-only discrimination seam: keep the real controller alive but intentionally
# postpone READY long enough for the real Robot Window to prove its pre-READY
# behavior. This mutation happens only in the checked-out CI working tree.
controller = controller_path.read_text(encoding='utf-8')
needle = '  send_text(PREFIX " READY");\n'
replacement = r'''  printf(PREFIX " CI READY_DELAY_BEGIN time=%.3f\n", wb_robot_get_time());
  fflush(stdout);
  while (wb_robot_get_time() < 12.0) {
    if (wb_robot_step(step) == -1) {
      wb_robot_cleanup();
      return 1;
    }
  }
  position = wb_gps_get_values(gps);
  rpy = wb_inertial_unit_get_roll_pitch_yaw(imu);
  target_x = position[0];
  target_y = position[1];
  target_z = position[2];
  target_yaw = rpy[2];
  previous_x = position[0];
  previous_y = position[1];
  previous_z = position[2];
  previous_time = wb_robot_get_time();
  printf(PREFIX " CI READY_DELAY_END time=%.3f\n", previous_time);
  fflush(stdout);
  send_text(PREFIX " READY");
'''
if needle not in controller:
    raise SystemExit('Runtime v2 READY injection point not found')
controller = controller.replace(needle, replacement, 1)
move_start_needle = '''        target_yaw = yaw;
        if (strcmp(request.direction, "forward") == 0) {'''
move_start_replacement = r'''        target_yaw = yaw;
        printf(PREFIX " CI MOVE_START %s x=%.9f y=%.9f yaw=%.9f\n", request.direction, x, y, yaw);
        fflush(stdout);
        if (strcmp(request.direction, "forward") == 0) {'''
if move_start_needle not in controller:
    raise SystemExit('Runtime v2 MOVE start instrumentation point not found')
controller = controller.replace(move_start_needle, move_start_replacement, 1)
move_end_needle = '''          trace_move(active_direction, active_value);
          response_ok(active_id);'''
move_end_replacement = r'''          trace_move(active_direction, active_value);
          printf(PREFIX " CI MOVE_END %s x=%.9f y=%.9f yaw=%.9f\n", active_direction, x, y, yaw);
          fflush(stdout);
          response_ok(active_id);'''
if move_end_needle not in controller:
    raise SystemExit('Runtime v2 MOVE end instrumentation point not found')
controller = controller.replace(move_end_needle, move_end_replacement, 1)
vertical_start_needle = '''        target_x = x;
        target_y = y;
        target_yaw = yaw;
        target_z = next_target_z;
        command = CMD_VERTICAL;'''
vertical_start_replacement = r'''        target_x = x;
        target_y = y;
        target_yaw = yaw;
        target_z = next_target_z;
        printf(PREFIX " CI VERTICAL_START %s x=%.9f y=%.9f z=%.9f yaw=%.9f target_z=%.9f\n",
               request.direction, x, y, z, yaw, target_z);
        fflush(stdout);
        command = CMD_VERTICAL;'''
if vertical_start_needle not in controller:
    raise SystemExit('Runtime v2 VERTICAL start instrumentation point not found')
controller = controller.replace(vertical_start_needle, vertical_start_replacement, 1)
vertical_end_needle = '''          trace_vertical(active_direction, active_value);
          response_ok(active_id);'''
vertical_end_replacement = r'''          trace_vertical(active_direction, active_value);
          printf(PREFIX " CI VERTICAL_END %s x=%.9f y=%.9f z=%.9f yaw=%.9f\n",
                 active_direction, x, y, z, yaw);
          fflush(stdout);
          response_ok(active_id);'''
if vertical_end_needle not in controller:
    raise SystemExit('Runtime v2 VERTICAL end instrumentation point not found')
controller = controller.replace(vertical_end_needle, vertical_end_replacement, 1)
turn_start_needle = '''        target_x = x;
        target_y = y;
        target_z = z;
        target_yaw = wrap_angle(yaw + request.value * PI / 180.0);
        command = CMD_TURN;'''
turn_start_replacement = r'''        target_x = x;
        target_y = y;
        target_z = z;
        target_yaw = wrap_angle(yaw + request.value * PI / 180.0);
        printf(PREFIX " CI TURN_START angle_deg=%.9f x=%.9f y=%.9f z=%.9f yaw=%.9f target_yaw=%.9f\n",
               request.value, x, y, z, yaw, target_yaw);
        fflush(stdout);
        command = CMD_TURN;'''
if turn_start_needle not in controller:
    raise SystemExit('Runtime v2 TURN start instrumentation point not found')
controller = controller.replace(turn_start_needle, turn_start_replacement, 1)
turn_end_needle = '''          trace_turn(active_value);
          response_ok(active_id);'''
turn_end_replacement = r'''          trace_turn(active_value);
          printf(PREFIX " CI TURN_END angle_deg=%.9f x=%.9f y=%.9f z=%.9f yaw=%.9f target_yaw=%.9f\n",
                 active_value, x, y, z, yaw, target_yaw);
          fflush(stdout);
          response_ok(active_id);'''
if turn_end_needle not in controller:
    raise SystemExit('Runtime v2 TURN end instrumentation point not found')
controller = controller.replace(turn_end_needle, turn_end_replacement, 1)
controller_path.write_text(controller, encoding='utf-8')

script = r'''
<script>
(async function() {
  function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }
  let seq = 0;
  let chain = Promise.resolve();
  let astEvents = 0;
  const wwiTx = [];
  function report(event, detail) {
    const payload = {seq: seq++, event, detail: detail === undefined ? null : detail, wall_ms: Date.now()};
    chain = chain.then(() => fetch('http://127.0.0.1:8765/event', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
    }));
    return chain;
  }
  function snapshot() {
    const submit = document.getElementById('submit');
    const state = document.getElementById('runtimeState');
    const detail = document.getElementById('runtimeDetail');
    return {
      readyState: document.readyState,
      hasBlockly: typeof window.Blockly !== 'undefined',
      blocklyVersion: typeof window.Blockly !== 'undefined' ? String(window.Blockly.VERSION || '') : null,
      hasActivities: typeof window.WebeeBlocksActivities !== 'undefined',
      hasProfiles: typeof window.WebeeBlocksActivityProfiles !== 'undefined',
      hasAst: typeof window.WebeeBlocksSemanticAst !== 'undefined',
      hasInterpreter: typeof window.WebeeBlocksInterpreter !== 'undefined',
      hasContract: typeof window.WebeeBlocksActivityContract !== 'undefined',
      hasBackendClass: typeof window.WebeeBlocksWwiBackend !== 'undefined',
      hasWorkspace: !!window.workspace,
      hasRobotWindow: !!window.robotWindow,
      hasBackend: !!window.runtimeBackend,
      backendReady: window.runtimeBackend ? window.runtimeBackend.ready : null,
      backendNextId: window.runtimeBackend ? window.runtimeBackend.nextId : null,
      backendPending: window.runtimeBackend ? Object.keys(window.runtimeBackend.pending || {}).length : null,
      runtimeRunning: !!window.runtimeRunning,
      astEvents: astEvents,
      wwiTxCount: wwiTx.length,
      submitDisabled: submit ? submit.disabled : null,
      state: state ? state.textContent : null,
      detail: detail ? detail.textContent : null
    };
  }
  async function waitFor(predicate, label, timeoutMs) {
    const start = Date.now();
    let nextDiag = start;
    while (Date.now() - start < timeoutMs) {
      if (predicate()) return;
      if (Date.now() >= nextDiag) {
        await report('DIAG', snapshot());
        nextDiag = Date.now() + 2000;
      }
      await sleep(25);
    }
    throw new Error('timeout waiting for ' + label + ': ' + JSON.stringify(snapshot()));
  }
  function normalizeWwiRequest(message) {
    const match = String(message).match(/^WEBEEBLOCKS_RUNTIME_V2 REQUEST (\d+) (.+)$/);
    if (!match)
      throw new Error('unexpected WWI request framing: ' + String(message));
    const id = Number(match[1]);
    const command = match[2];
    if (command.startsWith('TAKEOFF '))
      return {id, command: 'TAKEOFF'};
    if (command === 'RANGE front')
      return {id, command: 'RANGE'};
    if (command.startsWith('MOVE left '))
      return {id, command: 'MOVE_LEFT'};
    if (command.startsWith('MOVE forward '))
      return {id, command: 'MOVE_FORWARD'};
    if (command === 'LAND')
      return {id, command: 'LAND'};
    throw new Error('unexpected WWI request command: ' + command);
  }

  window.addEventListener('error', event => report('WINDOW_ERROR', {
    message: event.message, filename: event.filename, lineno: event.lineno, colno: event.colno
  }));
  window.addEventListener('unhandledrejection', event => report('UNHANDLED_REJECTION', String(event.reason)));
  window.addEventListener('webeeblocks-runtime-v2', event => report('STATE', event.detail));
  window.addEventListener('webeeblocks-runtime-v2-ast', event => {
    astEvents += 1;
    report('AST', event.detail);
  });
  window.addEventListener('webeeblocks-wwi', event => report('WWI_RX', String(event.detail)));

  try {
    await report('HARNESS_START', snapshot());

    // The CI controller intentionally withholds READY until simulation time 12 s.
    // Observe the actual product UI during that interval, with a valid program
    // already loaded so an old eager runProgram() would generate AST/WWI traffic.
    await waitFor(() => window.workspace && window.runtimeBackend && window.robotWindow,
      'Runtime v2 pre-READY objects', 12000);
    if (String(Blockly.VERSION || '') !== '13.2.1')
      throw new Error('unexpected runtime Blockly.VERSION=' + String(Blockly.VERSION || ''));
    await report('BLOCKLY_VERSION', String(Blockly.VERSION));

    // Observe the exact product WWI commands emitted by the shared interpreter.
    const originalRobotWindowSend = robotWindow.send.bind(robotWindow);
    robotWindow.send = function(message) {
      const text = String(message);
      if (text.startsWith('WEBEEBLOCKS_RUNTIME_V2 REQUEST ')) {
        wwiTx.push(text);
        report('WWI_TX', text);
      }
      return originalRobotWindowSend(message);
    };

    workspace.clear();
    const fixtureDom = Blockly.utils.xml.textToDom(__FIXTURE__);
    Blockly.Xml.domToWorkspace(fixtureDom, workspace);
    await report('FIXTURE_IMPORTED', {topBlocks: workspace.getTopBlocks(false).length});
    await sleep(50);

    const submit = document.getElementById('submit');
    const state = document.getElementById('runtimeState');
    const preNextId = runtimeBackend.nextId;
    if (runtimeBackend.ready !== false)
      throw new Error('backend became ready before delayed controller READY: ' + JSON.stringify(snapshot()));
    if (!submit.disabled)
      throw new Error('Submit enabled before controller READY: ' + JSON.stringify(snapshot()));
    if (state.textContent !== 'INITIALISATION')
      throw new Error('UI not INITIALISATION before controller READY: ' + JSON.stringify(snapshot()));
    await report('PRE_READY', snapshot());

    // Exercise both user click semantics and the public run function. Neither may
    // compile an AST nor emit a product request while backend.ready is false.
    submit.click();
    await window.runProgram();
    await sleep(300);
    if (astEvents !== 0)
      throw new Error('AST generated before controller READY');
    if (runtimeBackend.nextId !== preNextId)
      throw new Error('WWI request id consumed before controller READY');
    if (Object.keys(runtimeBackend.pending || {}).length !== 0)
      throw new Error('pending WWI request exists before controller READY');
    if (wwiTx.length !== 0)
      throw new Error('WWI request emitted before controller READY: ' + JSON.stringify(wwiTx));
    if (window.runtimeRunning)
      throw new Error('runtime entered running state before controller READY');
    if (!submit.disabled || state.textContent !== 'INITIALISATION' || runtimeBackend.ready !== false)
      throw new Error('pre-READY guard changed UI/backend state: ' + JSON.stringify(snapshot()));
    await report('PRE_READY_GUARD_OK', snapshot());

    await waitFor(() => runtimeBackend.ready === true, 'controller READY message', 20000);
    await waitFor(() => !submit.disabled && state.textContent === 'PRÊT', 'post-READY UI enable', 2000);
    await report('READY', snapshot());

    // Discriminating fail-closed proof on the actual WWI backend object. Remove
    // range(front) only from the backend contract and require ActivityContract to
    // reject the valid workspace before the interpreter can emit TAKEOFF or RANGE.
    const originalCapabilities = runtimeBackend.capabilities;
    runtimeBackend.capabilities = Object.freeze({
      actions: originalCapabilities.actions.slice(),
      rangeDirections: [],
      moveDirections: originalCapabilities.moveDirections.slice(),
      verticalDirections: originalCapabilities.verticalDirections.slice()
    });
    const negativeNextId = runtimeBackend.nextId;
    const negativeTxCount = wwiTx.length;
    let negativeRejected = false;
    try {
      await WebeeBlocksActivityContract.execute(
        runtimeProfile,
        workspace,
        WebeeBlocksSemanticAst,
        WebeeBlocksInterpreter,
        runtimeBackend,
        {maxSteps: 1000}
      );
    } catch (error) {
      negativeRejected = true;
      await report('BACKEND_CAPABILITY_REJECTED', error && error.message ? error.message : String(error));
    } finally {
      runtimeBackend.capabilities = originalCapabilities;
    }
    if (!negativeRejected)
      throw new Error('missing range(front) backend capability was accepted');
    if (runtimeBackend.nextId !== negativeNextId)
      throw new Error('fail-closed preflight consumed WWI request id');
    if (wwiTx.length !== negativeTxCount)
      throw new Error('fail-closed preflight emitted WWI request: ' + JSON.stringify(wwiTx.slice(negativeTxCount)));
    if (Object.keys(runtimeBackend.pending || {}).length !== 0)
      throw new Error('fail-closed preflight left pending WWI request');
    await report('BACKEND_CAPABILITY_GUARD_OK', snapshot());

    const ast = WebeeBlocksSemanticAst.compileWorkspace(workspace);
    await report('FIXTURE_AST', ast);
    submit.click();
    await report('SUBMIT', 'clicked');
    await waitFor(() => document.getElementById('runtimeState').textContent === 'TERMINÉ', 'Runtime v2 completion', 70000);

    const normalized = wwiTx.map(normalizeWwiRequest);
    const expectedCommands = ['TAKEOFF','RANGE','MOVE_LEFT','RANGE','MOVE_FORWARD','RANGE','MOVE_LEFT','LAND'];
    const actualCommands = normalized.map(entry => entry.command);
    const actualIds = normalized.map(entry => entry.id);
    if (JSON.stringify(actualCommands) !== JSON.stringify(expectedCommands))
      throw new Error('unexpected WWI request sequence: ' + JSON.stringify(actualCommands));
    if (JSON.stringify(actualIds) !== JSON.stringify([1,2,3,4,5,6,7,8]))
      throw new Error('unexpected WWI request ids: ' + JSON.stringify(actualIds));
    await report('WWI_SEQUENCE_OK', normalized);

    const lateralRanges = {};
    for (const direction of ['left', 'right']) {
      const value = await runtimeBackend.readRange(direction);
      if (!Number.isFinite(value) || value < 0 || value > 2.001)
        throw new Error('invalid ' + direction + ' range sample: ' + String(value));
      lateralRanges[direction] = value;
    }
    await report('LATERAL_RANGES_OK', lateralRanges);

    await runtimeBackend.resetSimulation();
    const lightTxStart = wwiTx.length;
    workspace.clear();
    const lightTakeoff = workspace.newBlock('webeeblocks_v2_takeoff');
    const lightBlue = workspace.newBlock('webeeblocks_v2_light');
    const lightOff = workspace.newBlock('webeeblocks_v2_light');
    const lightLand = workspace.newBlock('webeeblocks_v2_land');
    lightTakeoff.setFieldValue('0.35', 'HEIGHT');
    lightBlue.setFieldValue('blue', 'COLOR');
    lightOff.setFieldValue('off', 'COLOR');
    lightTakeoff.nextConnection.connect(lightBlue.previousConnection);
    lightBlue.nextConnection.connect(lightOff.previousConnection);
    lightOff.nextConnection.connect(lightLand.previousConnection);
    const lightAst = WebeeBlocksSemanticAst.compileWorkspace(workspace);
    const expectedLightAst = {version:1,semantics:'webeeblocks-ast-v1',program:[
      {kind:'takeoff',height_m:0.35},{kind:'set_light',color:'blue'},{kind:'set_light',color:'off'},{kind:'land'}
    ]};
    if (JSON.stringify(lightAst) !== JSON.stringify(expectedLightAst))
      throw new Error('unexpected Color LED AST: ' + JSON.stringify(lightAst));
    await WebeeBlocksActivityContract.execute(
      runtimeProfile, workspace, WebeeBlocksSemanticAst, WebeeBlocksInterpreter, runtimeBackend, {maxSteps:20}
    );
    const lightRequests = wwiTx.slice(lightTxStart).map(text => text.replace(/^WEBEEBLOCKS_RUNTIME_V2 REQUEST \d+ /, ''));
    const expectedLightRequests = [
      'TAKEOFF ' + Number(0.35).toPrecision(17),
      'LIGHT blue',
      'LIGHT off',
      'LAND'
    ];
    if (JSON.stringify(lightRequests) !== JSON.stringify(expectedLightRequests))
      throw new Error('unexpected Color LED WWI sequence: ' + JSON.stringify(lightRequests));
    await report('COLOR_LED_OK', {ast:lightAst, requests:lightRequests});

    await runtimeBackend.resetSimulation();
    await runtimeBackend.takeoff(0.35);
    await runtimeBackend.move('back', 0.20);
    await runtimeBackend.move('right', 0.20);
    await runtimeBackend.vertical('up', 0.10);
    await runtimeBackend.vertical('down', 0.10);
    await runtimeBackend.turn(30);
    await runtimeBackend.turn(-30);
    await runtimeBackend.land();
    await report('HORIZONTAL_MOVES_OK', {directions:['back','right']});
    await report('VERTICAL_MOVES_OK', {directions:['up','down'], distance_m:0.10});
    await report('YAW_TURNS_OK', {angles_deg:[30,-30]});

    await report('DONE', document.getElementById('runtimeDetail').textContent);
    await chain;
    console.log('WEBEEBLOCKS_CI_RUNTIME_V2_DONE');
  } catch (error) {
    await report('ERROR', error && error.stack ? error.stack : String(error));
    await report('FINAL_DIAG', snapshot());
    await chain;
    console.error('WEBEEBLOCKS_CI_RUNTIME_V2_ERROR=' + (error && error.stack ? error.stack : String(error)));
  }
})();
</script>
'''.replace('__FIXTURE__', json.dumps(fixture))

html_path.write_text(html + '\n' + script, encoding='utf-8')
print('Prepared Runtime v2 real Robot Window harness with causal pre-READY, backend-capability and WWI-sequence discrimination.')
