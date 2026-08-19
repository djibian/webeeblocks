#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
html_path = ROOT / 'plugins/robot_windows/blockly/blockly.html'
html = html_path.read_text(encoding='utf-8')
fixtures = {
    'direct': (ROOT / 'controllers/Blockly_Programs/CrazyflieDirect.xml').read_text(encoding='utf-8'),
    'detour': (ROOT / 'controllers/Blockly_Programs/CrazyflieL.xml').read_text(encoding='utf-8'),
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

  // Programmatic XML loading is not a student edit. Nudge one real numeric
  // Blockly field and restore it immediately so the product change listener is
  // exercised while the serialized mission remains exactly the fixture.
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
      report('EDIT_NUDGE', JSON.stringify({block: block.type, field: fieldName, from: original, to: original + delta}));
      field.setValue(original + delta);
      field.setValue(original);
      return true;
    }
    return false;
  }

  async function runMission(name, xmlText, expectedResult) {
    await waitFor(() => crazyflieRuntimeState === 'WAITING', name + ' runtime WAITING', 8000);
    const terminalBeforeEdit = webeeblocksChallengeState === 'FINISHED';
    loadFixture(xmlText);
    if (terminalBeforeEdit && !simulateStudentEdit())
      throw new Error(name + ' fixture has no editable numeric field');
    await waitFor(() => panel().state === 'PRÊT', name + ' PRÊT after edit', 2000);
    if (terminalBeforeEdit)
      await report(name + '_EDIT_READY', JSON.stringify(panel()));
    const beforeChallenge = challengeEvents.length;
    const beforeResponses = responses.length;
    await report(name + '_BEFORE_SUBMIT', JSON.stringify(panel()));
    document.getElementById('submit').click();
    await waitFor(() => responses.slice(beforeResponses).indexOf('WEBEEBLOCKS_MISSION_V1 ACK') !== -1, name + ' ACK', 5000);
    await waitFor(() => challengeEvents.slice(beforeChallenge).some(e => e.state === 'RUNNING'), name + ' EN VOL', 5000);
    if (panel().state !== 'EN VOL')
      throw new Error(name + ' did not display EN VOL');
    await waitFor(() => challengeEvents.slice(beforeChallenge).some(e => e.state === 'FINISHED' && e.result === expectedResult), name + ' result ' + expectedResult, 70000);
    await waitFor(() => responses.slice(beforeResponses).indexOf('WEBEEBLOCKS_MISSION_V1 DONE') !== -1, name + ' DONE', 5000);
    const frozen = panel();
    if (frozen.state !== 'TERMINÉ' || frozen.result !== expectedResult || !/^[0-9]+\.[0-9]{2} s$/.test(frozen.time))
      throw new Error(name + ' terminal panel invalid: ' + JSON.stringify(frozen));
    const frozenTime = frozen.time;
    await sleep(350);
    if (panel().time !== frozenTime)
      throw new Error(name + ' timer did not remain frozen');
    await report(name + '_TERMINAL', JSON.stringify(panel()));
    // Give the controller enough real time to restore __init__ and enter its
    // next WAITING loop before the next human-like edit/submit action.
    await sleep(750);
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
    await runMission('GATE_MISS', __GATE_MISS__, 'PASSAGE MANQUÉ');

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
