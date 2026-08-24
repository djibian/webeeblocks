#!/usr/bin/env python3
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
html_path = ROOT / 'plugins/robot_windows/blockly_v2/blockly_v2.html'
fixture = (ROOT / 'controllers/Blockly_Programs/CrazyflieReactiveV2.xml').read_text(encoding='utf-8')
html = html_path.read_text(encoding='utf-8')

seam = '  <script src="project_ui.js"></script>\n'
if seam not in html:
    raise SystemExit('project_ui.js seam not found')

fake_api = r'''
  <script>
  window.__webeeblocksCiRealFileApi = {
    open: typeof window.showOpenFilePicker === 'function',
    save: typeof window.showSaveFilePicker === 'function',
    secureContext: window.isSecureContext === true
  };
  window.__webeeblocksCiFileStore = {bytes: '', writes: 0, names: [], handle: null};
  window.__webeeblocksCiFileStore.handle = {
    name: 'ci-roundtrip.webeeblocks.json',
    async createWritable() {
      return {
        async write(text) {
          window.__webeeblocksCiFileStore.bytes = String(text);
          window.__webeeblocksCiFileStore.writes += 1;
          window.__webeeblocksCiFileStore.names.push('ci-roundtrip.webeeblocks.json');
        },
        async close() {}
      };
    },
    async getFile() {
      return {name: this.name, text: async () => window.__webeeblocksCiFileStore.bytes};
    }
  };
  window.showSaveFilePicker = async function() { return window.__webeeblocksCiFileStore.handle; };
  window.showOpenFilePicker = async function() { return [window.__webeeblocksCiFileStore.handle]; };
  </script>
'''

