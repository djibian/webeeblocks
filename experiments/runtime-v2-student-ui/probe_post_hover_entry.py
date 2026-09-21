#!/usr/bin/env python3
"""Run the canonical student UI probe with a stable real-hover target and passive diagnostics.

The product/runtime probe and existing exact-path delivery boundary remain
authoritative.  A naturally reproduced #414 failure proved that the public
localized tooltip can fire and render, then disappear immediately while the
stationary pointer transitions between Blockly path elements.  This wrapper
therefore chooses the canonical entry/settle points from a well-inside region of
the exact tooltip-bound repeat path instead of the first edge-adjacent hit.  It
still performs one ordinary outside -> path -> settle trajectory and preserves
the unchanged 5 s visible/non-empty/localized tooltip oracle.

After that hover it also retains passive browser observations: page
focus/visibility, ordinary mouse/pointer traffic, public tooltip DOM
mutations/visibility, and exact DOM identity for any later target transition. It
does not wrap timers, dispatch additional input, mutate Blockly/workspace state,
retry the hover, or weaken the oracle.
"""

from __future__ import annotations

import json
import time

import probe
import probe_entry


_ORIGINAL_EVAL = probe.Cdp.eval
_ORIGINAL_HOVER = probe.Cdp.hover

# #414 recurrence 35591000713 showed a real tooltip become visible and then hide
# while a stationary pointer produced path-to-path out/over events.  The original
# selector scanned from the repeat block's top-left and accepted the first exact
# path hit with only one adjacent exact hit, which unnecessarily leaves the
# canonical settle point close to an SVG hit-test boundary.  Keep the exact same
# tooltip-bound DOM path and ordinary real pointer trajectory, but select the
# candidate with the largest verified same-element neighbourhood.
_STABLE_REPEAT_HOVER_RECT = r'''(() => {
 const repeat=workspace.getBlocksByType('controls_repeat_ext',false)[0];
 if(!repeat)throw new Error('rendered repeat block missing for stable hover');
 const repeatRoot=repeat.getSvgRoot();
 if(!repeatRoot)throw new Error('rendered repeat SVG root missing for stable hover');
 const repeatPath=repeat.pathObject&&repeat.pathObject.svgPath;
 if(!repeatPath)throw new Error('rendered repeat has no Blockly tooltip-bound path object');
 if(!repeatRoot.contains(repeatPath))throw new Error('Blockly tooltip-bound repeat path is outside rendered repeat root');
 if(repeatPath.tooltip!==repeat)throw new Error('rendered repeat path is not bound to the repeat tooltip object');
 const rb=repeatRoot.getBoundingClientRect();
 const samePath=(x,y)=>document.elementFromPoint(x,y)===repeatPath;
 const clearanceAt=(x,y)=>{
   let clearance=0;
   for(let r=1;r<=8;r++){
     const points=[
       [x-r,y],[x+r,y],[x,y-r],[x,y+r],
       [x-r,y-r],[x-r,y+r],[x+r,y-r],[x+r,y+r]
     ];
     if(!points.every(([px,py])=>samePath(px,py)))break;
     clearance=r;
   }
   return clearance;
 };
 let best=null;
 for(let y=Math.ceil(rb.top)+2;y<Math.floor(rb.bottom);y+=2){
   for(let x=Math.ceil(rb.left)+2;x<Math.floor(rb.right);x+=2){
     if(!samePath(x,y))continue;
     const clearance=clearanceAt(x,y);
     if(!best||clearance>best.clearance)best={x:x,y:y,clearance:clearance};
   }
 }
 if(!best||best.clearance<3)throw new Error('no stable interior hover point on exact Blockly tooltip-bound repeat path');
 const neighbours=[[best.x+1,best.y],[best.x-1,best.y],[best.x,best.y+1],[best.x,best.y-1]];
 const settle=neighbours.find(([sx,sy])=>samePath(sx,sy)&&clearanceAt(sx,sy)>=2);
 if(!settle)throw new Error('no stable settle point on exact Blockly tooltip-bound repeat path');
 const outsideCandidates=[
   [Math.max(1,Math.floor(rb.left)-8),best.y],
   [Math.min(innerWidth-2,Math.ceil(rb.right)+8),best.y],
   [best.x,Math.max(1,Math.floor(rb.top)-8)],
   [best.x,Math.min(innerHeight-2,Math.ceil(rb.bottom)+8)],
 ];
 const outside=outsideCandidates.find(([ox,oy])=>{
   const hit=document.elementFromPoint(ox,oy);
   return hit&&!repeatRoot.contains(hit);
 });
 if(!outside)throw new Error('no outside hover origin for stable exact-path trajectory');
 return {
   x:best.x-1,y:best.y-1,width:2,height:2,
   entryX:best.x,entryY:best.y,settleX:settle[0],settleY:settle[1],
   outsideX:outside[0],outsideY:outside[1],
   hitTag:repeatPath.tagName,
   hitClass:String((repeatPath.getAttribute&&repeatPath.getAttribute('class'))||''),
   stableClearance:best.clearance
 };
})()'''

