#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = ROOT / 'plugins/robot_windows/blockly_v2/blockly_v2.html'
MARKER = '<!-- WEBEEBLOCKS_OBSERVABILITY_CI -->'
REACTIVE = (ROOT / 'controllers/Blockly_Programs/CrazyflieReactiveV2.xml').read_text(encoding='utf-8')
BLOCKED = '''<xml xmlns="https://developers.google.com/blockly/xml">
  <block type="webeeblocks_v2_takeoff" id="ci_blocked_takeoff" x="40" y="40">
    <field name="HEIGHT">1</field>
    <next>
      <block type="webeeblocks_v2_move" id="ci_blocked_move">
        <field name="DIRECTION">forward</field>
        <field name="DISTANCE">2</field>
        <next><block type="webeeblocks_v2_land" id="ci_blocked_land"></block></next>
      </block>
    </next>
  </block>
</xml>'''

COMMON = r'''
  function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }
  let seq = 0;
  let chain = Promise.resolve();
  function report(event, detail) {
    const payload = {seq: seq++, event, detail: detail === undefined ? null : detail, wall_ms: Date.now()};
    chain = chain.then(() => fetch('http://127.0.0.1:8765/event', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
    }));
    return chain;
  }
  function snapshot() {
    return {
      state: document.getElementById('runtimeState') && document.getElementById('runtimeState').textContent,
      detail: document.getElementById('runtimeDetail') && document.getElementById('runtimeDetail').textContent,
      debugPanelHidden: document.getElementById('debugPanel') && document.getElementById('debugPanel').hidden,
      stepModeChecked: document.getElementById('stepMode') && document.getElementById('stepMode').checked,
      nextDisabled: document.getElementById('stepNext') && document.getElementById('stepNext').disabled,
      continueDisabled: document.getElementById('stepContinue') && document.getElementById('stepContinue').disabled,
      sensorText: document.getElementById('debugSensors') && document.getElementById('debugSensors').textContent,
      variablesHidden: document.getElementById('debugVariablesRow') && document.getElementById('debugVariablesRow').hidden,
      backendReady: window.runtimeBackend && runtimeBackend.ready,
      simulationDebug: window.runtimeBackend && runtimeBackend.capabilities && runtimeBackend.capabilities.simulationDebug,
      nextId: window.runtimeBackend && runtimeBackend.nextId,
      pending: window.runtimeBackend ? Object.keys(runtimeBackend.pending || {}).length : null,
      runtimeRunning: !!window.runtimeRunning
    };
  }
  async function waitFor(predicate, label, timeoutMs) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      if (predicate()) return;
      await sleep(25);
    }
    throw new Error('timeout waiting for ' + label + ': ' + JSON.stringify(snapshot()));
  }
  function loadXml(xml) {
    workspace.clear();
    const dom = Blockly.utils.xml.textToDom(xml);
    Blockly.Xml.domToWorkspace(dom, workspace);
  }
  window.addEventListener('error', event => report('WINDOW_ERROR', {
    message: event.message, filename: event.filename, lineno: event.lineno, colno: event.colno
  }));
  window.addEventListener('unhandledrejection', event => report('UNHANDLED_REJECTION', String(event.reason)));
  window.addEventListener('webeeblocks-runtime-v2', event => report('STATE', event.detail));
'''

