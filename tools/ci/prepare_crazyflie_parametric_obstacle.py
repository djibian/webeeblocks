#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture")
    parser.add_argument("--expect-done", action="store_true")
    args = parser.parse_args()

    html_path = ROOT / "plugins/robot_windows/blockly/blockly.html"
    fixture_path = ROOT / args.fixture
    html = html_path.read_text(encoding="utf-8")
    fixture = fixture_path.read_text(encoding="utf-8")

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
    window.addEventListener('webeeblocks-wwi', event => {
      const value = String(event.detail);
      responses.push(value);
      report('RX', value);
    });

    await waitFor(() => window.robotWindow && typeof window.robotWindow.send === 'function', 'RobotWindow transport', 15000);
    await waitFor(() => typeof workspace !== 'undefined' && workspace, 'Blockly workspace', 5000);

    workspace.clear();
    Blockly.Xml.domToWorkspace(Blockly.Xml.textToDom(__FIXTURE__), workspace);
    const blocks = workspace.getAllBlocks(false).map(block => block.type + ':' + (block.getFieldValue('DISTANCE') || block.getFieldValue('ANGLE') || '')).join('|');
    const message = WebeeBlocksCrazyflie.workspaceToMissionMessage(workspace);
    await report('BLOCKS', blocks);
    await report('MISSION', message.replace(/\n/g, '|'));

    const before = responses.length;
    document.getElementById('submit').click();
    if (crazyflieRuntimeState !== 'PENDING')
      throw new Error('Submit did not enter PENDING');
    await report('STATE_AFTER_SUBMIT', crazyflieRuntimeState);
    await waitFor(() => responses.slice(before).indexOf('WEBEEBLOCKS_MISSION_V1 ACK') !== -1, 'ACK', 5000);
    if (crazyflieRuntimeState !== 'RUNNING')
      throw new Error('ACK did not enter RUNNING');
    await report('STATE_AFTER_ACK', crazyflieRuntimeState);
    await report('ARMED', 'Blockly mission accepted at runtime');

    if (__EXPECT_DONE__) {
      await waitFor(() => responses.indexOf('WEBEEBLOCKS_MISSION_V1 DONE') !== -1, 'DONE', 70000);
      if (crazyflieRuntimeState !== 'WAITING')
        throw new Error('DONE did not restore WAITING');
      await report('COMPLETE', 'SUCCESS');
      await reportChain;
      return;
    }

    // Collision witness: the external Supervisor ends Webots when the physical
    // contact happens. Keep the page alive after proving Blockly -> Submit -> ACK.
    while (true)
      await sleep(1000);
  } catch (error) {
    await report('ERROR', error && error.stack ? error.stack : String(error));
    await reportChain;
  }
})();
</script>
'''.replace('__FIXTURE__', json.dumps(fixture)).replace('__EXPECT_DONE__', 'true' if args.expect_done else 'false')

    html_path.write_text(html + "\n" + script, encoding="utf-8")
    print(f"Prepared runtime obstacle harness for {fixture_path.name}; expect_done={args.expect_done}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
