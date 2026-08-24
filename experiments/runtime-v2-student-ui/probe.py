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
 const blocks=workspace.getAllBlocks(false).map(b=>({type:b.type,colour:b.getColour&&b.getColour(),rect:rect(b.getSvgRoot&&b.getSvgRoot())}));
 const rs=blocks.map(x=>x.rect).filter(Boolean); let extent=null;
 if(rs.length){extent={left:Math.min(...rs.map(r=>r.x)),top:Math.min(...rs.map(r=>r.y)),right:Math.max(...rs.map(r=>r.right)),bottom:Math.max(...rs.map(r=>r.bottom))};extent.width=extent.right-extent.left;extent.height=extent.bottom-extent.top;}
 let registryMatch=false; try{const R=Blockly.registry.getClass(Blockly.registry.Type.RENDERER,'zelos',true);registryMatch=workspace.getRenderer() instanceof R;}catch(_){}
 const colours={}; blocks.forEach(b=>{(colours[b.type]||(colours[b.type]=[])).push(b.colour);});
 let toolboxItems=[]; try{toolboxItems=workspace.getToolbox().getToolboxItems().filter(x=>typeof x.getName==='function').map(x=>({name:x.getName(),colour:x.getColour&&x.getColour()}));}catch(_){}
 return {version:String(Blockly.VERSION),rendererMatchesRegistry:registryMatch,rendererClassName:workspace.getRenderer().getClassName&&workspace.getRenderer().getClassName(),theme:workspace.getTheme&&workspace.getTheme().name,
 viewport:{width:innerWidth,height:innerHeight},geometry:{toolbox:rect(document.querySelector('.blocklyToolbox')),flyout:rect(document.querySelector('.blocklyFlyout')),blockExtent:extent,toolbar:rect(document.getElementById('workspaceToolbar')),trash:rect(document.querySelector('.blocklyTrash'))},
 controls:{zoomIn:!!document.getElementById('zoomIn'),zoomOut:!!document.getElementById('zoomOut'),zoomFit:!!document.getElementById('zoomFit'),zoomReset:!!document.getElementById('zoomReset')},
 active:{inBlockly:!!(a&&a.closest&&a.closest('#blocklyDiv')),inToolbox:!!(a&&a.closest&&a.closest('.blocklyToolbox')),inFlyout:!!(a&&a.closest&&a.closest('.blocklyFlyout')),text:a&&a.textContent&&a.textContent.trim().slice(0,80)},
 selected:(document.querySelector('.blocklyToolboxCategory[aria-selected="true"],.blocklyTreeRow[aria-selected="true"]')||{}).textContent||null,
 rangeLabel:(Blockly.Blocks.webeeblocks_v2_range&&Blockly.Blocks.webeeblocks_v2_range.toString&&Blockly.Blocks.webeeblocks_v2_range.toString())||'',blockColours:colours,toolboxItems:toolboxItems,
 counts:{blocks:blocks.length,topBlocks:workspace.getTopBlocks(false).length,categories:document.querySelectorAll('.blocklyToolboxCategory,.blocklyTreeRow').length}};
})()'''

RESPONSIVE=r'''(() => {
 const visible=el=>{if(!el)return false;const r=el.getBoundingClientRect();const s=getComputedStyle(el);return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0;};
 const reset=document.querySelector('#zoomReset .toolbarText');
 const fit=document.querySelector('#zoomFit .toolbarText');
 return {viewport:{width:innerWidth,height:innerHeight},resetLabel:(reset&&reset.textContent.trim())||'',resetLabelVisible:visible(reset),fitLabelVisible:visible(fit),toolbarWidth:(document.getElementById('workspaceToolbar').getBoundingClientRect().width)};
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

def first_colour(snapshot, block_type):
    values=snapshot['blockColours'].get(block_type,[])
    if not values:
        raise RuntimeError('fixture does not contain '+block_type)
    return values[0].upper()

def main():
    p=argparse.ArgumentParser(); p.add_argument('--fixture',required=True); p.add_argument('--expected-ast',required=True); p.add_argument('--output',required=True); p.add_argument('--screenshot',required=True); a=p.parse_args()
    c=Cdp(wait_target()['webSocketDebuggerUrl']); c.call('Runtime.enable'); c.call('Page.enable'); c.call('Emulation.setDeviceMetricsOverride',{'width':1366,'height':768,'deviceScaleFactor':1,'mobile':False})
    end=time.time()+30
    while time.time()<end:
        ready=c.eval("({v:window.Blockly&&Blockly.VERSION,w:!!window.workspace})")
        if ready and ready.get('v')=='13.2.1' and ready.get('w'): break
        time.sleep(.2)
    else: raise RuntimeError('Blockly 13.2.1 workspace did not initialize')
    fixture=Path(a.fixture).read_text(encoding='utf-8')
    expected_ast=json.loads(Path(a.expected_ast).read_text(encoding='utf-8'))
    c.eval("workspace.clear();Blockly.Xml.domToWorkspace(Blockly.utils.xml.textToDom(%s),workspace);Blockly.svgResize(workspace);true"%json.dumps(fixture)); time.sleep(.5)
    ast=c.eval('WebeeBlocksSemanticAst.compileWorkspace(workspace)'); initial=c.eval(SNAP)
    if ast != expected_ast:
        raise RuntimeError('compiled fixture AST differs from canonical pre-#75 AST: '+json.dumps({'expected':expected_ast,'actual':ast},ensure_ascii=False,separators=(',',':')))
    if not initial['rendererMatchesRegistry']: raise RuntimeError('Zelos not actually instantiated')
    if initial['version']!='13.2.1': raise RuntimeError('wrong Blockly version')
    if not all(initial['controls'].values()): raise RuntimeError('workspace controls missing')
    expected_colours={'Vol':'#2563EB','Contrôle':'#7C3AED','Capteurs':'#0E7490','Opérateurs':'#047857'}
    toolbox={item['name']:(item.get('colour') or '').upper() for item in initial['toolboxItems']}
    if list(toolbox) != list(expected_colours):
        raise RuntimeError('toolbox semantic groups/order mismatch: '+json.dumps(initial['toolboxItems'],ensure_ascii=False))
    for name, colour in expected_colours.items():
        if toolbox[name] != colour:
            raise RuntimeError('toolbox colour mismatch for '+name+': '+toolbox[name]+' != '+colour)
    block_groups={
        'Vol':('webeeblocks_v2_takeoff','webeeblocks_v2_move','webeeblocks_v2_land'),
        'Contrôle':('controls_repeat_ext','controls_if'),
        'Capteurs':('webeeblocks_v2_range',),
        'Opérateurs':('logic_compare','math_number')
    }
    for name, block_types in block_groups.items():
        colours=[first_colour(initial,t) for t in block_types]
        if set(colours)!={expected_colours[name]}:
            raise RuntimeError(name+' blocks do not use semantic palette: '+json.dumps(dict(zip(block_types,colours)),ensure_ascii=False))
    key=keyboard(c)
    c.call('Emulation.setDeviceMetricsOverride',{'width':800,'height':768,'deviceScaleFactor':1,'mobile':False}); c.eval('Blockly.svgResize(workspace);true'); time.sleep(.25)
    responsive=c.eval(RESPONSIVE)
    if responsive['resetLabel']!='100 %' or not responsive['resetLabelVisible']:
        raise RuntimeError('100 % reset label must remain visible at narrow width: '+json.dumps(responsive,ensure_ascii=False))
    c.call('Emulation.setDeviceMetricsOverride',{'width':1366,'height':768,'deviceScaleFactor':1,'mobile':False}); c.eval('Blockly.svgResize(workspace);true'); time.sleep(.25)
    final=c.eval(SNAP); c.screenshot(a.screenshot)
    Path(a.output).write_text(json.dumps({'ast':ast,'astMatchesExpected':True,'initial':initial,'keyboard':key,'responsive800':responsive,'final':final},ensure_ascii=False,indent=2),encoding='utf-8')
    try:c.call('Browser.close')
    except Exception:pass
if __name__=='__main__': main()
