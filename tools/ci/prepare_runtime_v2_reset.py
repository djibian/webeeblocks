#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = ROOT / 'plugins/robot_windows/blockly_v2/blockly_v2.html'
MARKER = '<!-- WEBEEBLOCKS_RESET_REPLAY_CI -->'

NORMAL = '''<xml xmlns="https://developers.google.com/blockly/xml">
  <block type="webeeblocks_v2_takeoff" id="reset_normal_takeoff" x="40" y="40">
    <field name="HEIGHT">0.5</field>
    <next>
      <block type="webeeblocks_v2_move" id="reset_normal_move">
        <field name="DIRECTION">forward</field>
        <field name="DISTANCE">0.2</field>
        <next><block type="webeeblocks_v2_land" id="reset_normal_land"></block></next>
      </block>
    </next>
  </block>
</xml>'''

BLOCKED = '''<xml xmlns="https://developers.google.com/blockly/xml">
  <block type="webeeblocks_v2_takeoff" id="reset_blocked_takeoff" x="40" y="40">
    <field name="HEIGHT">0.5</field>
    <next>
      <block type="webeeblocks_v2_move" id="reset_blocked_move">
        <field name="DIRECTION">forward</field>
        <field name="DISTANCE">2</field>
        <next><block type="webeeblocks_v2_land" id="reset_blocked_land"></block></next>
      </block>
    </next>
  </block>
</xml>'''

SCRIPT = r'''
<script>
(async function() {
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
      submitDisabled: document.getElementById('submit') && document.getElementById('submit').disabled,
      resetHidden: document.getElementById('resetSimulation') && document.getElementById('resetSimulation').hidden,
      resetDisabled: document.getElementById('resetSimulation') && document.getElementById('resetSimulation').disabled,
      backendReady: window.runtimeBackend && runtimeBackend.ready,
      pending: window.runtimeBackend ? Object.keys(runtimeBackend.pending || {}).length : null,
      runtimeRunning: !!window.runtimeRunning,
      runtimeTerminal: !!window.runtimeTerminal,
      runtimeResetPending: !!window.runtimeResetPending
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
  function workspaceState() {
    return JSON.stringify(Blockly.serialization.workspaces.save(workspace));
  }
  function astState() {
    return JSON.stringify(WebeeBlocksSemanticAst.compileWorkspace(workspace));
  }
  async function clickResetAndProve(label, expectedWorkspace, expectedAst) {
    const button = document.getElementById('resetSimulation');
    if (button.hidden || button.disabled) throw new Error(label + ' reset action unavailable: ' + JSON.stringify(snapshot()));
    button.click();
    if (!button.disabled) throw new Error(label + ' reset action not gated while pending');
    await waitFor(() => document.getElementById('runtimeState').textContent === 'PRÊT', label + ' reset ready', 12000);
    if (!runtimeBackend.ready || Object.keys(runtimeBackend.pending || {}).length !== 0)
      throw new Error(label + ' backend not genuinely ready: ' + JSON.stringify(snapshot()));
    if (workspaceState() !== expectedWorkspace) throw new Error(label + ' workspace changed across reset');
    if (astState() !== expectedAst) throw new Error(label + ' AST changed across reset');
    if (runtimeProfile.id !== 'reactive-obstacle-v2') throw new Error(label + ' activity profile changed');
    if (document.getElementById('submit').disabled) throw new Error(label + ' run did not become available after reset');
    await report('RESET_OK', {label, workspace: expectedWorkspace, ast: JSON.parse(expectedAst), snapshot: snapshot()});
  }

  window.addEventListener('error', event => report('WINDOW_ERROR', {
    message: event.message, filename: event.filename, lineno: event.lineno, colno: event.colno
  }));
  window.addEventListener('unhandledrejection', event => report('UNHANDLED_REJECTION', String(event.reason)));
  window.addEventListener('webeeblocks-runtime-v2', event => report('STATE', event.detail));
  window.addEventListener('webeeblocks-runtime-v2-reset', event => report('RESET_EVENT', event.detail));

  try {
    await waitFor(() => window.workspace && window.runtimeBackend && runtimeBackend.ready === true,
      'Runtime v2 READY', 20000);
    if (!runtimeBackend.capabilities || runtimeBackend.capabilities.simulationReset !== true)
      throw new Error('simulation-only reset capability missing');
    if (document.getElementById('resetSimulation').hidden)
      throw new Error('Réinitialiser remained hidden in Webots simulation');
    await report('READY', snapshot());

    loadXml(__NORMAL__);
    const normalWorkspace = workspaceState();
    const normalAst = astState();
    document.getElementById('submit').click();
    await waitFor(() => document.getElementById('runtimeState').textContent === 'TERMINÉ', 'first normal completion', 45000);
    if (!document.getElementById('submit').disabled) throw new Error('rerun allowed without reset after TERMINÉ');
    await report('NORMAL_FIRST_DONE', {workspace: normalWorkspace, ast: JSON.parse(normalAst), snapshot: snapshot()});
    await clickResetAndProve('after-terminated', normalWorkspace, normalAst);

    document.getElementById('submit').click();
    await waitFor(() => document.getElementById('runtimeState').textContent === 'TERMINÉ', 'second normal completion', 45000);
    if (workspaceState() !== normalWorkspace || astState() !== normalAst)
      throw new Error('normal replay changed workspace or AST');
    await report('NORMAL_REPLAY_DONE', {workspace: normalWorkspace, ast: JSON.parse(normalAst), snapshot: snapshot()});
    await clickResetAndProve('before-unsafe', normalWorkspace, normalAst);

    loadXml(__BLOCKED__);
    const blockedWorkspace = workspaceState();
    const blockedAst = astState();
    document.getElementById('submit').click();
    await waitFor(() => document.getElementById('runtimeState').textContent === 'ARRÊTÉ', 'first unsafe stop', 45000);
    await report('UNSAFE_FIRST_DONE', {workspace: blockedWorkspace, ast: JSON.parse(blockedAst), snapshot: snapshot()});
    await clickResetAndProve('after-stopped', blockedWorkspace, blockedAst);

    document.getElementById('submit').click();
    await waitFor(() => document.getElementById('runtimeState').textContent === 'ARRÊTÉ', 'second unsafe stop', 45000);
    if (workspaceState() !== blockedWorkspace || astState() !== blockedAst)
      throw new Error('unsafe replay changed workspace or AST');
    await report('UNSAFE_REPLAY_DONE', {workspace: blockedWorkspace, ast: JSON.parse(blockedAst), snapshot: snapshot()});
    await chain;
    console.log('WEBEEBLOCKS_CI_RESET_REPLAY_DONE');
  } catch (error) {
    await report('ERROR', error && error.stack ? error.stack : String(error));
    await report('FINAL_DIAG', snapshot());
    await chain;
    console.error('WEBEEBLOCKS_CI_RESET_REPLAY_ERROR=' + (error && error.stack ? error.stack : String(error)));
  }
})();
</script>
'''

base = HTML.read_text(encoding='utf-8').split(MARKER, 1)[0].rstrip()
script = SCRIPT.replace('__NORMAL__', json.dumps(NORMAL)).replace('__BLOCKED__', json.dumps(BLOCKED))
if '</body>' not in base:
    raise SystemExit('blockly_v2.html missing </body>')
HTML.write_text(base.replace('</body>', f'{MARKER}\n{script}\n</body>') + '\n', encoding='utf-8')
print('PREPARED_RUNTIME_V2_RESET_REPLAY')
