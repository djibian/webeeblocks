#!/usr/bin/env python3
import argparse, base64, json, re, time, urllib.request
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
    def click(self,rect):
        x=rect['x']+rect['width']/2; y=rect['y']+rect['height']/2
        self.call('Input.dispatchMouseEvent',{'type':'mouseMoved','x':x,'y':y})
        self.call('Input.dispatchMouseEvent',{'type':'mousePressed','x':x,'y':y,'button':'left','clickCount':1})
        self.call('Input.dispatchMouseEvent',{'type':'mouseReleased','x':x,'y':y,'button':'left','clickCount':1})
    def hover(self,rect):
        self.call('Input.dispatchMouseEvent',{'type':'mouseMoved','x':1,'y':1})
        time.sleep(.1)
        self.call('Input.dispatchMouseEvent',{'type':'mouseMoved','x':rect['x']+rect['width']/2,'y':rect['y']+rect['height']/2})
    def screenshot(self,path):
        data=self.call('Page.captureScreenshot',{'format':'png','fromSurface':True})['data']
        Path(path).write_bytes(base64.b64decode(data))

SNAP=r'''(() => {
 const rect=el=>{if(!el)return null;const r=el.getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom}};
 const renderedCategoryColour=item=>{
   if(!item||typeof item.getDiv!=='function')return '';
   const root=item.getDiv(); if(!root)return '';
   const nodes=[root,...root.querySelectorAll('*')];
   for(const el of nodes){
     const s=getComputedStyle(el);
     for(const side of ['Left','Right','Top','Bottom']){
       const width=parseFloat(s['border'+side+'Width']||'0');
       const style=s['border'+side+'Style'];
       const colour=s['border'+side+'Color'];
       if(width>0&&style!=='none'&&colour&&colour!=='transparent'&&colour!=='rgba(0, 0, 0, 0)')return colour;
     }
   }
   return '';
 };
 const a=document.activeElement;
 const blocks=workspace.getAllBlocks(false).map(b=>({type:b.type,colour:b.getColour&&b.getColour(),rect:rect(b.getSvgRoot&&b.getSvgRoot())}));
 const rs=blocks.map(x=>x.rect).filter(Boolean); let extent=null;
 if(rs.length){extent={left:Math.min(...rs.map(r=>r.x)),top:Math.min(...rs.map(r=>r.y)),right:Math.max(...rs.map(r=>r.right)),bottom:Math.max(...rs.map(r=>r.bottom))};extent.width=extent.right-extent.left;extent.height=extent.bottom-extent.top;}
 let registryMatch=false; try{const R=Blockly.registry.getClass(Blockly.registry.Type.RENDERER,'zelos',true);registryMatch=workspace.getRenderer() instanceof R;}catch(_){}
 const colours={}; blocks.forEach(b=>{(colours[b.type]||(colours[b.type]=[])).push(b.colour);});
 let toolboxItems=[]; try{toolboxItems=workspace.getToolbox().getToolboxItems().filter(x=>typeof x.getName==='function').map(x=>({name:x.getName(),colour:renderedCategoryColour(x)}));}catch(_){}
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

LOCALE=r'''(() => {
 const blockText=type=>{const block=workspace.newBlock(type);try{return block.toString();}finally{block.dispose(false);}};
 const range=workspace.newBlock('webeeblocks_v2_range');
 let directionOptions;
 try{directionOptions=range.getField('DIRECTION').getOptions(false).map(option=>({label:option[0],value:option[1]}));}
 finally{range.dispose(false);}
 renderSensorValues({front:1,back:2,left:3,right:4,up:5});
 return {
   messages:{repeat:Blockly.Msg.CONTROLS_REPEAT_TITLE,if:Blockly.Msg.CONTROLS_IF_MSG_IF,do:Blockly.Msg.CONTROLS_IF_MSG_THEN,else:Blockly.Msg.CONTROLS_IF_MSG_ELSE,and:Blockly.Msg.LOGIC_OPERATION_AND,or:Blockly.Msg.LOGIC_OPERATION_OR,trueValue:Blockly.Msg.LOGIC_BOOLEAN_TRUE,falseValue:Blockly.Msg.LOGIC_BOOLEAN_FALSE,repeatTooltip:Blockly.Msg.CONTROLS_REPEAT_TOOLTIP},
   blocks:{repeat:blockText('controls_repeat_ext'),condition:blockText('controls_if'),logic:blockText('logic_operation'),comparison:blockText('logic_compare'),boolean:blockText('logic_boolean')},
   directionOptions:directionOptions,
   sensorText:document.getElementById('debugSensors').textContent
 };
})()'''

RENDER_LOCALE=r'''(() => {
 const rect=el=>{const r=el.getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom}};
 const xml='<xml xmlns="https://developers.google.com/blockly/xml"><block type="logic_operation" x="650" y="50"><field name="OP">AND</field><value name="A"><block type="logic_boolean"><field name="BOOL">TRUE</field></block></value><value name="B"><block type="logic_boolean"><field name="BOOL">FALSE</field></block></value></block><block type="logic_operation" x="650" y="180"><field name="OP">OR</field><value name="A"><block type="logic_boolean"><field name="BOOL">TRUE</field></block></value><value name="B"><block type="logic_boolean"><field name="BOOL">FALSE</field></block></value></block><block type="webeeblocks_v2_range" x="650" y="310"><field name="DIRECTION">front</field></block></xml>';
 Blockly.Xml.domToWorkspace(Blockly.utils.xml.textToDom(xml),workspace);
 Blockly.svgResize(workspace);
 const logicAnd=workspace.getBlocksByType('logic_operation',false).find(block=>block.getFieldValue('OP')==='AND'&&block.getRelativeToSurfaceXY().x>500);
 const logicOr=workspace.getBlocksByType('logic_operation',false).find(block=>block.getFieldValue('OP')==='OR'&&block.getRelativeToSurfaceXY().x>500);
 const range=workspace.getBlocksByType('webeeblocks_v2_range',false).find(block=>block.getRelativeToSurfaceXY().x>500);
 const repeat=workspace.getBlocksByType('controls_repeat_ext',false)[0];
 if(!logicAnd||!logicOr||!range||!repeat)throw new Error('rendered locale evidence blocks missing');
 const field=range.getField('DIRECTION');
 const fieldRoot=field.getSvgRoot();
 return {
   logicAndText:logicAnd.toString(),logicAndSvgText:logicAnd.getSvgRoot().textContent,
   logicOrText:logicOr.toString(),logicOrSvgText:logicOr.getSvgRoot().textContent,
   logicRects:[rect(logicAnd.getSvgRoot()),rect(logicOr.getSvgRoot())],directionFieldRect:rect(fieldRoot),directionFieldText:fieldRoot.textContent,
   directionFieldRole:fieldRoot.getAttribute('role'),directionFieldAriaLabel:fieldRoot.getAttribute('aria-label'),
   repeatRect:rect(repeat.inputList.flatMap(input=>input.fieldRow).find(field=>field.getSvgRoot&&field.getSvgRoot()).getSvgRoot()),
   workspaceAriaLabel:document.getElementById('blocklyDiv').getAttribute('aria-label')
 };
})()'''

VISIBLE_OVERLAY=r'''(() => {
 const visible=el=>{if(!el)return false;const r=el.getBoundingClientRect(),s=getComputedStyle(el);return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0;};
 const nodes=[...document.querySelectorAll('.blocklyDropDownDiv,.blocklyWidgetDiv,[role="menu"],[role="listbox"],.blocklyTooltipDiv')].filter(visible);
 return nodes.map(el=>({className:el.className||'',role:el.getAttribute('role'),ariaLabel:el.getAttribute('aria-label'),text:(el.innerText||el.textContent||'').trim(),html:el.outerHTML.slice(0,1200)}));
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

def normalise_colour(value):
    value=(value or '').strip()
    if re.fullmatch(r'#[0-9a-fA-F]{6}',value):
        return value.upper()
    match=re.fullmatch(r'rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*[0-9.]+)?\s*\)',value)
    if match:
        return '#%02X%02X%02X' % tuple(int(part) for part in match.groups())
    return value.upper()

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
    ast=c.eval('WebeeBlocksSemanticAst.compileWorkspace(workspace)'); initial=c.eval(SNAP); locale=c.eval(LOCALE)
    if ast != expected_ast:
        raise RuntimeError('compiled fixture AST differs from canonical pre-#75 AST: '+json.dumps({'expected':expected_ast,'actual':ast},ensure_ascii=False,separators=(',',':')))
    if not initial['rendererMatchesRegistry']: raise RuntimeError('Zelos not actually instantiated')
    if initial['version']!='13.2.1': raise RuntimeError('wrong Blockly version')
    if not all(initial['controls'].values()): raise RuntimeError('workspace controls missing')
    expected_colours={'Vol':'#2563EB','Contrôle':'#7C3AED','Capteurs':'#0E7490','Opérateurs':'#047857'}
    toolbox={item['name']:normalise_colour(item.get('colour')) for item in initial['toolboxItems']}
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

    rendered=c.eval(RENDER_LOCALE); time.sleep(.5)
    rendered_and=(rendered['logicAndSvgText']+' '+rendered['logicAndText']).lower()
    rendered_or=(rendered['logicOrSvgText']+' '+rendered['logicOrText']).lower()
    for expected in ('vrai','et','faux'):
        if expected not in rendered_and:
            raise RuntimeError('rendered AND program lacks '+expected+': '+rendered_and)
    for expected in ('vrai','ou','faux'):
        if expected not in rendered_or:
            raise RuntimeError('rendered OR program lacks '+expected+': '+rendered_or)
    if rendered['workspaceAriaLabel']!='Programme Blockly':
        raise RuntimeError('rendered workspace accessibility label is not French: '+str(rendered['workspaceAriaLabel']))
    screenshot=Path(a.screenshot)
    c.screenshot(screenshot)
    c.click(rendered['directionFieldRect']); time.sleep(.4)
    direction_menu=c.eval(VISIBLE_OVERLAY)
    if not direction_menu: raise RuntimeError('real direction dropdown did not open')
    menu_text=' '.join(entry['text'] for entry in direction_menu).lower()
    for expected in ('devant','derrière','à gauche','à droite','au-dessus'):
        if expected not in menu_text:
            raise RuntimeError('real direction dropdown lacks '+expected+': '+menu_text)
    c.screenshot(screenshot.with_name('direction-menu-1366x768.png'))
    c.key('Escape'); time.sleep(.2)
    c.hover(rendered['repeatRect'])
    tooltip=[]
    end=time.time()+5.0
    while time.time()<end:
        overlay=c.eval(VISIBLE_OVERLAY)
        tooltip=[entry for entry in overlay if ('Tooltip' in entry['className'] or 'tooltip' in entry['className'].lower()) and entry['text'].strip()]
        if tooltip:
            break
        time.sleep(.1)
    if not tooltip: raise RuntimeError('real repeat tooltip did not become visible and non-empty after hover within 5.0s')
    tooltip_text=' '.join(entry['text'] for entry in tooltip).lower()
    if not tooltip_text or 'repeat' in tooltip_text:
        raise RuntimeError('real repeat tooltip is empty or English: '+tooltip_text)
    c.screenshot(screenshot.with_name('repeat-tooltip-1366x768.png'))
    final=c.eval(SNAP)
    Path(a.output).write_text(json.dumps({'ast':ast,'astMatchesExpected':True,'locale':locale,'renderedLocale':rendered,'directionMenu':direction_menu,'repeatTooltip':tooltip,'initial':initial,'keyboard':key,'responsive800':responsive,'final':final},ensure_ascii=False,indent=2),encoding='utf-8')
    try:c.call('Browser.close')
    except Exception:pass
if __name__=='__main__': main()