# The canonical probe reads this expression immediately before its one hover.
probe.REPEAT_HOVER_RECT = _STABLE_REPEAT_HOVER_RECT

_POST_HOVER_INSTALL = r'''((x,y) => {
  const key='__webeeblocksCiTooltipPostHover';
  const old=window[key];
  if(old&&old.cleanup)old.cleanup();

  const target=document.elementFromPoint(x,y);
  const targetClass=String((target&&target.getAttribute&&target.getAttribute('class'))||'');
  if(!target||!targetClass.includes('blocklyPath'))throw new Error('post-hover target is not the exact public Blockly path');

  const tooltip=window.Blockly&&Blockly.Tooltip;
  const hasVisible=!!tooltip&&typeof tooltip.isVisible==='function';
  const hasGetDiv=!!tooltip&&typeof tooltip.getDiv==='function';
  const div=hasGetDiv ? tooltip.getDiv() : document.querySelector('.blocklyTooltipDiv');
  if(!div)throw new Error('public Blockly tooltip div unavailable for post-hover observation');

  const now=()=>performance.now();
  const classOf=node=>String((node&&node.getAttribute&&node.getAttribute('class'))||'');
  const pack=e=>({
    type:e.type,at:now(),x:e.clientX,y:e.clientY,buttons:e.buttons,
    targetTag:(e.target&&e.target.tagName)||'',targetClass:classOf(e.target),
    relatedClass:classOf(e.relatedTarget),
    targetIsObserved:e.target===target,relatedIsObserved:e.relatedTarget===target,
    targetSharesTooltip:!!(e.target&&target&&e.target.tooltip&&e.target.tooltip===target.tooltip),
    relatedSharesTooltip:!!(e.relatedTarget&&target&&e.relatedTarget.tooltip&&e.relatedTarget.tooltip===target.tooltip)
  });
  const state={
    installedAt:now(),target:target,events:[],lifecycle:[],mutations:[],cleanup:null,
    initial:{focused:document.hasFocus(),visibility:document.visibilityState,
      tooltipVisible:hasVisible ? !!tooltip.isVisible() : null,
      divDisplay:getComputedStyle(div).display,
      divText:String(div.innerText||div.textContent||'').trim().slice(0,240)}
  };
  const cap=(list,value,limit=128)=>{list.push(value);if(list.length>limit)list.shift();};
  const types=['mousemove','mouseover','mouseout','pointermove','pointerover','pointerout'];
  const docHandlers={};
  const targetHandlers={};
  for(const type of types){
    docHandlers[type]=e=>cap(state.events,Object.assign({phase:'document'},pack(e)));
    targetHandlers[type]=e=>cap(state.events,Object.assign({phase:'target'},pack(e)));
    document.addEventListener(type,docHandlers[type],true);
    target.addEventListener(type,targetHandlers[type],false);
  }
  const onFocus=()=>cap(state.lifecycle,{kind:'focus',at:now()});
  const onBlur=()=>cap(state.lifecycle,{kind:'blur',at:now()});
  const onVisibility=()=>cap(state.lifecycle,{kind:'visibility',at:now(),value:document.visibilityState});
  window.addEventListener('focus',onFocus,true);
  window.addEventListener('blur',onBlur,true);
  document.addEventListener('visibilitychange',onVisibility,true);

  const observer=new MutationObserver(records=>{
    for(const record of records){
      cap(state.mutations,{
        at:now(),type:record.type,attributeName:record.attributeName||'',
        display:getComputedStyle(div).display,
        text:String(div.innerText||div.textContent||'').trim().slice(0,240)
      });
    }
  });
  observer.observe(div,{attributes:true,attributeFilter:['style','class'],childList:true,subtree:true,characterData:true});

  state.cleanup=()=>{
    observer.disconnect();
    for(const type of types){
      document.removeEventListener(type,docHandlers[type],true);
      target.removeEventListener(type,targetHandlers[type],false);
    }
    window.removeEventListener('focus',onFocus,true);
    window.removeEventListener('blur',onBlur,true);
    document.removeEventListener('visibilitychange',onVisibility,true);
  };
  window[key]=state;
  return true;
})(%s,%s)'''