harness = r'''
  <script>
  (function() {
    function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }
    let seq = 0;
    let reportChain = Promise.resolve();
    function report(event, detail) {
      const payload = {seq: seq++, event, detail: detail === undefined ? null : detail, wall_ms: Date.now()};
      reportChain = reportChain.then(() => fetch('http://127.0.0.1:8765/event', {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
      }));
      return reportChain;
    }
    async function waitFor(predicate, label, timeoutMs) {
      const start = Date.now();
      while (Date.now() - start < timeoutMs) {
        if (predicate()) return;
        await sleep(25);
      }
      throw new Error('timeout waiting for ' + label);
    }
    function currentAst() { return WebeeBlocksSemanticAst.compileWorkspace(workspace); }
    function same(left, right) { return JSON.stringify(left) === JSON.stringify(right); }
    function click(id) { document.getElementById(id).click(); }
    function firstMove() { return workspace.getBlocksByType('webeeblocks_v2_move', false)[0]; }
    async function expectOpenError(bytes, expectedAst, writes, label) {
      window.__webeeblocksCiFileStore.bytes = bytes;
      click('projectOpen');
      await waitFor(() => document.getElementById('projectFileState').dataset.error === 'true', label + ' error', 3000);
      if (!same(currentAst(), expectedAst)) throw new Error(label + ' replaced current valid AST');
      if (window.__webeeblocksCiFileStore.writes !== writes) throw new Error(label + ' caused write');
      document.getElementById('projectFileState').dataset.error = 'false';
    }

    window.addEventListener('error', e => report('WINDOW_ERROR', {message:e.message, filename:e.filename, lineno:e.lineno}));
    window.addEventListener('unhandledrejection', e => report('UNHANDLED_REJECTION', String(e.reason)));

    window.addEventListener('load', async function() {
      try {
        await waitFor(() => window.workspace && window.WebeeBlocksProjectManager, 'project manager', 10000);
        await report('FILE_API_BOUNDARY', window.__webeeblocksCiRealFileApi);
        if (String(Blockly.VERSION) !== '13.2.1') throw new Error('unexpected Blockly version ' + Blockly.VERSION);
        if (!document.getElementById('projectOpen') || !document.getElementById('projectSave') || !document.getElementById('projectSaveAs'))
          throw new Error('manual project buttons missing');

        workspace.clear();
        Blockly.Xml.domToWorkspace(Blockly.utils.xml.textToDom(__FIXTURE__), workspace);
        const initialAst = currentAst();
        await report('INITIAL_AST', initialAst);

        click('projectSaveAs');
        await waitFor(() => window.__webeeblocksCiFileStore.writes === 1, 'Save As write', 3000);
        const savedBytes = window.__webeeblocksCiFileStore.bytes;
        const savedObject = JSON.parse(savedBytes);
        if (JSON.stringify(Object.keys(savedObject).sort()) !== JSON.stringify(['activity','format','version','workspace']))
          throw new Error('unexpected project root fields');
        if (savedObject.format !== 'webeeblocks-project' || savedObject.version !== 1)
          throw new Error('unexpected project format/version');
        if (savedObject.activity.id !== 'reactive-obstacle-v2' || savedObject.activity.semantics !== 'webeeblocks-ast-v1')
          throw new Error('unexpected activity compatibility fields');
        for (const forbidden of ['identity','attempt','result','score','debug','progress','history']) {
          if (savedBytes.toLowerCase().includes('"' + forbidden)) throw new Error('forbidden stored field ' + forbidden);
        }
        await report('SAVE_AS_OK', {bytes:savedBytes.length, writes:1});

        firstMove().setFieldValue('0.8', 'DISTANCE');
        await sleep(150);
        if (window.__webeeblocksCiFileStore.writes !== 1) throw new Error('workspace edit triggered persistence write');
        await report('EDIT_NO_WRITE_OK', {writes:window.__webeeblocksCiFileStore.writes});

        window.__webeeblocksCiFileStore.bytes = savedBytes;
        click('projectOpen');
        await waitFor(() => same(currentAst(), initialAst), 'Open AST restoration', 3000);
        if (window.__webeeblocksCiFileStore.writes !== 1) throw new Error('Open triggered persistence write');
        await report('OPEN_ROUNDTRIP_OK', currentAst());

        firstMove().setFieldValue('0.7', 'DISTANCE');
        const editedAst = currentAst();
        click('projectSave');
        await waitFor(() => window.__webeeblocksCiFileStore.writes === 2, 'explicit Save write', 3000);
        const editedBytes = window.__webeeblocksCiFileStore.bytes;
        firstMove().setFieldValue('0.4', 'DISTANCE');
        window.__webeeblocksCiFileStore.bytes = editedBytes;
        click('projectOpen');
        await waitFor(() => same(currentAst(), editedAst), 'edited Save AST restoration', 3000);
        await report('SAVE_UPDATE_OK', {writes:window.__webeeblocksCiFileStore.writes, ast:currentAst()});

        const stableAst = currentAst();
        const stableWrites = window.__webeeblocksCiFileStore.writes;
        await expectOpenError('{bad json', stableAst, stableWrites, 'malformed');
        const unsupported = JSON.parse(editedBytes); unsupported.version = 999;
        await expectOpenError(JSON.stringify(unsupported), stableAst, stableWrites, 'version');
        const incompatible = JSON.parse(editedBytes); incompatible.activity.id = 'unknown-profile';
        await expectOpenError(JSON.stringify(incompatible), stableAst, stableWrites, 'activity');
        const forbidden = JSON.parse(editedBytes); forbidden.history = [{score:1}];
        await expectOpenError(JSON.stringify(forbidden), stableAst, stableWrites, 'history');
        await report('FAIL_CLOSED_OK', {writes:window.__webeeblocksCiFileStore.writes, ast:currentAst()});

        // Execution/debug state changes are not persistence triggers: only explicit file actions above wrote.
        window.dispatchEvent(new CustomEvent('webeeblocks-runtime-v2', {detail:{state:'EN VOL'}}));
        window.dispatchEvent(new CustomEvent('webeeblocks-debug-active', {detail:{blockId:'ci'}}));
        await sleep(100);
        if (window.__webeeblocksCiFileStore.writes !== stableWrites)
          throw new Error('runtime/debug event triggered persistence write');
        await report('RUN_DEBUG_NO_WRITE_OK', {writes:window.__webeeblocksCiFileStore.writes});
        await report('PROJECT_FILES_TEST_COMPLETE', {ast:currentAst(), fileApi:window.__webeeblocksCiRealFileApi});
      } catch (error) {
        await report('ERROR', error && error.stack ? error.stack : String(error));
      }
    });
  })();
  </script>
'''.replace('__FIXTURE__', json.dumps(fixture))

html = html.replace(seam, fake_api + seam + harness, 1)
html_path.write_text(html, encoding='utf-8')
