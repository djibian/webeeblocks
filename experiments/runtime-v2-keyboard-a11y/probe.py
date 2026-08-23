#!/usr/bin/env python3
import json, sys, time, urllib.request
import websocket

CDP='http://127.0.0.1:9222/json'

def targets():
    with urllib.request.urlopen(CDP, timeout=2) as response:
        return json.load(response)

def wait_target(timeout=30):
    end=time.time()+timeout
    while time.time()<end:
        try:
            for target in targets():
                if target.get('type')=='page' and 'blockly_v2' in target.get('url',''):
                    return target
        except Exception:
            pass
        time.sleep(.2)
    raise RuntimeError('Runtime v2 Robot Window target not found')

class Cdp:
    def __init__(self, url):
        self.ws=websocket.create_connection(url, timeout=5)
        self.seq=0
    def call(self, method, params=None):
        self.seq+=1; ident=self.seq
        self.ws.send(json.dumps({'id':ident,'method':method,'params':params or {}}))
        while True:
            msg=json.loads(self.ws.recv())
            if msg.get('id')==ident:
                if 'error' in msg: raise RuntimeError(msg['error'])
                return msg.get('result',{})
    def eval(self, expr):
        result=self.call('Runtime.evaluate', {'expression':expr,'returnByValue':True,'awaitPromise':True})
        if result.get('exceptionDetails'): raise RuntimeError(result['exceptionDetails'])
        return result.get('result',{}).get('value')
    def key(self, key, code=None, text=None):
        code=code or key
        base={'key':key,'code':code,'windowsVirtualKeyCode': 9 if key=='Tab' else 0}
        self.call('Input.dispatchKeyEvent', dict(base, type='keyDown'))
        if text:
            self.call('Input.dispatchKeyEvent', {'type':'char','text':text,'key':key,'code':code})
        self.call('Input.dispatchKeyEvent', dict(base, type='keyUp'))

SNAP="""(() => {
 const a=document.activeElement;
 const toolbox=document.querySelector('.blocklyToolbox');
 const selected=document.querySelector('.blocklyToolboxCategory[aria-selected="true"]');
 const aria=[...document.querySelectorAll('[role],[aria-label],[aria-labelledby],[aria-describedby]')];
 return {
  activeTag:a&&a.tagName, activeClass:a&&a.getAttribute&&a.getAttribute('class'), activeRole:a&&a.getAttribute&&a.getAttribute('role'),
  activeInBlockly:!!(a&&a.closest&&a.closest('#blocklyDiv')),
  activeInToolbox:!!(a&&a.closest&&a.closest('.blocklyToolbox')),
  toolboxVisible:!!(toolbox && getComputedStyle(toolbox).display!=='none'),
  selectedCategory:selected&&selected.textContent&&selected.textContent.trim(),
  ariaCount:aria.length,
  blockAriaCount:[...document.querySelectorAll('.blocklyBlockCanvas [role], .blocklyBlockCanvas [aria-label]')].length,
  keyboardAccessibilityMode: !!(window.workspace && window.workspace.keyboardAccessibilityMode),
  shortcutNames: Blockly.ShortcutRegistry && Blockly.ShortcutRegistry.registry ? Object.keys(Blockly.ShortcutRegistry.registry.getRegistry()) : []
 };
})()"""

def exercise(cdp):
    cdp.eval("document.activeElement && document.activeElement.blur(); document.body.setAttribute('tabindex','-1'); document.body.focus(); true")
    snaps=[]
    for _ in range(16):
        cdp.key('Tab','Tab')
        s=cdp.eval(SNAP); snaps.append(s)
        if s and s.get('activeInBlockly'): break
    cdp.key('t','KeyT','t')
    time.sleep(.2)
    after=cdp.eval(SNAP)
    return {'tabs':snaps,'afterT':after,'toolboxFocused':bool(after and after.get('activeInToolbox'))}

def main():
    cdp=Cdp(wait_target()['webSocketDebuggerUrl'])
    cdp.call('Runtime.enable')
    end=time.time()+30
    while time.time()<end:
        version=cdp.eval("window.Blockly && Blockly.VERSION")
        if version=='13.2.1' and cdp.eval("!!window.workspace"): break
        time.sleep(.2)
    else: raise RuntimeError('Blockly 13.2.1 workspace not initialized')
    initial=cdp.eval(SNAP)
    native=exercise(cdp)
    registered=None
    if not native['toolboxFocused']:
        available=cdp.eval("!!(Blockly.ShortcutItems && Blockly.ShortcutItems.registerNavigationShortcuts)")
        if available:
            cdp.eval("Blockly.ShortcutItems.registerNavigationShortcuts(); true")
            registered=exercise(cdp)
    result={'version':'13.2.1','initial':initial,'native':native,'afterRegisterNavigationShortcuts':registered}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if initial.get('ariaCount',0) <= 0:
        raise RuntimeError('no ARIA/role metadata found in real Robot Window')
    if not native['toolboxFocused'] and not (registered and registered['toolboxFocused']):
        raise RuntimeError('keyboard-only toolbox focus failed before and after registerNavigationShortcuts()')

if __name__=='__main__':
    main()
