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
controller_path.write_text(controller.replace(needle, replacement, 1), encoding='utf-8')

script = r'''
<script>
(async function() {
  function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }
  let seq = 0;
  let chain = Promise.resolve();
  let astEvents = 0;
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
    workspace.clear();
    Blockly.Xml.domToWorkspace(Blockly.Xml.textToDom(__FIXTURE__), workspace);
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
    if (window.runtimeRunning)
      throw new Error('runtime entered running state before controller READY');
    if (!submit.disabled || state.textContent !== 'INITIALISATION' || runtimeBackend.ready !== false)
      throw new Error('pre-READY guard changed UI/backend state: ' + JSON.stringify(snapshot()));
    await report('PRE_READY_GUARD_OK', snapshot());

    await waitFor(() => runtimeBackend.ready === true, 'controller READY message', 20000);
    await waitFor(() => !submit.disabled && state.textContent === 'PRÊT', 'post-READY UI enable', 2000);
    await report('READY', snapshot());

    const ast = WebeeBlocksSemanticAst.compileWorkspace(workspace);
    await report('FIXTURE_AST', ast);
    submit.click();
    await report('SUBMIT', 'clicked');
    await waitFor(() => document.getElementById('runtimeState').textContent === 'TERMINÉ', 'Runtime v2 completion', 70000);
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
print('Prepared Runtime v2 real Robot Window harness with causal pre-READY discrimination.')
