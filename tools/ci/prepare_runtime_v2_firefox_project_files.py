#!/usr/bin/env python3
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[2]
html_path = ROOT / 'plugins/robot_windows/blockly_v2/blockly_v2.html'
fixture = (ROOT / 'controllers/Blockly_Programs/CrazyflieReactiveV2.xml').read_text(encoding='utf-8')
html = html_path.read_text(encoding='utf-8')

seam_match = re.search(r'  <script src="project_ui\.js(?:\?[^\"]+)?"></script>\n', html)
if not seam_match:
    raise SystemExit('project_ui.js seam not found')
seam = seam_match.group(0)

harness = r'''
  <script>
  (function() {
    function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }
    let seq = 0;
    let reportChain = Promise.resolve();
    let captured = null;

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
    function same(left, right) { return JSON.stringify(left) === JSON.stringify(right); }
    function currentAst() { return WebeeBlocksSemanticAst.compileWorkspace(workspace); }
    function firstMove() { return workspace.getBlocksByType('webeeblocks_v2_move', false)[0]; }
    function loadXml(xml) {
      workspace.clear();
      Blockly.Xml.domToWorkspace(Blockly.utils.xml.textToDom(xml), workspace);
    }
    function click(id) { document.getElementById(id).click(); }
    function capture(method) {
      const manager = window.WebeeBlocksProjectManager;
      const original = manager[method].bind(manager);
      manager[method] = function() {
        const promise = original.apply(null, arguments);
        captured = {method, promise};
        promise.catch(function() {});
        return promise;
      };
    }
    async function clickAndAwait(button, method, expectError) {
      captured = null;
      click(button);
      await waitFor(() => captured && captured.method === method, method + ' invocation', 1000);
      let result = null;
      let failure = null;
      try { result = await captured.promise; }
      catch (error) { failure = error; }
      await sleep(50);
      if (expectError) {
        if (!failure) throw new Error(method + ' unexpectedly succeeded');
        return failure;
      }
      if (failure) throw failure;
      return result;
    }
    async function expectRejectedOpen(label, stableAst, stableTarget) {
      const error = await clickAndAwait('projectOpen', 'open', true);
      if (error && error.name === 'AbortError') throw new Error(label + ' was cancelled instead of rejected');
      if (!same(currentAst(), stableAst)) throw new Error(label + ' replaced current valid AST');
      if (window.WebeeBlocksProjectManager.currentName() !== stableTarget ||
          !window.WebeeBlocksProjectManager.hasCurrentTarget())
        throw new Error(label + ' replaced current file target');
      await report('INVALID_OPEN_REJECTED', {label, message:String(error && error.message || error)});
    }

    window.addEventListener('error', e => report('WINDOW_ERROR', {message:e.message, filename:e.filename, lineno:e.lineno}));
    window.addEventListener('unhandledrejection', e => report('UNHANDLED_REJECTION', String(e.reason)));

    window.addEventListener('load', async function() {
      try {
        await waitFor(() => window.workspace && window.WebeeBlocksProjectManager, 'Firefox project manager', 15000);
        if (!/Firefox\/155\.0\b/.test(navigator.userAgent))
          throw new Error('unexpected Firefox user agent ' + navigator.userAgent);
        if (typeof window.showOpenFilePicker === 'function' || typeof window.showSaveFilePicker === 'function')
          throw new Error('Firefox unexpectedly exposed File System Access; WWI broker path not exercised');
        if (document.body.dataset.projectFileMode !== 'wwi-native')
          throw new Error('Firefox project file mode is not wwi-native: ' + document.body.dataset.projectFileMode);
        if (document.getElementById('projectOpen').disabled || document.getElementById('projectSaveAs').disabled ||
            !document.getElementById('projectSave').disabled)
          throw new Error('initial project button state is not Open/SaveAs enabled and Save disabled');

        capture('open');
        capture('saveAs');
        capture('save');
        loadXml(__FIXTURE__);
        const initialAst = currentAst();
        await report('FIREFOX_BROKER_READY', {userAgent:navigator.userAgent, mode:document.body.dataset.projectFileMode, ast:initialAst});

        const saveAs = await clickAndAwait('projectSaveAs', 'saveAs', false);
        if (saveAs.name !== 'roundtrip.wbb') throw new Error('unexpected Save As name ' + saveAs.name);
        if (window.WebeeBlocksProjectManager.currentName() !== 'roundtrip.wbb' || document.getElementById('projectSave').disabled)
          throw new Error('Save target was not adopted after Save As');
        const stableState = document.getElementById('projectFileState').textContent;
        await report('FIREFOX_SAVE_AS_OK', {name:saveAs.name, ast:currentAst()});

        const saveCancel = await clickAndAwait('projectSaveAs', 'saveAs', true);
        if (!saveCancel || saveCancel.name !== 'AbortError') throw new Error('Save As cancellation was not AbortError');
        if (document.getElementById('projectFileState').textContent !== stableState ||
            window.WebeeBlocksProjectManager.currentName() !== 'roundtrip.wbb')
          throw new Error('Save As cancellation changed state/target');
        await report('FIREFOX_SAVE_AS_CANCEL_OK', {target:window.WebeeBlocksProjectManager.currentName()});

        const openCancel = await clickAndAwait('projectOpen', 'open', true);
        if (!openCancel || openCancel.name !== 'AbortError') throw new Error('Open cancellation was not AbortError');
        if (document.getElementById('projectFileState').textContent !== stableState ||
            window.WebeeBlocksProjectManager.currentName() !== 'roundtrip.wbb')
          throw new Error('Open cancellation changed state/target');
        await report('FIREFOX_OPEN_CANCEL_OK', {target:window.WebeeBlocksProjectManager.currentName()});

        firstMove().setFieldValue('0.8', 'DISTANCE');
        if (same(currentAst(), initialAst)) throw new Error('fixture edit did not change AST before Open');
        const opened = await clickAndAwait('projectOpen', 'open', false);
        if (opened.name !== 'roundtrip.wbb' || !same(currentAst(), initialAst))
          throw new Error('valid Firefox Open did not restore the saved project');
        await report('FIREFOX_OPEN_OK', {name:opened.name, ast:currentAst()});

        firstMove().setFieldValue('0.7', 'DISTANCE');
        const editedAst = currentAst();
        const saved = await clickAndAwait('projectSave', 'save', false);
        if (saved.name !== 'roundtrip.wbb' || window.WebeeBlocksProjectManager.currentName() !== 'roundtrip.wbb')
          throw new Error('same-file Save changed target/name');
        await report('FIREFOX_SAME_FILE_SAVE_OK', {name:saved.name, ast:editedAst});

        const stableTarget = window.WebeeBlocksProjectManager.currentName();
        await expectRejectedOpen('malformed', editedAst, stableTarget);
        await expectRejectedOpen('unsupported-version', editedAst, stableTarget);
        await expectRejectedOpen('unknown-activity', editedAst, stableTarget);

        firstMove().setFieldValue('0.6', 'DISTANCE');
        const finalAst = currentAst();
        const finalSave = await clickAndAwait('projectSave', 'save', false);
        if (finalSave.name !== 'roundtrip.wbb' || window.WebeeBlocksProjectManager.currentName() !== stableTarget)
          throw new Error('Save after rejected Open did not preserve exact target');
        await report('FIREFOX_TARGET_PRESERVED_OK', {name:finalSave.name, ast:finalAst});
        await report('FIREFOX_PROJECT_FILES_TEST_COMPLETE', {name:finalSave.name, mode:document.body.dataset.projectFileMode, ast:finalAst});
      } catch (error) {
        await report('ERROR', error && error.stack ? error.stack : String(error));
      }
    });
  })();
  </script>
'''.replace('__FIXTURE__', json.dumps(fixture))

html = html.replace(seam, seam + harness, 1)
html_path.write_text(html, encoding='utf-8')
