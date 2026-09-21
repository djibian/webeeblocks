#!/usr/bin/env python3
"""Run the canonical student UI probe with deterministic real-hover reset and passive diagnostics.

The product/runtime probe and existing exact-path delivery boundary remain
authoritative.  Natural #414 evidence has demonstrated two distinct real-pointer
failure modes: a tooltip can render and be hidden by an edge-adjacent path
transition, and a later stable same-path hover can receive ordinary pointer input
without scheduling any visible tooltip.  Blockly's tooltip state intentionally
poisons an element after showing it and clears that poison when mouseover changes
tooltip owner.  A background-only first move cannot repair stale owner/poison
state if a prior pointerout was lost.

This wrapper therefore keeps the same three real pointer moves but makes their
first point a stable path belonging to a different tooltip owner, then chooses
entry/settle points well inside the exact tooltip-bound repeat path.  This is a
deterministic real-pointer precondition, not an outcome-conditioned retry.  The
5 s public visible/non-empty/localized tooltip oracle and ordinary exit assertion
remain unchanged.

After the hover it retains passive browser observations: page focus/visibility,
ordinary mouse/pointer traffic, public tooltip DOM mutations/visibility, and
exact DOM/tooltip-owner identity. It does not wrap timers or Blockly lifecycle
functions, mutate tooltip/workspace state, synthesize visibility, retry the
hover, or weaken the oracle.
"""

from __future__ import annotations

import json
import time

import probe
import probe_entry


_ORIGINAL_EVAL = probe.Cdp.eval
_ORIGINAL_HOVER = probe.Cdp.hover

# Blockly 13.2.x tooltip semantics leave a shown element poisoned until an
# onMouseOver transition changes tooltip owner (or a completed pointerout clears
# the state).  #491 showed that a stable repeat-path entry can still receive
# pointerover/pointermove while producing no tooltip at all.  Make the existing
# first/outside move causally useful: hit a different tooltip-bound block before
# entering the repeat block.  Keep repeat entry/settle on one exact DOM path and
# away from SVG hit-test edges to retain the independent post-fire lesson from
# the earlier #485 recurrence.
_RESET_REPEAT_HOVER_RECT = r'''(() => {
 const repeat=workspace.getBlocksByType('controls_repeat_ext',false)[0];
 const resetBlock=workspace.getBlocksByType('controls_if',false)[0];
 if(!repeat)throw new Error('rendered repeat block missing for hover');
 if(!resetBlock)throw new Error('rendered condition block missing for tooltip-owner reset');
 const repeatRoot=repeat.getSvgRoot();
 const resetRoot=resetBlock.getSvgRoot();
 if(!repeatRoot||!resetRoot)throw new Error('rendered tooltip-owner reset roots missing');
 const repeatPath=repeat.pathObject&&repeat.pathObject.svgPath;
 const resetPath=resetBlock.pathObject&&resetBlock.pathObject.svgPath;
 if(!repeatPath||!resetPath)throw new Error('rendered tooltip-bound paths missing');
 if(!repeatRoot.contains(repeatPath)||!resetRoot.contains(resetPath))throw new Error('tooltip-bound path outside rendered block root');
 if(repeatPath.tooltip!==repeat||resetPath.tooltip!==resetBlock)throw new Error('rendered path is not bound to its block tooltip object');
 if(resetPath.tooltip===repeatPath.tooltip)throw new Error('tooltip-owner reset must use a different tooltip owner');

 const same=(path,x,y)=>document.elementFromPoint(x,y)===path;
 const clearanceAt=(path,x,y,maxRadius)=>{
   let clearance=0;
   for(let r=1;r<=maxRadius;r++){
     const points=[
       [x-r,y],[x+r,y],[x,y-r],[x,y+r],
       [x-r,y-r],[x-r,y+r],[x+r,y-r],[x+r,y+r]
     ];
     if(!points.every(([px,py])=>same(path,px,py)))break;
     clearance=r;
   }
   return clearance;
 };
 const bestPoint=(root,path,maxRadius)=>{
   const rb=root.getBoundingClientRect();
   let best=null;
   for(let y=Math.ceil(rb.top)+2;y<Math.floor(rb.bottom);y+=2){
     for(let x=Math.ceil(rb.left)+2;x<Math.floor(rb.right);x+=2){
       if(!same(path,x,y))continue;
       const clearance=clearanceAt(path,x,y,maxRadius);
       if(!best||clearance>best.clearance)best={x:x,y:y,clearance:clearance};
     }
   }
   return best;
 };

 const entry=bestPoint(repeatRoot,repeatPath,8);
 if(!entry||entry.clearance<3)throw new Error('no stable interior hover point on exact Blockly tooltip-bound repeat path');
 const neighbours=[[entry.x+1,entry.y],[entry.x-1,entry.y],[entry.x,entry.y+1],[entry.x,entry.y-1]];
 const settle=neighbours.find(([sx,sy])=>same(repeatPath,sx,sy)&&clearanceAt(repeatPath,sx,sy,8)>=2);
 if(!settle)throw new Error('no stable settle point on exact Blockly tooltip-bound repeat path');

 const reset=bestPoint(resetRoot,resetPath,6);
 if(!reset||reset.clearance<2)throw new Error('no stable real-pointer tooltip-owner reset point');
 if(repeatRoot.contains(resetPath))throw new Error('tooltip-owner reset path unexpectedly belongs to repeat root');
 if(document.elementFromPoint(reset.x,reset.y)!==resetPath)throw new Error('tooltip-owner reset point lost exact DOM identity');

 return {
   x:entry.x-1,y:entry.y-1,width:2,height:2,
   entryX:entry.x,entryY:entry.y,settleX:settle[0],settleY:settle[1],
   outsideX:reset.x,outsideY:reset.y,
   hitTag:repeatPath.tagName,
   hitClass:String((repeatPath.getAttribute&&repeatPath.getAttribute('class'))||''),
   stableClearance:entry.clearance,
   resetTag:resetPath.tagName,
   resetClass:String((resetPath.getAttribute&&resetPath.getAttribute('class'))||''),
   resetClearance:reset.clearance
 };
})()'''

# The canonical probe reads this expression immediately before its one hover.
probe.REPEAT_HOVER_RECT = _RESET_REPEAT_HOVER_RECT

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