_POST_HOVER_SNAPSHOT = r'''((x,y) => {
  const s=window.__webeeblocksCiTooltipPostHover;
  if(!s)return null;
  const tooltip=window.Blockly&&Blockly.Tooltip;
  const hasVisible=!!tooltip&&typeof tooltip.isVisible==='function';
  const hasGetDiv=!!tooltip&&typeof tooltip.getDiv==='function';
  const div=hasGetDiv ? tooltip.getDiv() : document.querySelector('.blocklyTooltipDiv');
  const hit=document.elementFromPoint(x,y);
  return {
    installedAt:s.installedAt,initial:s.initial,
    current:{
      at:performance.now(),focused:document.hasFocus(),visibility:document.visibilityState,
      hitTag:(hit&&hit.tagName)||'',hitClass:String((hit&&hit.getAttribute&&hit.getAttribute('class'))||''),
      hitIsObserved:hit===s.target,
      hitSharesTooltip:!!(hit&&s.target&&hit.tooltip&&hit.tooltip===s.target.tooltip),
      tooltipVisible:hasVisible ? !!tooltip.isVisible() : null,
      divExists:!!div,divDisplay:div ? getComputedStyle(div).display : null,
      divText:div ? String(div.innerText||div.textContent||'').trim().slice(0,240) : null
    },
    events:s.events.slice(),lifecycle:s.lifecycle.slice(),mutations:s.mutations.slice()
  };
})(%s,%s)'''

_POST_HOVER_CLEANUP = r'''(() => {
  const key='__webeeblocksCiTooltipPostHover';
  const s=window[key];
  if(!s)return false;
  if(s.cleanup)s.cleanup();
  delete window[key];
  return true;
})()'''


def _tooltip_visible(entries: object) -> bool:
    if not isinstance(entries, list):
        return False
    return any(
        isinstance(entry, dict)
        and "tooltip" in str(entry.get("className", "")).lower()
        and str(entry.get("text", "")).strip()
        for entry in entries
    )


def _snapshot(c: probe.Cdp) -> object:
    rect = getattr(c, "_webeeblocks_post_hover_rect", None)
    if not rect:
        return None
    return _ORIGINAL_EVAL(
        c,
        _POST_HOVER_SNAPSHOT
        % (float(rect["settleX"]), float(rect["settleY"])),
    )


def _emit(c: probe.Cdp, reason: str, cleanup: bool) -> None:
    snapshot = _snapshot(c)
    print(
        "WEBEEBLOCKS_TOOLTIP_POST_HOVER_DIAGNOSTIC "
        + json.dumps({"reason": reason, "snapshot": snapshot}, sort_keys=True)
    )
    if cleanup:
        _ORIGINAL_EVAL(c, _POST_HOVER_CLEANUP)
        c._webeeblocks_post_hover_active = False


def hover_with_post_hover_diagnostics(self: probe.Cdp, rect: dict[str, object]) -> None:
    # Keep the integrated focus/path/delivery diagnostic and one real hover.
    _ORIGINAL_HOVER(self, rect)
    installed = _ORIGINAL_EVAL(
        self,
        _POST_HOVER_INSTALL
        % (float(rect["settleX"]), float(rect["settleY"])),
    )
    if not installed:
        raise RuntimeError("passive post-hover tooltip observer could not be installed")
    self._webeeblocks_post_hover_rect = dict(rect)
    self._webeeblocks_post_hover_started = time.monotonic()
    self._webeeblocks_post_hover_late_emitted = False
    self._webeeblocks_post_hover_active = True


def eval_with_post_hover_diagnostics(self: probe.Cdp, expr: str):
    result = _ORIGINAL_EVAL(self, expr)
    if expr != probe.VISIBLE_OVERLAY or not getattr(
        self, "_webeeblocks_post_hover_active", False
    ):
        return result

    if _tooltip_visible(result):
        _emit(self, "public-tooltip-visible", cleanup=True)
        return result

    elapsed = time.monotonic() - getattr(
        self, "_webeeblocks_post_hover_started", time.monotonic()
    )
    # The expected public tooltip delay is 750 ms.  A single late snapshot after
    # 4.25 s cannot make a correctly scheduled tooltip pass, while preserving
    # evidence from almost the entire unchanged 5 s oracle window.
    if elapsed >= 4.25 and not getattr(
        self, "_webeeblocks_post_hover_late_emitted", False
    ):
        self._webeeblocks_post_hover_late_emitted = True
        _emit(self, "still-absent-after-4.25s", cleanup=False)
    return result


probe.Cdp.hover = hover_with_post_hover_diagnostics
probe.Cdp.eval = eval_with_post_hover_diagnostics

if __name__ == "__main__":
    probe.main()
