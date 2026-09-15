#!/usr/bin/env python3
import argparse
import json
import time
import urllib.request
from pathlib import Path

import websocket

CDP = 'http://127.0.0.1:9222/json'


def wait_target(timeout=30.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            with urllib.request.urlopen(CDP, timeout=2) as response:
                for target in json.load(response):
                    if target.get('type') == 'page' and 'blockly_v2' in target.get('url', ''):
                        return target
        except Exception:
            pass
        time.sleep(0.2)
    raise RuntimeError('Runtime v2 Robot Window target not found for page activation')


class Cdp:
    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=5)
        self.seq = 0

    def call(self, method, params=None):
        self.seq += 1
        ident = self.seq
        self.ws.send(json.dumps({'id': ident, 'method': method, 'params': params or {}}))
        while True:
            message = json.loads(self.ws.recv())
            if message.get('id') != ident:
                continue
            if 'error' in message:
                raise RuntimeError(message['error'])
            return message.get('result', {})

    def eval(self, expression):
        response = self.call(
            'Runtime.evaluate',
            {'expression': expression, 'returnByValue': True, 'awaitPromise': True},
        )
        if response.get('exceptionDetails'):
            raise RuntimeError(response['exceptionDetails'])
        return response.get('result', {}).get('value')

    def close(self):
        self.ws.close()


SNAPSHOT = r'''(() => {
  const active = document.activeElement;
  return {
    url: location.href,
    readyState: document.readyState,
    visibilityState: document.visibilityState,
    hasFocus: document.hasFocus(),
    activeElement: active ? {
      tag: active.tagName,
      id: active.id || '',
      className: String(active.className || '')
    } : null
  };
})()'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)

    target = wait_target()
    cdp = Cdp(target['webSocketDebuggerUrl'])
    trace = {'targetId': target.get('id'), 'before': None, 'samples': [], 'after': None}
    try:
        cdp.call('Runtime.enable')
        cdp.call('Page.enable')
        trace['before'] = cdp.eval(SNAPSHOT)
        cdp.call('Page.bringToFront')

        end = time.monotonic() + 2.0
        while time.monotonic() < end:
            state = cdp.eval(SNAPSHOT)
            trace['samples'].append(state)
            if state.get('hasFocus') and state.get('visibilityState') == 'visible':
                trace['after'] = state
                break
            time.sleep(0.05)
        if trace['after'] is None:
            trace['after'] = cdp.eval(SNAPSHOT)
    finally:
        output.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding='utf-8')
        cdp.close()

    after = trace['after'] or {}
    if after.get('visibilityState') != 'visible' or not after.get('hasFocus'):
        raise RuntimeError(
            'Runtime v2 Robot Window did not become visible and focused after Page.bringToFront: '
            + json.dumps(after, ensure_ascii=False, separators=(',', ':'))
        )


if __name__ == '__main__':
    main()
