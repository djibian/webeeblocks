#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
html_path = ROOT / 'plugins/robot_windows/blockly_v2/blockly_v2.html'
html = html_path.read_text(encoding='utf-8')
main_seam = '  <script src="main.js"></script>\n'
if main_seam not in html:
    raise SystemExit('main.js seam not found')
html = html.replace(main_seam, '  <script>window.WEBEEBLOCKS_NATIVE_FILE_BROKER_PROBE = true;</script>\n' + main_seam, 1)
project_seam = '  <script src="project_ui.js"></script>\n'
if project_seam not in html:
    raise SystemExit('project_ui.js seam not found')
harness = r'''  <script>
  (function() {
    let sequence = 0;
    let reportChain = Promise.resolve();
    function report(event, detail) {
      const payload = {seq: sequence++, event, detail: detail === undefined ? null : detail, wall_ms: Date.now()};
      reportChain = reportChain.then(() => fetch('http://127.0.0.1:8765/event', {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
      }));
      return reportChain;
    }
    window.addEventListener('error', event => report('WINDOW_ERROR', event.message));
    window.addEventListener('unhandledrejection', event => report('UNHANDLED_REJECTION', String(event.reason)));
    window.addEventListener('webeeblocks-native-file-broker-ready', async event => {
      await report('FILE_BROKER_CAPABILITIES', event.detail);
      await report('FILE_BROKER_TEST_COMPLETE', {runtimeState: document.getElementById('runtimeState').textContent});
    });
  })();
  </script>
'''
html_path.write_text(html.replace(project_seam, harness + project_seam, 1), encoding='utf-8')
