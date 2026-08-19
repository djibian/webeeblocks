#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
html_path = ROOT / 'plugins/robot_windows/blockly/blockly.html'
fixture_path = ROOT / 'controllers/Blockly_Programs/CrazyflieL.xml'
html = html_path.read_text(encoding='utf-8')
fixture = fixture_path.read_text(encoding='utf-8')

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
    const payload = {seq: reportSequence++, event: event, detail: detail === undefined ? null : String(detail)};
    reportChain = reportChain.then(() => fetch('http://127.0.0.1:8765/event', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    }));
    return reportChain;
  }

  try {
    const responses = [];
    let stateWhenBusy = null;
    let stateWhenDone = null;
    window.addEventListener('webeeblocks-wwi', event => {
      const value = String(event.detail);
      responses.push(value);
      report('RX', value);
      if (value === 'WEBEEBLOCKS_MISSION_V1 ERR BUSY') {
        stateWhenBusy = crazyflieRuntimeState;
        report('STATE_AFTER_BUSY', stateWhenBusy);
      } else if (value === 'WEBEEBLOCKS_MISSION_V1 DONE') {
        stateWhenDone = crazyflieRuntimeState;
        report('STATE_AFTER_DONE', stateWhenDone);
      }
      console.log('WEBEEBLOCKS_CI_WWI_RX=' + value);
    });

    await waitFor(() => window.robotWindow && typeof window.robotWindow.send === 'function', 'RobotWindow transport', 15000);
    await waitFor(() => typeof workspace !== 'undefined' && workspace, 'Blockly workspace', 5000);
    await report('READY', crazyflieRuntimeState);

    const xmlText = __FIXTURE__;
    workspace.clear();
    Blockly.Xml.domToWorkspace(Blockly.Xml.textToDom(xmlText), workspace);
    const validMessage = WebeeBlocksCrazyflie.workspaceToMissionMessage(workspace);
    await report('MISSION', validMessage.replace(/\n/g, '|'));

    async function sendAndExpect(label, message, expected) {
      const before = responses.length;
      await report(label, message.replace(/\n/g, '|'));
      window.robotWindow.send(message);
      await waitFor(() => responses.slice(before).indexOf(expected) !== -1, expected, 5000);
    }

    await sendAndExpect('TX_NEGATIVE_VERSION', 'WEBEEBLOCKS_MISSION_V0\nTAKEOFF 1', 'WEBEEBLOCKS_MISSION_V1 ERR VERSION');
    await sendAndExpect('TX_NEGATIVE_COMMAND', 'WEBEEBLOCKS_MISSION_V1\nTAKEOFF 1\nSPIN 1\nLAND 0', 'WEBEEBLOCKS_MISSION_V1 ERR COMMAND');
    await sendAndExpect('TX_NEGATIVE_PARAMETER', 'WEBEEBLOCKS_MISSION_V1\nTAKEOFF 1\nFORWARD 0.05\nLAND 0', 'WEBEEBLOCKS_MISSION_V1 ERR PARAMETER');
    await sendAndExpect('TX_NEGATIVE_SEQUENCE', 'WEBEEBLOCKS_MISSION_V1\nFORWARD 1\nTURN 1.5707963267948966\nLAND 0', 'WEBEEBLOCKS_MISSION_V1 ERR SEQUENCE');
    await sendAndExpect('TX_NEGATIVE_TOO_LONG', 'WEBEEBLOCKS_MISSION_V1\nTAKEOFF 1\nFORWARD 1\nTURN 1.5707963267948966\nFORWARD 1\nTURN 1.5707963267948966\nFORWARD 1\nLAND 0', 'WEBEEBLOCKS_MISSION_V1 ERR TOO_LONG');

    const realSend = window.robotWindow.send.bind(window.robotWindow);
    let uiTransportSends = 0;
    window.robotWindow.send = function(message) {
      uiTransportSends += 1;
      return realSend(message);
    };

    const ackBefore = responses.length;
    await report('SUBMIT_CLICK', crazyflieRuntimeState);
    document.getElementById('submit').click();
    if (crazyflieRuntimeState !== 'PENDING')
      throw new Error('Submit did not synchronously enter PENDING');
    if (uiTransportSends !== 1)
      throw new Error('first Submit did not send exactly one runtime mission');
    await report('STATE_AFTER_SUBMIT', crazyflieRuntimeState);
    await waitFor(() => responses.slice(ackBefore).indexOf('WEBEEBLOCKS_MISSION_V1 ACK') !== -1, 'runtime ACK', 5000);
    if (crazyflieRuntimeState !== 'RUNNING')
      throw new Error('ACK did not enter RUNNING');
    await report('STATE_AFTER_ACK', crazyflieRuntimeState);

    await report('SECOND_SUBMIT_CLICK', crazyflieRuntimeState);
    document.getElementById('submit').click();
    if (uiTransportSends !== 1 || crazyflieRuntimeState !== 'RUNNING')
      throw new Error('second UI Submit was not blocked locally');
    await report('SECOND_SUBMIT_BLOCKED_LOCAL', crazyflieRuntimeState);

    const busyBefore = responses.length;
    await report('BUSY_PROBE_SEND', 'runtime transport direct');
    realSend(validMessage);
    await waitFor(() => responses.slice(busyBefore).indexOf('WEBEEBLOCKS_MISSION_V1 ERR BUSY') !== -1, 'BUSY rejection', 5000);
    if (stateWhenBusy !== 'RUNNING')
      throw new Error('BUSY response did not preserve RUNNING at its event boundary');

    await waitFor(() => responses.indexOf('WEBEEBLOCKS_MISSION_V1 DONE') !== -1, 'mission DONE', 70000);
    if (stateWhenDone !== 'WAITING')
      throw new Error('DONE did not return UI to WAITING at its event boundary');
    await reportChain;
    console.log('WEBEEBLOCKS_CI_RUNTIME_WWI_DONE');
  } catch (error) {
    await report('ERROR', error && error.stack ? error.stack : String(error));
    await reportChain;
    console.error('WEBEEBLOCKS_CI_RUNTIME_WWI_ERROR=' + error.stack);
  }
})();
</script>
'''.replace('__FIXTURE__', json.dumps(fixture))

html_path.write_text(html + '\n' + script, encoding='utf-8')
print('Prepared Blockly Robot Window runtime WWI harness.')