STEP = r'''
<script>
(async function() {
__COMMON__
  const wwiTx = [];
  const active = [];
  const paused = [];
  const sensors = [];
  const diagnostics = [];
  const asts = [];
  function blockDetail(detail) {
    const block = detail && detail.blockId && window.workspace ? workspace.getBlockById(detail.blockId) : null;
    return {
      path: detail && detail.path,
      kind: detail && (detail.kind || (detail.node && detail.node.kind)),
      blockId: detail && detail.blockId,
      blockType: block ? block.type : (detail && detail.blockType) || null,
      direction: block && block.getFieldValue('DIRECTION') !== null ? block.getFieldValue('DIRECTION') : null,
      iteration: detail && detail.iteration
    };
  }
  window.addEventListener('webeeblocks-runtime-v2-diagnostic', event => {
    diagnostics.push(event.detail); report('DIAGNOSTIC', event.detail);
  });
  window.addEventListener('webeeblocks-runtime-v2-ast', event => {
    asts.push(event.detail); report('AST', event.detail);
  });
  window.addEventListener('webeeblocks-debug-active', event => {
    const detail = blockDetail(event.detail); active.push(detail); report('DEBUG_ACTIVE', detail);
  });
  window.addEventListener('webeeblocks-debug-paused', event => {
    const detail = blockDetail(event.detail); paused.push(detail);
    report('DEBUG_PAUSED', Object.assign(detail, {txCount: wwiTx.length}));
  });
  window.addEventListener('webeeblocks-debug-resumed', event => report('DEBUG_RESUMED', blockDetail(event.detail)));
  window.addEventListener('webeeblocks-debug-sensor', event => {
    const detail = Object.assign(blockDetail(event.detail), {
      sensorDirection: event.detail.direction, sensorValue: event.detail.value
    });
    sensors.push(detail); report('DEBUG_SENSOR', detail);
  });
  async function nextAndWait(count, label, timeout) {
    document.getElementById('stepNext').click();
    await waitFor(() => paused.length >= count, label, timeout || 5000);
  }
  try {
    await waitFor(() => window.workspace && window.runtimeBackend && runtimeBackend.ready === true,
      'Runtime v2 READY', 20000);
    if (String(Blockly.VERSION || '') !== '13.2.1') throw new Error('unexpected Blockly.VERSION');
    if (!runtimeBackend.capabilities || runtimeBackend.capabilities.simulationDebug !== true)
      throw new Error('simulation-only debug capability not enabled for Webots backend');
    if (!runtimeBackend.capabilities || runtimeBackend.capabilities.simulationReset !== true)
      throw new Error('simulation-only reset capability not enabled for Webots backend');
    if (document.getElementById('debugPanel').hidden) throw new Error('simulation debug panel remained hidden');
    if (!document.getElementById('debugVariablesRow').hidden)
      throw new Error('variables shown despite no product variable semantics');
    await report('READY', snapshot());

    const originalRobotWindowSend = robotWindow.send.bind(robotWindow);
    robotWindow.send = function(message) {
      const text = String(message);
      if (text.startsWith('WEBEEBLOCKS_RUNTIME_V2 REQUEST ')) {
        wwiTx.push(text); report('WWI_TX', text);
      }
      return originalRobotWindowSend(message);
    };

    loadXml(__REACTIVE__);
    const baselineAst = WebeeBlocksSemanticAst.compileWorkspace(workspace);
    const originalTakeoff = runtimeBackend.takeoff.bind(runtimeBackend);
    const techStartId = runtimeBackend.nextId;
    runtimeBackend.takeoff = function() { return Promise.reject(new Error('CI_TECHNICAL_FAILURE')); };
    await window.runProgram();
    runtimeBackend.takeoff = originalTakeoff;
    if (document.getElementById('runtimeState').textContent !== 'ERREUR')
      throw new Error('technical failure did not remain ERREUR: ' + JSON.stringify(snapshot()));
    if (runtimeBackend.nextId !== techStartId) throw new Error('technical fault consumed WWI request');
    if (!diagnostics.length || diagnostics[diagnostics.length - 1].studentState !== 'ERREUR' || diagnostics[diagnostics.length - 1].machineCode !== null)
      throw new Error('technical diagnostic mismatch: ' + JSON.stringify(diagnostics));
    await report('TECHNICAL_FAILURE_OK', snapshot());

    const resetTxStart = wwiTx.length;
    const workspaceBeforeReset = JSON.stringify(Blockly.serialization.workspaces.save(workspace));
    document.getElementById('resetSimulation').click();
    await waitFor(() => document.getElementById('runtimeState').textContent === 'PRÊT', 'reset after technical failure', 5000);
    const resetTx = wwiTx.slice(resetTxStart);
    if (resetTx.length !== 1 || !resetTx[0].includes(' RESET'))
      throw new Error('technical failure reset did not emit exactly one RESET request: ' + JSON.stringify(resetTx));
    if (runtimeBackend.pending && Object.keys(runtimeBackend.pending).length !== 0)
      throw new Error('technical failure reset left pending backend requests: ' + JSON.stringify(snapshot()));
    const workspaceAfterReset = JSON.stringify(Blockly.serialization.workspaces.save(workspace));
    if (workspaceAfterReset !== workspaceBeforeReset)
      throw new Error('technical failure reset changed workspace');
    if (JSON.stringify(WebeeBlocksSemanticAst.compileWorkspace(workspace)) !== JSON.stringify(baselineAst))
      throw new Error('technical failure reset changed AST');
    await report('TECHNICAL_FAILURE_RESET_OK', snapshot());

    loadXml(__REACTIVE__);
    const stepAst = WebeeBlocksSemanticAst.compileWorkspace(workspace);
    if (JSON.stringify(stepAst) !== JSON.stringify(baselineAst)) throw new Error('step mode changed AST');
    document.getElementById('stepMode').checked = true;
    const txStart = wwiTx.length;
    document.getElementById('submit').click();
    await waitFor(() => paused.length >= 1, 'takeoff pause', 5000);
    if (paused[0].blockType !== 'webeeblocks_v2_takeoff' || paused[0].kind !== 'takeoff')
      throw new Error('takeoff semantic block mismatch: ' + JSON.stringify(paused[0]));
    await sleep(300);
    if (wwiTx.length !== txStart) throw new Error('TAKEOFF started before Pas suivant');
    await report('STEP_TAKEOFF_HELD', paused[0]);

    await nextAndWait(2, 'repeat iteration pause', 20000);
    if (paused[1].blockType !== 'controls_repeat_ext' || paused[1].kind !== 'repeat' || paused[1].iteration !== 0)
      throw new Error('repeat semantic boundary mismatch: ' + JSON.stringify(paused[1]));
    if (wwiTx.length !== txStart + 1 || !wwiTx[txStart].includes(' TAKEOFF '))
      throw new Error('first Pas suivant did not release exactly TAKEOFF: ' + JSON.stringify(wwiTx.slice(txStart)));
    await report('STEP_REPEAT_HELD', paused[1]);

    await nextAndWait(3, 'range pause');
    if (paused[2].blockType !== 'webeeblocks_v2_range' || paused[2].kind !== 'range')
      throw new Error('range semantic boundary mismatch: ' + JSON.stringify(paused[2]));
    if (wwiTx.length !== txStart + 1) throw new Error('repeat step unexpectedly emitted backend action');
    await report('STEP_RANGE_HELD', paused[2]);

    await nextAndWait(4, 'numeric threshold pause');
    await waitFor(() => sensors.length >= 1, 'fresh sensor value', 4000);
    if (sensors[0].blockType !== 'webeeblocks_v2_range' || sensors[0].sensorDirection !== 'front')
      throw new Error('fresh sensor correlation mismatch: ' + JSON.stringify(sensors[0]));
    if (!Number.isFinite(Number(sensors[0].sensorValue))) throw new Error('sensor value is not numeric');
    if (paused[3].blockType !== 'math_number' || paused[3].kind !== 'number')
      throw new Error('number semantic boundary mismatch: ' + JSON.stringify(paused[3]));
    if (wwiTx.length !== txStart + 2 || !wwiTx[txStart + 1].includes(' RANGE front'))
      throw new Error('range step did not release exactly one RANGE request');
    if (wwiTx.slice(txStart).some(text => text.includes(' MOVE '))) throw new Error('branch action started while evaluating condition');
    const sensorText = document.getElementById('debugSensors').textContent;
    if (!sensorText.includes(String(sensors[0].sensorValue)))
      throw new Error('raw sensor value not displayed verbatim: ' + sensorText);
    await report('STEP_NUMBER_HELD_AFTER_SENSOR', {sensor: sensors[0], pause: paused[3], snapshot: snapshot()});

    await nextAndWait(5, 'comparison decision pause');
    if (paused[4].blockType !== 'logic_compare' || paused[4].kind !== 'compare')
      throw new Error('comparison semantic boundary mismatch: ' + JSON.stringify(paused[4]));
    if (wwiTx.length !== txStart + 2) throw new Error('comparison boundary emitted backend action');
    await report('STEP_COMPARE_HELD', paused[4]);

    await nextAndWait(6, 'if decision pause');
    if (paused[5].blockType !== 'controls_if' || paused[5].kind !== 'if')
      throw new Error('if decision boundary mismatch: ' + JSON.stringify(paused[5]));
    if ('decision' in paused[5]) throw new Error('if condition result leaked into debug surface: ' + JSON.stringify(paused[5]));
    if (wwiTx.length !== txStart + 2) throw new Error('if decision boundary emitted backend action');
    await report('STEP_IF_HELD', paused[5]);

    await nextAndWait(7, 'chosen movement pause');
    if (paused[6].kind !== 'move' || paused[6].direction !== 'left')
      throw new Error('branch selection did not pause at chosen move: ' + JSON.stringify(paused[6]));
    if (wwiTx.length !== txStart + 2) throw new Error('chosen move started before its own Pas suivant');
    await report('SEMANTIC_DECISION_CHAIN_OK', {sensor: sensors[0], pauses: paused.slice(2, 7), snapshot: snapshot()});

    document.getElementById('stepContinue').click();
    await waitFor(() => document.getElementById('runtimeState').textContent === 'TERMINÉ', 'continued completion', 60000);
    if (paused.length !== 7) throw new Error('Continuer left additional semantic pauses: ' + JSON.stringify(paused));
    const runAst = asts[asts.length - 1];
    if (JSON.stringify(runAst) !== JSON.stringify(baselineAst)) throw new Error('executed step AST differs from baseline');
    await report('STEP_CONTINUE_DONE', {ast: runAst, snapshot: snapshot()});
    await report('STEP_SCENARIO_DONE', snapshot());
    await chain;
    console.log('WEBEEBLOCKS_CI_OBSERVABILITY_STEP_DONE');
  } catch (error) {
    await report('ERROR', error && error.stack ? error.stack : String(error));
    await report('FINAL_DIAG', snapshot());
    await chain;
    console.error('WEBEEBLOCKS_CI_OBSERVABILITY_STEP_ERROR=' + (error && error.stack ? error.stack : String(error)));
  }
})();
</script>
'''

