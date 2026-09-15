#!/usr/bin/env python3
import json
import time
import urllib.request

import websocket

CDP = 'http://127.0.0.1:9222/json'


def wait_target(timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(CDP, timeout=2) as response:
                for target in json.load(response):
                    if target.get('type') == 'page' and 'blockly_v2' in target.get('url', ''):
                        return target
        except Exception:
            pass
        time.sleep(0.2)
    raise RuntimeError('Runtime v2 Robot Window target not found for activation')


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

    def eval(self, expression):
        result = self.call('Runtime.evaluate', {
            'expression': expression,
            'returnByValue': True,
            'awaitPromise': True,
        })
        if result.get('exceptionDetails'):
            raise RuntimeError(result['exceptionDetails'])
        return result.get('result', {}).get('value')


c = Cdp(wait_target()['webSocketDebuggerUrl'])
c.call('Runtime.enable')
c.call('Page.enable')
c.call('Page.bringToFront')

end = time.time() + 5.0
state = None
while time.time() < end:
    state = c.eval("({focused:document.hasFocus(),visibility:document.visibilityState,workspace:!!window.workspace})")
    if state and state.get('focused') and state.get('visibility') == 'visible' and state.get('workspace'):
        break
    time.sleep(0.05)
else:
    raise RuntimeError('Robot Window page did not become visibly focused after Page.bringToFront: ' + json.dumps(state, sort_keys=True))

c.eval(r'''(() => {
  const key='__webeeblocksCiPointerActivation';
  if(window[key]&&window[key].cleanup)window[key].cleanup();
  const state={count:0,last:null,cleanup:null};
  const handler=e=>{state.count+=1;state.last={x:e.clientX,y:e.clientY,target:(e.target&&e.target.tagName)||''};};
  document.addEventListener('mousemove',handler,true);
  state.cleanup=()=>document.removeEventListener('mousemove',handler,true);
  window[key]=state;
  return true;
})()''')
c.call('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': 8, 'y': 8})

end = time.time() + 2.0
pointer = None
while time.time() < end:
    pointer = c.eval("(() => {const s=window.__webeeblocksCiPointerActivation;return s?{count:s.count,last:s.last}:null;})()")
    if pointer and pointer.get('count', 0) > 0:
        break
    time.sleep(0.05)
else:
    raise RuntimeError('focused Robot Window did not receive public mousemove input: ' + json.dumps(pointer, sort_keys=True))

c.eval("window.__webeeblocksCiPointerActivation.cleanup();delete window.__webeeblocksCiPointerActivation;true")
print('WEBEEBLOCKS_STUDENT_UI_INPUT_READY ' + json.dumps({'page': state, 'pointer': pointer}, sort_keys=True))
