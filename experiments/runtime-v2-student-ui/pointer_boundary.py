#!/usr/bin/env python3
import argparse, json, time, urllib.request
from pathlib import Path
import websocket

CDP='http://127.0.0.1:9222/json'


def wait_target(timeout=30):
    end=time.time()+timeout
    while time.time()<end:
        try:
            with urllib.request.urlopen(CDP,timeout=2) as response:
                for target in json.load(response):
                    if target.get('type')=='page' and 'blockly_v2' in target.get('url',''):
                        return target
        except Exception:
            pass
        time.sleep(.2)
    raise RuntimeError('Runtime v2 Robot Window target not found')


class Cdp:
    def __init__(self,url):
        self.ws=websocket.create_connection(url,timeout=5)
        self.seq=0

    def call(self,method,params=None):
        self.seq+=1
        ident=self.seq
        self.ws.send(json.dumps({'id':ident,'method':method,'params':params or {}}))
        while True:
            msg=json.loads(self.ws.recv())
            if msg.get('id')==ident:
                if 'error' in msg:
                    raise RuntimeError(msg['error'])
                return msg.get('result',{})

    def eval(self,expr):
        result=self.call('Runtime.evaluate',{'expression':expr,'returnByValue':True,'awaitPromise':True})
        if result.get('exceptionDetails'):
            raise RuntimeError(result['exceptionDetails'])
        return result.get('result',{}).get('value')


INSTALL=r'''(() => {
  const state={
    installedAt:performance.now(),
    activation:{visibility:document.visibilityState,focus:document.hasFocus()},
    events:[]
  };
  const record=event=>{
    const target=event.target;
    const tooltip=target&&target.tooltip;
    if(!tooltip||tooltip.type!=='controls_repeat_ext')return;
    const exactPath=!!(tooltip.pathObject&&tooltip.pathObject.svgPath===target);
    state.events.push({
      type:event.type,
      isTrusted:event.isTrusted,
      pointerType:event.pointerType||'',
      exactPath:exactPath,
      clientX:event.clientX,
      clientY:event.clientY,
      timeStamp:event.timeStamp,
      visibility:document.visibilityState,
      focus:document.hasFocus()
    });
  };
  for(const type of ['pointerover','pointermove','pointerout']){
    document.addEventListener(type,record,{capture:true,passive:true});
  }
  window.__webeeblocksPointerBoundary=state;
  return state;
})()'''

SNAPSHOT=r'''(() => ({
  visibility:document.visibilityState,
  focus:document.hasFocus(),
  activeTag:document.activeElement&&document.activeElement.tagName,
  activeClass:String(document.activeElement&&document.activeElement.className||''),
  boundary:window.__webeeblocksPointerBoundary||null
}))()'''


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=('activate','collect'),required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    c=Cdp(wait_target()['webSocketDebuggerUrl'])
    c.call('Runtime.enable')
    c.call('Page.enable')
    if args.mode=='activate':
        c.call('Page.bringToFront')
        end=time.time()+2.0
        snapshot=None
        while time.time()<end:
            snapshot=c.eval(SNAPSHOT)
            if snapshot and snapshot.get('visibility')=='visible' and snapshot.get('focus'):
                break
            time.sleep(.05)
        else:
            raise RuntimeError('Robot Window page did not become visible and focused before pointer input: '+json.dumps(snapshot,separators=(',',':')))
        installed=c.eval(INSTALL)
        Path(args.output).write_text(json.dumps({'activation':snapshot,'installed':installed},ensure_ascii=False,indent=2),encoding='utf-8')
        return
    snapshot=c.eval(SNAPSHOT)
    Path(args.output).write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    main()
