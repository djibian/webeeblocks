#!/usr/bin/env python3
import argparse
import base64
import json
import time
import urllib.request
from pathlib import Path

import websocket

CDP = 'http://127.0.0.1:9222/json'


def targets():
    with urllib.request.urlopen(CDP, timeout=2) as response:
        return json.load(response)


def wait_target(timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        try:
            for target in targets():
                if target.get('type') == 'page' and 'blockly_v2' in target.get('url', ''):
                    return target
        except Exception:
            pass
        time.sleep(0.2)
    raise RuntimeError('Runtime v2 Robot Window target not found')


class Cdp:
    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=5)
        self.seq = 0

    def call(self, method, params=None):
        self.seq += 1
        ident = self.seq
        self.ws.send(json.dumps({'id': ident, 'method': method, 'params': params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get('id') == ident:
                if 'error' in msg:
                    raise RuntimeError(msg['error'])
                return msg.get('result', {})

    def eval(self, expr):
        result = self.call('Runtime.evaluate', {
            'expression': expr,
            'returnByValue': True,
            'awaitPromise': True,
        })
        if result.get('exceptionDetails'):
            raise RuntimeError(result['exceptionDetails'])
        return result.get('result', {}).get('value')

    def key(self, key, code=None):
        code = code or key
        vk = {'Tab': 9, 'Enter': 13, 'Escape': 27, 'ArrowDown': 40, 'ArrowUp': 38}.get(key, 0)
        base = {'key': key, 'code': code, 'windowsVirtualKeyCode': vk, 'nativeVirtualKeyCode': vk}
        self.call('Input.dispatchKeyEvent', dict(base, type='keyDown'))
        self.call('Input.dispatchKeyEvent', dict(base, type='keyUp'))

    def screenshot(self, path):
        data = self.call('Page.captureScreenshot', {'format': 'png', 'fromSurface': True})['data']
        Path(path).write_bytes(base64.b64decode(data))


SNAPSHOT = r'''(() => {
  const a = document.activeElement;
  const rect = el => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom};
  };
  const toolbox = document.querySelector('.blocklyToolbox');
  const flyout = document.querySelector('.blocklyFlyout');
  const workspaceSvg = document.querySelector('#blocklyDiv .blocklySvg');
  const zoom = document.querySelector('.blocklyZoom');
  const trash = document.querySelector('.blocklyTrash');
  const selected = document.querySelector('.blocklyToolboxCategory[aria-selected="true"], .blocklyTreeRow[aria-selected="true"]');
  const blocks = workspace ? workspace.getAllBlocks(false).map(b => {
    const root = b.getSvgRoot && b.getSvgRoot();
    return {type:b.type, rect:rect(root)};
  }) : [];
  const allRects = blocks.map(b => b.rect).filter(Boolean);
  const extent = allRects.length ? {
    left:Math.min(...allRects.map(r=>r.x)), top:Math.min(...allRects.map(r=>r.y)),
    right:Math.max(...allRects.map(r=>r.right)), bottom:Math.max(...allRects.map(r=>r.bottom))
  } : null;
  if (extent) { extent.width=extent.right-extent.left; extent.height=extent.bottom-extent.top; }
  const className = workspace && workspace.getRenderer && workspace.getRenderer().getClassName ? workspace.getRenderer().getClassName() : null;
  const expected = window.__WEBEEBLOCKS_RENDERER_VARIANT;
  let registryMatch = false;
  try {
    const R = Blockly.registry.getClass(Blockly.registry.Type.RENDERER, expected, true);
    registryMatch = !!(workspace && workspace.getRenderer() instanceof R);
  } catch (_) {}
  return {
    version:String(Blockly.VERSION || ''), expectedRenderer:expected, rendererClassName:className, rendererMatchesRegistry:registryMatch,
    viewport:{width:innerWidth,height:innerHeight,devicePixelRatio:devicePixelRatio},
    active:{tag:a&&a.tagName,role:a&&a.getAttribute&&a.getAttribute('role'),label:a&&a.getAttribute&&a.getAttribute('aria-label'),text:a&&a.textContent&&a.textContent.trim().slice(0,80),
      inBlockly:!!(a&&a.closest&&a.closest('#blocklyDiv')), inToolbox:!!(a&&a.closest&&a.closest('.blocklyToolbox')), inFlyout:!!(a&&a.closest&&a.closest('.blocklyFlyout'))},
    selectedCategory:selected&&selected.textContent&&selected.textContent.trim(),
    geometry:{blocklyDiv:rect(document.getElementById('blocklyDiv')), workspaceSvg:rect(workspaceSvg), toolbox:rect(toolbox), flyout:rect(flyout), zoom:rect(zoom), trash:rect(trash), blockExtent:extent},
    counts:{blocks:blocks.length, topBlocks:workspace?workspace.getTopBlocks(false).length:0, toolboxCategories:document.querySelectorAll('.blocklyToolboxCategory,.blocklyTreeRow').length, flyoutBlocks:document.querySelectorAll('.blocklyFlyout .blocklyDraggable').length},
    blocks:blocks
  };
})()'''


def wait_ready(cdp, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        value = cdp.eval("({version:window.Blockly&&Blockly.VERSION,workspace:!!window.workspace,renderer:window.__WEBEEBLOCKS_RENDERER_VARIANT||null})")
        if value and value.get('version') == '13.2.1' and value.get('workspace') and value.get('renderer'):
            return value
        time.sleep(0.2)
    raise RuntimeError('Blockly 13.2.1 workspace did not initialize')


def keyboard_path(cdp):
    cdp.eval("document.activeElement&&document.activeElement.blur();document.body.setAttribute('tabindex','-1');document.body.focus();true")
    steps = []

    def snap(name):
        value = cdp.eval(SNAPSHOT)
        steps.append({'step': name, 'snapshot': value})
        return value

    snap('body_focus')
    entered = False
    for index in range(16):
        cdp.key('Tab', 'Tab')
        state = snap(f'tab_{index+1}')
        if state['active']['inToolbox']:
            entered = True
            break

    arrow_down = arrow_up = opened = flyout_reached = workspace_returned = False
    flyout_open_before = False
    if entered:
        before = steps[-1]['snapshot']
        cdp.key('ArrowDown', 'ArrowDown')
        down = snap('arrow_down')
        arrow_down = (down.get('selectedCategory'), down['active'].get('text')) != (before.get('selectedCategory'), before['active'].get('text'))

        before_up = down
        cdp.key('ArrowUp', 'ArrowUp')
        up = snap('arrow_up')
        arrow_up = (up.get('selectedCategory'), up['active'].get('text')) != (before_up.get('selectedCategory'), before_up['active'].get('text'))

        flyout = up['geometry'].get('flyout')
        flyout_open_before = bool(flyout and flyout.get('width', 0) > 0)
        cdp.key('Enter', 'Enter')
        opened_state = snap('activate_category')
        flyout = opened_state['geometry'].get('flyout')
        opened = bool(flyout and flyout.get('width', 0) > 0)

        for index in range(12):
            cdp.key('Tab', 'Tab')
            state = snap(f'flyout_tab_{index+1}')
            if state['active']['inFlyout']:
                flyout_reached = True
                break

        cdp.key('Escape', 'Escape')
        snap('escape_from_flyout')
        for index in range(16):
            cdp.key('Tab', 'Tab')
            state = snap(f'workspace_tab_{index+1}')
            if state['active']['inBlockly'] and not state['active']['inToolbox'] and not state['active']['inFlyout']:
                workspace_returned = True
                break

    return {
        'toolboxEntry': entered,
        'arrowDown': arrow_down,
        'arrowUp': arrow_up,
        'flyoutOpenBeforeActivation': flyout_open_before,
        'categoryActivation': opened,
        'flyoutBlockReachable': flyout_reached,
        'workspaceFocusReturn': workspace_returned,
        'steps': steps,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--renderer', required=True, choices=['thrasos', 'zelos'])
    parser.add_argument('--fixture', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--screenshot', required=True)
    args = parser.parse_args()

    cdp = Cdp(wait_target()['webSocketDebuggerUrl'])
    cdp.call('Runtime.enable')
    cdp.call('Page.enable')
    cdp.call('Emulation.setDeviceMetricsOverride', {
        'width': 1366, 'height': 768, 'deviceScaleFactor': 1, 'mobile': False,
    })
    wait_ready(cdp)
    cdp.eval("window.dispatchEvent(new Event('resize'));Blockly.svgResize(workspace);true")

    fixture = Path(args.fixture).read_text(encoding='utf-8')
    cdp.eval("workspace.clear();Blockly.Xml.domToWorkspace(Blockly.utils.xml.textToDom(%s),workspace);Blockly.svgResize(workspace);true" % json.dumps(fixture))
    time.sleep(0.5)
    ast = cdp.eval("WebeeBlocksSemanticAst.compileWorkspace(workspace)")
    initial = cdp.eval(SNAPSHOT)
    if initial.get('expectedRenderer') != args.renderer or not initial.get('rendererMatchesRegistry'):
        raise RuntimeError('renderer registry mismatch: ' + json.dumps(initial, ensure_ascii=False))
    if ast.get('semantics') != 'webeeblocks-ast-v1':
        raise RuntimeError('unexpected AST semantics: ' + json.dumps(ast))

    keyboard = keyboard_path(cdp)
    final = cdp.eval(SNAPSHOT)
    cdp.screenshot(args.screenshot)
    result = {'renderer': args.renderer, 'ast': ast, 'initial': initial, 'keyboard': keyboard, 'final': final}
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    try:
        cdp.call('Browser.close')
    except Exception:
        pass


if __name__ == '__main__':
    main()
