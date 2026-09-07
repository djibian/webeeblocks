#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
html_path = ROOT / 'plugins/robot_windows/blockly/blockly.html'
html = html_path.read_text(encoding='utf-8')
fixtures = {
    'direct': (ROOT / 'controllers/Blockly_Programs/CrazyflieDirect.xml').read_text(encoding='utf-8'),
    'detour': (ROOT / 'controllers/Blockly_Programs/CrazyflieDetourOffset.xml').read_text(encoding='utf-8'),
    'gate_miss': (ROOT / 'controllers/Blockly_Programs/CrazyflieGateMiss.xml').read_text(encoding='utf-8'),
}

script = r'''
<script>
(async function() {
  function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }
  async function waitFor(predicate, label, timeoutMs) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      if (predicate()) return;
      await sleep(25);
    }
    throw new Error('timeout waiting for ' + label);
  }

  let reportSequence = 0;
  let reportChain = Promise.resolve();
  function report(event, detail) {
    const payload = {
      seq: reportSequence++,
      wall_ms: Date.now(),
      performance_ms: typeof performance !== 'undefined' ? performance.now() : null,
      event: event,
      detail: detail === undefined ? null : String(detail),
    };
    reportChain = reportChain.then(() => fetch('http://127.0.0.1:8765/event', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    }));
    return reportChain;
  }

  const responses = [];
  const challengeEvents = [];
  const javascriptErrors = [];
  window.addEventListener('error', event => {
    const detail = event && (event.error || event.message) ? String(event.error || event.message) : 'unknown error';
    javascriptErrors.push(detail);
    report('JS_ERROR', detail);
  });
  window.addEventListener('unhandledrejection', event => {
    const detail = event && event.reason ? String(event.reason) : 'unknown rejection';
    javascriptErrors.push(detail);
    report('JS_REJECTION', detail);
  });
  window.addEventListener('webeeblocks-wwi', event => {
    const value = String(event.detail);
    responses.push(value);
    report('RX', value);
  });
  window.addEventListener('webeeblocks-challenge', event => {
    const d = event.detail || {};
    const entry = {state: d.state, result: d.result, elapsed: d.elapsed};
    challengeEvents.push(entry);
    report('CHALLENGE', JSON.stringify(entry));
  });

  function panel() {
    return {
      state: document.getElementById('webeeblocksChallengeState').textContent,
      result: document.getElementById('webeeblocksChallengeResult').textContent,
      time: document.getElementById('webeeblocksChallengeTime').textContent,
    };
  }

  function loadFixture(xmlText) {
    workspace.clear();
    Blockly.Xml.domToWorkspace(Blockly.Xml.textToDom(xmlText), workspace);
  }

  // Direct Field.setValue() is silent in this vendored Blockly 2020 path.
  // Construct the same standard field-change event a real edit produces and
  // deliver it through Workspace.fireChangeListener(), the public listener
  // boundary used by Blockly.Events. Restore the numeric field silently afterwards.
  function simulateStudentEdit() {
    const blocks = workspace.getAllBlocks(false);
    for (let i = 0; i < blocks.length; ++i) {
      const block = blocks[i];
      const fieldName = block.getField('DISTANCE') ? 'DISTANCE' : (block.getField('ANGLE') ? 'ANGLE' : null);
      if (!fieldName)
        continue;
      const field = block.getField(fieldName);
      const original = Number(field.getValue());
      const delta = fieldName === 'DISTANCE' ? (original >= 1.9 ? -0.1 : 0.1) : (original >= 134 ? -1 : 1);
      const edited = original + delta;
      report('EDIT_NUDGE', JSON.stringify({block: block.type, field: fieldName, from: original, to: edited,
                                           runtimeState: crazyflieRuntimeState}));
      field.setValue(edited);
      const change = new Blockly.Events.Change(block, 'field', fieldName, String(original), String(edited));
      workspace.fireChangeListener(change);
      field.setValue(original);
      return true;
    }
    return false;
  }

  async function prepareNextMission(name, xmlText) {
    const terminalBeforeEdit = webeeblocksChallengeState === 'FINISHED';
    if (terminalBeforeEdit) {
      // Edit immediately while the controller may still be RECOVERING. The
      // challenge presentation may become PRÊT, but transport must remain blocked.
      if (!simulateStudentEdit())
        throw new Error(name + ' previous workspace has no editable numeric field');
      await waitFor(() => panel().state === 'PRÊT', name + ' PRÊT after edit', 2000);
      await report(name + '_EDIT_READY', JSON.stringify({panel: panel(), runtimeState: crazyflieRuntimeState}));
    }

    loadFixture(xmlText);
    await report(name + '_FIXTURE_LOADED', JSON.stringify({panel: panel(), runtimeState: crazyflieRuntimeState}));

    if (crazyflieRuntimeState !== 'WAITING') {
      const responseStart = responses.length;
      await report(name + '_WAIT_RUNTIME_READY', crazyflieRuntimeState);
      await waitFor(() => responses.slice(responseStart).indexOf('WEBEEBLOCKS_MISSION_V1 RUNTIME_READY') !== -1,
                    name + ' RUNTIME_READY', 8000);
      await waitFor(() => crazyflieRuntimeState === 'WAITING', name + ' runtime WAITING after RUNTIME_READY', 1000);
      await report(name + '_RUNTIME_READY', JSON.stringify({panel: panel(), runtimeState: crazyflieRuntimeState}));
    }

    if (javascriptErrors.some(e => e.indexOf('Generator code for block type') !== -1 || e.indexOf('generator') !== -1))
      throw new Error(name + ' Crazyflie edit invoked Python generation: ' + javascriptErrors.join(' | '));
  }

  async function runMission(name, xmlText, expectedResult) {
    await prepareNextMission(name, xmlText);
    const missionMessage = WebeeBlocksCrazyflie.workspaceToMissionMessage(workspace);
    await report(name + '_MISSION', missionMessage);
    const beforeChallenge = challengeEvents.length;
    const beforeResponses = responses.length;
    await report(name + '_BEFORE_SUBMIT', JSON.stringify({panel: panel(), runtimeState: crazyflieRuntimeState}));

    // Submit immediately once RUNTIME_READY has moved transport to WAITING. No
    // arbitrary real-time grace period is allowed between readiness and retry.
    document.getElementById('submit').click();
    await waitFor(() => responses.slice(beforeResponses).indexOf('WEBEEBLOCKS_MISSION_V1 ACK') !== -1, name + ' ACK', 5000);
    await waitFor(() => challengeEvents.slice(beforeChallenge).some(e => e.state === 'RUNNING'), name + ' EN VOL', 5000);
    if (panel().state !== 'EN VOL')
      throw new Error(name + ' did not display EN VOL');
    await waitFor(() => challengeEvents.slice(beforeChallenge).some(e => e.state === 'FINISHED' && e.result === expectedResult), name + ' result ' + expectedResult, 70000);
    await waitFor(() => responses.slice(beforeResponses).indexOf('WEBEEBLOCKS_MISSION_V1 DONE') !== -1, name + ' DONE', 5000);
    await waitFor(() => crazyflieRuntimeState === 'RECOVERING', name + ' transport RECOVERING', 1000);
    const runtimeStateAtTerminal = crazyflieRuntimeState;
    const frozen = panel();
    if (frozen.state !== 'TERMINÉ' || frozen.result !== expectedResult || !/^[0-9]+\.[0-9]{2} s$/.test(frozen.time))
      throw new Error(name + ' terminal panel invalid: ' + JSON.stringify(frozen));
    const frozenTime = frozen.time;
    await sleep(350);
    if (panel().time !== frozenTime)
      throw new Error(name + ' timer did not remain frozen');
    await report(name + '_TERMINAL', JSON.stringify({
      panel: panel(),
      runtimeStateAtTerminal: runtimeStateAtTerminal,
      runtimeStateAfterFreeze: crazyflieRuntimeState,
    }));
    return {responseStart: beforeResponses};
  }

  try {
    await waitFor(() => window.robotWindow && typeof window.robotWindow.send === 'function', 'RobotWindow transport', 15000);
    await waitFor(() => typeof workspace !== 'undefined' && workspace, 'Blockly workspace', 5000);
    workspace.addChangeListener(function(event) {
      const detail = {
        type: event && event.type,
        element: event && event.element,
        name: event && event.name,
        oldValue: event && event.oldValue,
        newValue: event && event.newValue,
        challengeState: webeeblocksChallengeState,
        runtimeState: crazyflieRuntimeState,
      };
      report('BLOCKLY_CHANGE', JSON.stringify(detail));
    });
    await waitFor(() => document.getElementById('webeeblocksChallengeState'), 'challenge panel', 5000);
    if (panel().state !== 'PRÊT' || panel().time !== '—')
      throw new Error('initial challenge presentation is not PRÊT');
    await report('INITIAL', JSON.stringify(panel()));

    // A rejected mission must never start the challenge timer.
    const invalidBeforeResponses = responses.length;
    const invalidBeforeChallenges = challengeEvents.length;
    window.robotWindow.send('WEBEEBLOCKS_MISSION_V1\nTAKEOFF 1\nFORWARD 0.05\nLAND 0');
    await waitFor(() => responses.slice(invalidBeforeResponses).indexOf('WEBEEBLOCKS_MISSION_V1 ERR PARAMETER') !== -1, 'invalid mission rejection', 5000);
    await sleep(250);
    if (challengeEvents.slice(invalidBeforeChallenges).some(e => e.state === 'RUNNING'))
      throw new Error('invalid mission started challenge timer');
    if (panel().state !== 'PRÊT' || panel().time !== '—')
      throw new Error('invalid mission changed challenge presentation');
    await report('INVALID_REJECTED_NO_TIMER', JSON.stringify(panel()));

    await runMission('DIRECT', __DIRECT__, 'COLLISION');
    await runMission('DETOUR', __DETOUR__, 'RÉUSSI');
    const gateMissRun = await runMission('GATE_MISS', __GATE_MISS__, 'PASSAGE MANQUÉ');

    // Even after the last attempt, prove the runtime physically rearmed and the
    // same Robot Window received the explicit readiness signal. Scan from the
    // final mission's pre-submit boundary because readiness may arrive while the
    // terminal timer is being verified as frozen.
    const finalResponseStart = gateMissRun.responseStart;
    await waitFor(() => responses.slice(finalResponseStart).indexOf('WEBEEBLOCKS_MISSION_V1 RUNTIME_READY') !== -1,
                  'final RUNTIME_READY', 8000);
    await waitFor(() => crazyflieRuntimeState === 'WAITING', 'final runtime WAITING', 1000);
    await report('FINAL_RUNTIME_READY', JSON.stringify({panel: panel(), runtimeState: crazyflieRuntimeState}));

    if (javascriptErrors.some(e => e.indexOf('Generator code for block type') !== -1 || e.indexOf('generator') !== -1))
      throw new Error('Crazyflie challenge triggered Python generation: ' + javascriptErrors.join(' | '));
    await report('CHALLENGE_TEST_COMPLETE', JSON.stringify(panel()));
    await reportChain;
  } catch (error) {
    await report('ERROR', error && error.stack ? error.stack : String(error));
    await reportChain;
  }
})();
</script>
'''.replace('__DIRECT__', json.dumps(fixtures['direct'])) \
   .replace('__DETOUR__', json.dumps(fixtures['detour'])) \
   .replace('__GATE_MISS__', json.dumps(fixtures['gate_miss']))

html_path.write_text(html + '\n' + script, encoding='utf-8')
print('Prepared same-session Crazyflie challenge UX harness.')
