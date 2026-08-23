#!/usr/bin/env python3
import argparse, base64, json, time, urllib.request
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
    def __init__(self,url): self.ws=websocket.create_connection(url,timeout=5); self.seq=0
    def call(self,method,params=None):
        self.seq+=1; ident=self.seq
        self.ws.send(json.dumps({'id':ident,'method':method,'params':params or {}}))
        while True:
            msg=json.loads(self.ws.recv())
            if msg.get('id')==ident:
                if 'error' in msg: raise RuntimeError(msg['error'])
                return msg.get('result',{})
    def eval(self,expr):
        result=self.call('Runtime.evaluate',{'expression':expr,'returnByValue':True,'awaitPromise':True})
        if result.get('exceptionDetails'): raise RuntimeError(result['exceptionDetails'])
        return result.get('result',{}).get('value')
    def key(self,key,code=None):
        vk={'Tab':9,'Enter':13,'Escape':27,'ArrowDown':40,'ArrowUp':38}.get(key,0); code=code or key
        base={'key':key,'code':code,'windowsVirtualKeyCode':vk,'nativeVirtualKeyCode':vk}
        self.call('Input.dispatchKeyEvent',dict(base,type='keyDown')); self.call('Input.dispatchKeyEvent',dict(base,type='keyUp'))
    def screenshot(self,path):
        data=self.call('Page.captureScreenshot',{'format':'png','fromSurface':True})['data']
        Path(path).write_bytes(base64.b64decode(data))

SNAP=r'''(() => {
 const rect=el=>{if(!el)return null;const r=el.getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom}};
 const a=document.activeElement;
 const blocks=workspace.getAllBlocks(false).map(b=>({type:b.type,rect:rect(b.getSvgRoot&&b.getSvgRoot())}));
 const rs=blocks.map(x=>x.rect).filter(Boolean); let extent=null;
 if(rs.length){extent={left:Math.min(...rs.map(r=>r.x)),top:Math.min(...rs.map(r=>r.y)),right:Math.max(...rs.map(r=>r.right)),bottom:Math.max(...rs.map(r=>r.bottom))};extent.width=extent.right-extent.left;extent.height=extent.bottom-extent.top;}
 let registryMatch=false; try{const R=Blockly.registry.getClass(Blockly.registry.Type.RENDERER,'zelos',true);registryMatch=workspace.getRenderer() instanceof R;}catch(_){}
 return {version:String(Blockly.VERSION),rendererMatchesRegistry:registryMatch,rendererClassName:workspace.getRenderer().getClassName&&workspace.getRenderer().getClassName(),theme:workspace.getTheme&&workspace.getTheme().name,
 viewport:{width:innerWidth,height:innerHeight},geometry:{toolbox:rect(document.querySelector('.blocklyToolbox')),flyout:rect(document.querySelector('.blocklyFlyout')),blockExtent:extent,toolbar:rect(document.getElementById('workspaceToolbar')),trash:rect(document.querySelector('.blocklyTrash'))},
 controls:{zoomIn:!!document.getElementById('zoomIn'),zoomOut:!!document.getElementById('zoomOut'),zoomFit:!!document.getElementById('zoomFit'),zoomReset:!!document.getElementById('zoomReset')},
 active:{inBlockly:!!(a&&a.closest&&a.closest('#blocklyDiv')),inToolbox:!!(a&&a.closest&&a.closest('.blocklyToolbox')),inFlyout:!!(a&&a.closest&&a.closest('.blocklyFlyout')),text:a&&a.textContent&&a.textContent.trim().slice(0,80)},
 selected:(document.querySelector('.blocklyToolboxCategory[aria-selected="true"],.blocklyTreeRow[aria-selected="true"]')||{}).textContent||null,
 rangeLabel:(Blockly.Blocks.webeeblocks_v2_range&&Blockly.Blocks.webeeblocks_v2_range.toString&&Blockly.Blocks.webeeblocks_v2_range.toString())||'',counts:{blocks:blocks.length,topBlocks:workspace.getTopBlocks(false).length,categories:document.querySelectorAll('.blocklyToolboxCategory,.blocklyTreeRow').length}};
})()'''

def keyboard(c):
    c.eval("document.activeElement&&document.activeElement.blur();document.body.setAttribute('tabindex','-1');document.body.focus();true")
    states=[]
    def snap(name):
        v=c.eval(SNAP); states.append({'step':name,'state':v}); return v
    entered=False
    for i in range(16):
        c.key('Tab'); s=snap(f'tab_{i+1}')
        if s['active']['inToolbox']: entered=True; break
    down=up=opened=flyout=returned=False
    if entered:
        b=states[-1]['state']; c.key('ArrowDown'); d=snap('down'); down=(d['selected'],d['active']['text'])!=(b['selected'],b['active']['text'])
        c.key('ArrowUp'); u=snap('up'); up=(u['selected'],u['active']['text'])!=(d['selected'],d['active']['text'])
        c.key('Enter'); o=snap('open'); opened=bool(o['geometry']['flyout'] and o['geometry']['flyout']['width']>0)
        for i in range(12):
            c.key('Tab'); s=snap(f'flyout_{i+1}')
            if s['active']['inFlyout']: flyout=True; break
        c.key('Escape')
        for i in range(16):
            c.key('Tab'); s=snap(f'workspace_{i+1}')
            if s['active']['inBlockly'] and not s['active']['inToolbox'] and not s['active']['inFlyout']: returned=True; break
    return {'toolboxEntry':entered,'arrowDown':down,'arrowUp':up,'categoryActivation':opened,'flyoutBlockReachable':flyout,'workspaceFocusReturn':returned,'steps':states}

def main():
    p=argparse.ArgumentParser(); p.add_argument('--fixture',required=True); p.add_argument('--output',required=True); p.add_argument('--screenshot',required=True); a=p.parse_args()
    c=Cdp(wait_target()['webSocketDebuggerUrl']); c.call('Runtime.enable'); c.call('Page.enable'); c.call('Emulation.setDeviceMetricsOverride',{'width':1366,'height':768,'deviceScaleFactor':1,'mobile':False})
    end=time.time()+30
    while time.time()<end:
        ready=c.eval("({v:window.Blockly&&Blockly.VERSION,w:!!window.workspace})")
        if ready and ready.get('v')=='13.2.1' and ready.get('w'): break
        time.sleep(.2)
    else: raise RuntimeError('Blockly 13.2.1 workspace did not initialize')
    fixture=Path(a.fixture).read_text(encoding='utf-8')
    c.eval("workspace.clear();Blockly.Xml.domToWorkspace(Blockly.utils.xml.textToDom(%s),workspace);Blockly.svgResize(workspace);true"%json.dumps(fixture)); time.sleep(.5)
    ast=c.eval('WebeeBlocksSemanticAst.compileWorkspace(workspace)'); initial=c.eval(SNAP)
    if ast.get('semantics')!='webeeblocks-ast-v1': raise RuntimeError('unexpected AST semantics')
    if not initial['rendererMatchesRegistry']: raise RuntimeError('Zelos not actually instantiated')
    if initial['version']!='13.2.1': raise RuntimeError('wrong Blockly version')
    if not all(initial['controls'].values()): raise RuntimeError('workspace controls missing')
    key=keyboard(c); final=c.eval(SNAP); c.screenshot(a.screenshot)
    Path(a.output).write_text(json.dumps({'ast':ast,'initial':initial,'keyboard':key,'final':final},ensure_ascii=False,indent=2),encoding='utf-8')
    try:c.call('Browser.close')
    except Exception:pass
if __name__=='__main__': main()
