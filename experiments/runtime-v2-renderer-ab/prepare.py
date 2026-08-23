#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
html_path = ROOT / 'plugins/robot_windows/blockly_v2/blockly_v2.html'
html = html_path.read_text(encoding='utf-8')

needle = '  <script src="main.js"></script>\n'
if needle not in html:
    raise SystemExit('Runtime v2 main.js script tag not found')

bootstrap = r'''  <script id="webeeblocks-renderer-ab-bootstrap">
  (function() {
    const requested = new URLSearchParams(window.location.search).get('renderer');
    if (requested !== 'thrasos' && requested !== 'zelos')
      throw new Error('renderer A/B: expected ?renderer=thrasos or ?renderer=zelos');
    const originalInject = Blockly.inject.bind(Blockly);
    Blockly.inject = function(container, options) {
      const merged = Object.assign({}, options || {}, {renderer: requested});
      const ws = originalInject(container, merged);
      window.__WEBEEBLOCKS_RENDERER_VARIANT = requested;
      return ws;
    };
  })();
  </script>
'''

html_path.write_text(html.replace(needle, bootstrap + needle, 1), encoding='utf-8')
print('Prepared Runtime v2 renderer A/B seam; only the renderer query parameter varies between runs.')
