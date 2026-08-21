#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
html_path = ROOT / 'plugins/robot_windows/blockly_v2/blockly_v2.html'
fixture = (ROOT / 'controllers/Blockly_Programs/CrazyflieReactiveV2.xml').read_text(encoding='utf-8')
html = html_path.read_text(encoding='utf-8')

script = r'''
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
  window.addEventListener('webeeblocks-runtime-v2-ast', event => report('AST', event.detail));
  window.addEventListener('webeeblocks-wwi', event => report('WWI_RX', String(event.detail)));

  try {
    await report('HARNESS_START', snapshot());
    await waitFor(() => window.workspace && window.runtimeBackend && document.getElementById('submit') && !document.getElementById('submit').disabled, 'Runtime v2 ready', 20000);
    await report('READY', runtimeBackend.capabilities);
    workspace.clear();
    Blockly.Xml.domToWorkspace(Blockly.Xml.textToDom(__FIXTURE__), workspace);
    const ast = WebeeBlocksSemanticAst.compileWorkspace(workspace);
    await report('FIXTURE_AST', ast);
    document.getElementById('submit').click();
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
print('Prepared Runtime v2 real Robot Window harness.')
