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

  const responses = [];
  window.addEventListener('webeeblocks-wwi', event => {
    responses.push(String(event.detail));
    console.log('WEBEEBLOCKS_CI_WWI_RX=' + event.detail);
  });

  await waitFor(() => window.robotWindow && typeof window.robotWindow.send === 'function', 'RobotWindow transport', 15000);
  await waitFor(() => typeof workspace !== 'undefined' && workspace, 'Blockly workspace', 5000);

  const xmlText = __FIXTURE__;
  workspace.clear();
  Blockly.Xml.domToWorkspace(Blockly.Xml.textToDom(xmlText), workspace);
  const validMessage = WebeeBlocksCrazyflie.workspaceToMissionMessage(workspace);
  console.log('WEBEEBLOCKS_CI_RUNTIME_MESSAGE=' + validMessage.replace(/\n/g, '|'));

  async function sendAndExpect(message, expected) {
    const before = responses.length;
    window.robotWindow.send(message);
    await waitFor(() => responses.slice(before).indexOf(expected) !== -1, expected, 5000);
  }

  await sendAndExpect('WEBEEBLOCKS_MISSION_V0\nTAKEOFF 1', 'WEBEEBLOCKS_MISSION_V1 ERR VERSION');
  await sendAndExpect('WEBEEBLOCKS_MISSION_V1\nTAKEOFF 1\nSPIN 1\nLAND 0', 'WEBEEBLOCKS_MISSION_V1 ERR COMMAND');
  await sendAndExpect('WEBEEBLOCKS_MISSION_V1\nTAKEOFF 1\nFORWARD 9\nTURN 1\nFORWARD 1\nLAND 0', 'WEBEEBLOCKS_MISSION_V1 ERR PARAMETER');
  await sendAndExpect('WEBEEBLOCKS_MISSION_V1\nTAKEOFF 1\nTURN 1\nFORWARD 1\nFORWARD 1\nLAND 0', 'WEBEEBLOCKS_MISSION_V1 ERR SEQUENCE');
  await sendAndExpect('WEBEEBLOCKS_MISSION_V1\nTAKEOFF 1\nFORWARD 1\nTURN 1\nFORWARD 1\nTURN 1\nLAND 0', 'WEBEEBLOCKS_MISSION_V1 ERR TOO_LONG');

  const ackBefore = responses.length;
  document.getElementById('submit').click();
  await waitFor(() => responses.slice(ackBefore).indexOf('WEBEEBLOCKS_MISSION_V1 ACK') !== -1, 'runtime ACK', 5000);

  const busyBefore = responses.length;
  window.robotWindow.send(validMessage);
  await waitFor(() => responses.slice(busyBefore).indexOf('WEBEEBLOCKS_MISSION_V1 ERR BUSY') !== -1, 'BUSY rejection', 5000);
  await waitFor(() => responses.indexOf('WEBEEBLOCKS_MISSION_V1 DONE') !== -1, 'mission DONE', 70000);
  console.log('WEBEEBLOCKS_CI_RUNTIME_WWI_DONE');
})().catch(error => console.error('WEBEEBLOCKS_CI_RUNTIME_WWI_ERROR=' + error.stack));
</script>
'''.replace('__FIXTURE__', json.dumps(fixture))

html_path.write_text(html + '\n' + script, encoding='utf-8')
print('Prepared Blockly Robot Window runtime WWI harness.')
