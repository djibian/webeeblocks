#!/usr/bin/env python3
"""Run the canonical student UI probe with a stable single-entry real hover.

Natural #414 recurrences established two distinct harness-side instability
boundaries while preserving the product/runtime behavior: the canonical adjacent
settle move deliberately clears and replaces Blockly's 750 ms tooltip timer, and
a later sibling-path transition can hide an already rendered tooltip before the
public polling oracle observes it.  This wrapper therefore keeps one ordinary
real pointer entry on the exact tooltip-bound repeat path, but chooses that entry
well inside one DOM path and then leaves the pointer stationary until the
unchanged 5 s visible/non-empty/localized oracle observes the public tooltip.

The existing same-session focus and public pointer-delivery checks remain
mandatory.  Passive post-hover observations remain diagnostic only.  This module
does not wrap Blockly timers, synthesize tooltip visibility, mutate Blockly or
workspace state, retry the hover, or weaken the acceptance timeout/assertions.
"""

from __future__ import annotations

import json
import time

import probe
import probe_entry


_ORIGINAL_EVAL = probe.Cdp.eval


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
   entryX:best.x,entryY:best.y,settleX:best.x,settleY:best.y,
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
        % (float(rect["entryX"]), float(rect["entryY"])),
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


def _perform_single_entry_with_delivery(
    self: probe.Cdp, rect: dict[str, object]
) -> None:
    focus = probe_entry._same_session_focus(self)
    gesture = probe_entry._gesture_snapshot(self)

    # Resolve geometry in the focused frame, perform the required ordinary move
    # to a point outside the repeat, and only then bind the delivery observer to
    # Blockly's current exact repeat path. This ordering closes the exact-head
    # refutation where the outside move could replace the pre-bound path node.
    probe_entry._refresh_hover_geometry(self, rect)
    outside_x = float(rect["outsideX"])
    outside_y = float(rect["outsideY"])
    self.call(
        "Input.dispatchMouseEvent",
        {"type": "mouseMoved", "x": outside_x, "y": outside_y},
    )
    time.sleep(0.1)
    probe_entry._install_delivery_probe(self, rect, outside_x, outside_y)

    delivery = None
    try:
        # Exactly one ordinary real entry on the current exact path.  Do not
        # dispatch the former adjacent settle move: Blockly schedules its tooltip
        # from this one target pointermove and the pointer then remains stationary.
        self.call(
            "Input.dispatchMouseEvent",
            {"type": "mouseMoved", "x": rect["entryX"], "y": rect["entryY"]},
        )
        time.sleep(0.04)
        delivery = probe_entry._read_delivery(self, rect)
    except BaseException:
        try:
            delivery = probe_entry._read_delivery(self, rect)
            print(
                "WEBEEBLOCKS_TOOLTIP_CAUSAL_DIAGNOSTIC "
                + json.dumps(
                    {"focus": focus, "gesture": gesture, "delivery": delivery},
                    sort_keys=True,
                )
            )
        except Exception:
            try:
                probe_entry._cleanup_delivery_probe(self)
            except Exception:
                pass
        raise

    if not delivery:
        raise RuntimeError("real tooltip hover produced no public pointer-delivery observation")
    evidence = {"focus": focus, "gesture": gesture, "delivery": delivery}
    print("WEBEEBLOCKS_TOOLTIP_CAUSAL_DIAGNOSTIC " + json.dumps(evidence, sort_keys=True))

    # The delivery probe is deliberately installed after the outside move. One
    # document move plus the entry events therefore proves the single exact-path
    # entry without observing or creating an extra target move.
    document = delivery.get("document", {})
    if document.get("mousemove", 0) < 1 or document.get("pointermove", 0) < 1:
        raise RuntimeError(
            "real tooltip hover did not deliver the single public document move event: "
            + json.dumps(evidence, sort_keys=True)
        )
    if document.get("mouseover", 0) < 1 or document.get("pointerover", 0) < 1:
        raise RuntimeError(
            "real tooltip hover did not deliver public document entry events: "
            + json.dumps(evidence, sort_keys=True)
        )

    target = delivery.get("target", {})
    if (
        target.get("mousemove", 0) < 1
        or target.get("pointermove", 0) < 1
        or target.get("mouseover", 0) < 1
        or target.get("pointerover", 0) < 1
    ):
        raise RuntimeError(
            "real tooltip hover did not reach the exact Blockly path at target phase: "
            + json.dumps(evidence, sort_keys=True)
        )
    mouse_sequence = [
        event
        for event in delivery.get("targetSequence", [])
        if event in ("mouseover", "mouseout", "mousemove")
    ]
    if not mouse_sequence or mouse_sequence[-1] != "mousemove":
        raise RuntimeError(
            "real tooltip hover did not finish with a stable exact-path target mousemove: "
            + json.dumps(evidence, sort_keys=True)
        )

    hit_class = str(delivery.get("hitClass", ""))
    target_mouse = delivery.get("targetLast", {}).get("mousemove", {})
    target_pointer = delivery.get("targetLast", {}).get("pointermove", {})
    if (
        "blocklyPath" not in hit_class
        or "blocklyPath" not in str(target_mouse.get("targetClass", ""))
        or "blocklyPath" not in str(target_pointer.get("targetClass", ""))
        or target_mouse.get("targetIsObserved") is not True
        or target_pointer.get("targetIsObserved") is not True
    ):
        raise RuntimeError(
            "real tooltip hover did not settle on the exact current public Blockly path: "
            + json.dumps(evidence, sort_keys=True)
        )


def hover_with_post_hover_diagnostics(self: probe.Cdp, rect: dict[str, object]) -> None:
    _perform_single_entry_with_delivery(self, rect)
    installed = _ORIGINAL_EVAL(
        self,
        _POST_HOVER_INSTALL % (float(rect["entryX"]), float(rect["entryY"])),
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