UNSAFE = r'''
<script>
(async function() {
__COMMON__
  const diagnostics = [];
  window.addEventListener('webeeblocks-runtime-v2-diagnostic', event => {
    diagnostics.push(event.detail); report('DIAGNOSTIC', event.detail);
  });
  try {
    await waitFor(() => window.workspace && window.runtimeBackend && runtimeBackend.ready === true,
      'Runtime v2 READY', 20000);
    if (!runtimeBackend.capabilities || runtimeBackend.capabilities.simulationDebug !== true)
      throw new Error('simulation-only debug capability missing');
    loadXml(__BLOCKED__);
    document.getElementById('stepMode').checked = false;
    const startDiagnostics = diagnostics.length;
    window.runProgram();
    await waitFor(() => document.getElementById('runtimeState').textContent === 'ARRÊTÉ', 'neutral safety stop', 45000);
    const detail = document.getElementById('runtimeDetail').textContent;
    if (detail !== 'L’action n’a pas pu être terminée')
      throw new Error('unsafe student detail mismatch: ' + detail);
    if (detail.includes('UNSAFE_OR_TIMEOUT')) throw new Error('machine code leaked to student status');
    if (diagnostics.length !== startDiagnostics + 1)
      throw new Error('missing diagnostic event: ' + JSON.stringify(diagnostics));
    const unsafe = diagnostics[diagnostics.length - 1];
    if (unsafe.studentState !== 'ARRÊTÉ' || unsafe.machineCode !== 'UNSAFE_OR_TIMEOUT')
      throw new Error('low-level safety code not preserved: ' + JSON.stringify(unsafe));
    const surface = [detail, document.getElementById('debugState').textContent].join(' ').toLowerCase();
    ['mur', 'obstacle', 'utilise ', 'essaie ', 'condition vraie', 'condition fausse', 'bloc conseillé', 'solution'].forEach(term => {
      if (surface.includes(term)) throw new Error('anti-tutoring boundary crossed: ' + term);
    });
    await report('UNSAFE_SCENARIO_DONE', {diagnostic: unsafe, snapshot: snapshot()});
    await chain;
    console.log('WEBEEBLOCKS_CI_OBSERVABILITY_UNSAFE_DONE');
  } catch (error) {
    await report('ERROR', error && error.stack ? error.stack : String(error));
    await report('FINAL_DIAG', snapshot());
    await chain;
    console.error('WEBEEBLOCKS_CI_OBSERVABILITY_UNSAFE_ERROR=' + (error && error.stack ? error.stack : String(error)));
  }
})();
</script>
'''

def render(template: str) -> str:
    return (template.replace('__COMMON__', COMMON)
            .replace('__REACTIVE__', json.dumps(REACTIVE))
            .replace('__BLOCKED__', json.dumps(BLOCKED)))

parser = argparse.ArgumentParser()
parser.add_argument('--mode', choices=('step', 'unsafe'), required=True)
args = parser.parse_args()
base = HTML.read_text(encoding='utf-8').split(MARKER, 1)[0].rstrip()
harness = render(STEP if args.mode == 'step' else UNSAFE)
HTML.write_text(base + '\n' + MARKER + '\n' + harness + '\n', encoding='utf-8')
print('Prepared Runtime v2 observability harness mode=' + args.mode)
