#!/usr/bin/env python3
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
html_path = ROOT / 'plugins/robot_windows/blockly_v2/blockly_v2.html'
fixture = (ROOT / 'controllers/Blockly_Programs/CrazyflieReactiveV2.xml').read_text(encoding='utf-8')
simple_run = '''<xml xmlns="https://developers.google.com/blockly/xml">
  <block type="webeeblocks_v2_takeoff" id="ci_project_takeoff" x="40" y="40">
    <field name="HEIGHT">0.5</field>
    <next><block type="webeeblocks_v2_land" id="ci_project_land"></block></next>
  </block>
</xml>'''
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
  window.__webeeblocksCiPickerOptions = [];
  function validatePickerOptions(options) {
    if (!options || !Array.isArray(options.types) || options.types.length === 0)
      throw new TypeError('missing picker types');
    options.types.forEach(function(type) {
      Object.keys(type.accept || {}).forEach(function(mime) {
        if (!/^[^/]+\\/[^/]+$/.test(mime)) throw new TypeError('invalid picker MIME type');
        type.accept[mime].forEach(function(extension) {
          if (typeof extension !== 'string' || extension[0] !== '.' || extension.length < 2 ||
              Array.from(extension).length > 16 || /[\\\\/:*?"<>|]/.test(extension.slice(1)))
            throw new TypeError('invalid picker extension: ' + extension);
        });
      });
    });
  }
  (function proveOldSuffixRejected() {
    var rejected = false;
    try {
      validatePickerOptions({types:[{accept:{'application/json':['.webeeblocks.json']}}]});
    } catch (error) {
      rejected = error instanceof TypeError;
    }
    if (!rejected) throw new Error('old compound picker suffix was not rejected');
  })();
  window.showSaveFilePicker = async function(options) {
    validatePickerOptions(options);
    if (!String(options.suggestedName || '').endsWith('.webeeblocks.json'))
      throw new TypeError('full WebeeBlocks suggested name missing');
    window.__webeeblocksCiPickerOptions.push({kind:'save', options:options});
    return window.__webeeblocksCiFileStore.handle;
  };
  window.showOpenFilePicker = async function(options) {
    validatePickerOptions(options);
    window.__webeeblocksCiPickerOptions.push({kind:'open', options:options});
    return [window.__webeeblocksCiFileStore.handle];
  };
  </script>
'''

harness = r'''
  <script>
  (function() {
    function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }
    let seq = 0;
    let reportChain = Promise.resolve();
    let debugPauseCount = 0;
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
    function loadXml(xml) {
      workspace.clear();
      Blockly.Xml.domToWorkspace(Blockly.utils.xml.textToDom(xml), workspace);
    }
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
    window.addEventListener('webeeblocks-debug-paused', () => { debugPauseCount += 1; });

    window.addEventListener('load', async function() {
      try {
        await waitFor(() => window.workspace && window.WebeeBlocksProjectManager, 'project manager', 10000);
        await report('FILE_API_BOUNDARY', window.__webeeblocksCiRealFileApi);
        if (String(Blockly.VERSION) !== '13.2.1') throw new Error('unexpected Blockly version ' + Blockly.VERSION);
        if (!document.getElementById('projectOpen') || !document.getElementById('projectSave') || !document.getElementById('projectSaveAs'))
          throw new Error('manual project buttons missing');
        if (document.body.dataset.projectFileMode !== 'native') throw new Error('R2025a project file mode is not native');

        loadXml(__FIXTURE__);
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
        if (window.__webeeblocksCiPickerOptions.length < 4)
          throw new Error('native picker options were not exercised on Save As/Open/Save/Open');
        for (const entry of window.__webeeblocksCiPickerOptions) {
          const extensions = entry.options.types[0].accept['application/json'];
          if (JSON.stringify(extensions) !== JSON.stringify(['.json']))
            throw new Error('unexpected native picker extensions ' + JSON.stringify(extensions));
        }
        await report('PICKER_OPTIONS_OK', window.__webeeblocksCiPickerOptions.map(entry => ({
          kind:entry.kind,
          extensions:entry.options.types[0].accept['application/json'],
          suggestedName:entry.options.suggestedName || null
        })));
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

        // Exercise the real Runtime v2 run path and the real #67 step controls.
        loadXml(__SIMPLE_RUN__);
        await waitFor(() => window.runtimeBackend && window.runtimeBackend.ready === true,
          'Runtime v2 ready before debug run', 15000);
        const writesBeforeRun = window.__webeeblocksCiFileStore.writes;
        document.getElementById('stepMode').checked = true;
        const runPromise = window.runProgram();
        await waitFor(() => debugPauseCount >= 1 && document.getElementById('stepNext').disabled === false,
          'first real debug pause', 5000);
        if (window.__webeeblocksCiFileStore.writes !== writesBeforeRun)
          throw new Error('starting real debug run triggered persistence write');
        click('stepNext');
        await waitFor(() => debugPauseCount >= 2 && document.getElementById('stepNext').disabled === false,
          'second real debug pause', 20000);
        if (window.__webeeblocksCiFileStore.writes !== writesBeforeRun)
          throw new Error('real Pas suivant triggered persistence write');
        click('stepContinue');
        await runPromise;
        if (document.getElementById('runtimeState').textContent !== 'TERMINÉ')
          throw new Error('real debug run did not complete');
        if (window.__webeeblocksCiFileStore.writes !== writesBeforeRun)
          throw new Error('real run/debug completion triggered persistence write');
        document.getElementById('stepMode').checked = false;
        await report('RUN_DEBUG_NO_WRITE_OK', {writes:window.__webeeblocksCiFileStore.writes, pauses:debugPauseCount});
        await report('PROJECT_FILES_TEST_COMPLETE', {ast:currentAst(), fileApi:window.__webeeblocksCiRealFileApi});
      } catch (error) {
        await report('ERROR', error && error.stack ? error.stack : String(error));
      }
    });
  })();
  </script>
'''.replace('__FIXTURE__', json.dumps(fixture)).replace('__SIMPLE_RUN__', json.dumps(simple_run))

html = html.replace(seam, fake_api + seam + harness, 1)
html_path.write_text(html, encoding='utf-8')
