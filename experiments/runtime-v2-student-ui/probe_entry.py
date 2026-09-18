#!/usr/bin/env python3
"""Run the canonical student UI probe with passive tooltip diagnostics.

The product/runtime probe remains authoritative. This entrypoint changes no
student-visible behavior and never retries a tooltip interaction. It passively
records the real browser delivery, exported Blockly tooltip observables, and the
causal scheduling/firing/cancellation of 1 ms / HOVER_MS timers around the one
existing canonical hover. It also attempts a transparent observation of exported
Blockly Tooltip block/unblock calls as supporting evidence. The canonical 5 s
visible/non-empty/localized tooltip oracle remains unchanged.
"""

from __future__ import annotations

import json
import time

import probe


_ORIGINAL_EVAL = probe.Cdp.eval
_ORIGINAL_HOVER = probe.Cdp.hover

_LIFECYCLE_INSTALL = r'''(() => {
  const key='__webeeblocksCiTooltipLifecycle';
  if(window[key])return !!window[key].installed;
  const tooltip=window.Blockly&&Blockly.Tooltip;
  if(!tooltip||typeof tooltip.block!=='function'||typeof tooltip.unblock!=='function')return false;
  const state={installed:false,transitions:[],originalBlock:tooltip.block,originalUnblock:tooltip.unblock};
  const record=kind=>{
    state.transitions.push({kind:kind,at:performance.now()});
    if(state.transitions.length>64)state.transitions.shift();
  };
  const block=function(...args){record('block');return state.originalBlock.apply(this,args);};
  const unblock=function(...args){record('unblock');return state.originalUnblock.apply(this,args);};
  try{
    tooltip.block=block;
    tooltip.unblock=unblock;
    state.installed=tooltip.block===block&&tooltip.unblock===unblock;
  }catch(_){state.installed=false;}
  window[key]=state;
  return state.installed;
})()'''

_TIMER_INSTALL = r'''(() => {
  const key='__webeeblocksCiTooltipTimers';
  if(window[key]&&window[key].installed)return true;
  const originalSetTimeout=window.setTimeout;
  const originalClearTimeout=window.clearTimeout;
  const state={installed:false,next:1,events:[],tracked:{},originalSetTimeout:originalSetTimeout,originalClearTimeout:originalClearTimeout};
  const record=entry=>{
    state.events.push(Object.assign({at:performance.now()},entry));
    if(state.events.length>96)state.events.shift();
  };
  const wrapperSetTimeout=function(handler,delay,...args){
    const numeric=Number(delay);
    const observed=Number.isFinite(numeric)&&(Math.round(numeric)===1||Math.round(numeric)===750);
    const token=observed ? state.next++ : null;
    const stack=observed ? String((new Error()).stack||'').split('\n').slice(1,8).join(' | ') : '';
    let wrapped=handler;
    if(observed&&typeof handler==='function'){
      wrapped=function(...callbackArgs){
        record({kind:'fire',token:token,delay:numeric});
        delete state.tracked[String(this&&this.__webeeblocksTimerId||'')];
        return handler.apply(this,callbackArgs);
      };
    }
    const nativeId=originalSetTimeout.call(window,wrapped,delay,...args);
    if(observed){
      const id=String(nativeId);
      state.tracked[id]={token:token,delay:numeric,stack:stack};
      if(typeof wrapped==='function'){
        try{Object.defineProperty(wrapped,'__webeeblocksTimerId',{value:nativeId,configurable:true});}catch(_){}
      }
      record({kind:'schedule',token:token,id:id,delay:numeric,stack:stack});
    }
    return nativeId;
  };
  const wrapperClearTimeout=function(nativeId){
    const id=String(nativeId);
    const tracked=state.tracked[id];
    if(tracked){
      record({kind:'clear',token:tracked.token,id:id,delay:tracked.delay});
      delete state.tracked[id];
    }
    return originalClearTimeout.call(window,nativeId);
  };
  window.setTimeout=wrapperSetTimeout;
  window.clearTimeout=wrapperClearTimeout;
  state.installed=window.setTimeout===wrapperSetTimeout&&window.clearTimeout===wrapperClearTimeout;
  window[key]=state;
  return state.installed;
})()'''

_TIMER_STATE = r'''(() => {
  const s=window.__webeeblocksCiTooltipTimers;
  const life=window.__webeeblocksCiTooltipLifecycle;
  if(!s)return null;
  return {
    installed:!!s.installed,
    events:s.events.slice(),
    tracked:Object.entries(s.tracked).map(([id,value])=>({id:id,token:value.token,delay:value.delay,stack:value.stack})),
    lifecycleObserverInstalled:!!(life&&life.installed),
    lifecycleTransitions:life ? life.transitions.slice() : []
  };
})()'''

_TIMER_RESTORE = r'''(() => {
  const s=window.__webeeblocksCiTooltipTimers;
  if(!s)return false;
  if(window.setTimeout!==s.originalSetTimeout)window.setTimeout=s.originalSetTimeout;
  if(window.clearTimeout!==s.originalClearTimeout)window.clearTimeout=s.originalClearTimeout;
  s.installed=false;
  return true;
})()'''


def _timer_signature(state: object) -> str:
    return json.dumps(state, sort_keys=True, separators=(",", ":"))


def eval_with_passive_diagnostics(self: probe.Cdp, expr: str):
    result = _ORIGINAL_EVAL(self, expr)

    if not getattr(self, "_webeeblocks_lifecycle_checked", False):
        try:
            installed = _ORIGINAL_EVAL(self, _LIFECYCLE_INSTALL)
            if installed:
                self._webeeblocks_lifecycle_checked = True
        except Exception:
            # Blockly may not exist yet during the normal readiness loop.
            pass

    if expr == probe.VISIBLE_OVERLAY and getattr(self, "_webeeblocks_timer_probe", False):
        state = _ORIGINAL_EVAL(self, _TIMER_STATE)
        signature = _timer_signature(state)
        if signature != getattr(self, "_webeeblocks_last_timer_signature", None):
            self._webeeblocks_last_timer_signature = signature
            print("WEBEEBLOCKS_TOOLTIP_TIMER_DIAGNOSTIC " + json.dumps(state, sort_keys=True))
        tooltip_visible = any(
            isinstance(entry, dict)
            and "tooltip" in str(entry.get("className", "")).lower()
            and str(entry.get("text", "")).strip()
            for entry in (result or [])
        )
        if tooltip_visible:
            _ORIGINAL_EVAL(self, _TIMER_RESTORE)
            self._webeeblocks_timer_probe = False

    return result


def _same_session_focus(c: probe.Cdp) -> dict[str, object]:
    c.call("Page.bringToFront")
    deadline = time.time() + 2.0
    state = None
    while time.time() < deadline:
        state = c.eval(
            "({focused:document.hasFocus(),visibility:document.visibilityState,workspace:!!window.workspace})"
        )
        if (
            state
            and state.get("focused")
            and state.get("visibility") == "visible"
            and state.get("workspace")
        ):
            return state
        time.sleep(0.05)
    raise RuntimeError(
        "Robot Window lost visible focus immediately before real tooltip hover: "
        + json.dumps(state, sort_keys=True)
    )


def _gesture_snapshot(c: probe.Cdp) -> dict[str, object]:
    state = c.eval(
        r'''(() => {
          const gesture=window.Blockly&&Blockly.Gesture;
          const available=!!gesture&&typeof gesture.inProgress==='function';
          return {available:available,inProgress:available ? !!gesture.inProgress() : null};
        })()'''
    )
    if not state or not state.get("available"):
        raise RuntimeError(
            "Blockly gesture lifecycle is unavailable before real tooltip hover: "
            + json.dumps(state, sort_keys=True)
        )
    return state


def _tooltip_snapshot(c: probe.Cdp, rect: dict[str, object]) -> dict[str, object]:
    settle_x = float(rect["settleX"])
    settle_y = float(rect["settleY"])
    expression = r'''((x,y) => {
      const tooltip=window.Blockly&&Blockly.Tooltip;
      const target=document.elementFromPoint(x,y);
      const hasVisible=!!tooltip&&typeof tooltip.isVisible==='function';
      const hasGetDiv=!!tooltip&&typeof tooltip.getDiv==='function';
      const div=hasGetDiv ? tooltip.getDiv() : null;
      const life=window.__webeeblocksCiTooltipLifecycle;
      const classOf=node=>String((node&&node.getAttribute&&node.getAttribute('class'))||'');
      const tooltipChain=[];
      const seen=new Set();
      let cursor=target;
      for(let depth=0;depth<8&&cursor&&!seen.has(cursor);depth+=1){
        seen.add(cursor);
        const value=cursor.tooltip;
        if(value===undefined||value===null)break;
        const kind=typeof value;
        const entry={kind:kind};
        if(kind==='string'){
          entry.text=value.slice(0,200);
          tooltipChain.push(entry);
          break;
        }
        if(kind==='function'){
          entry.name=String(value.name||'');
          tooltipChain.push(entry);
          break;
        }
        if(kind==='object'){
          entry.constructor=String((value.constructor&&value.constructor.name)||'');
          entry.hasTooltip=Object.prototype.hasOwnProperty.call(value,'tooltip')||('tooltip' in value);
          tooltipChain.push(entry);
          cursor=value;
          continue;
        }
        entry.value=String(value).slice(0,200);
        tooltipChain.push(entry);
        break;
      }
      return {
        available:!!tooltip,
        hasIsVisible:hasVisible,
        hasGetDiv:hasGetDiv,
        visible:hasVisible ? !!tooltip.isVisible() : null,
        targetClass:classOf(target),
        targetHasTooltip:!!(target&&target.tooltip),
        targetMouseOverBound:!!(target&&target.mouseOverWrapper_),
        targetMouseOutBound:!!(target&&target.mouseOutWrapper_),
        tooltipChain:tooltipChain,
        divExists:!!div,
        divDisplay:div ? getComputedStyle(div).display : null,
        divText:div ? String(div.innerText||div.textContent||'').trim().slice(0,200) : null,
        lifecycleObserverInstalled:!!(life&&life.installed),
        lifecycleTransitions:life ? life.transitions.slice() : []
      };
    })(%s,%s)''' % (settle_x, settle_y)
    state = c.eval(expression)
    if (
        not state
        or not state.get("available")
        or not state.get("hasIsVisible")
        or not state.get("hasGetDiv")
    ):
        raise RuntimeError(
            "Exported Blockly tooltip observables are unavailable for passive diagnostics: "
            + json.dumps(state, sort_keys=True)
        )
    return state


def _install_delivery_probe(c: probe.Cdp, rect: dict[str, object]) -> None:
    settle_x = float(rect["settleX"])
    settle_y = float(rect["settleY"])
    expression = r'''((x,y) => {
      const key='__webeeblocksCiTooltipDelivery';
      if(window[key]&&window[key].cleanup)window[key].cleanup();
      const target=document.elementFromPoint(x,y);
      const targetClass=String((target&&target.getAttribute&&target.getAttribute('class'))||'');
      if(!target||!targetClass.includes('blocklyPath'))throw new Error('tooltip delivery target is not the exact public Blockly path');
      const types=['mousemove','mouseover','mouseout','pointermove','pointerover','pointerout'];
      const state={document:{},target:{},last:{},targetLast:{},targetSequence:[],cleanup:null};
      const pack=e=>({
        x:e.clientX,y:e.clientY,buttons:e.buttons,defaultPrevented:e.defaultPrevented,
        targetTag:(e.target&&e.target.tagName)||'',
        targetClass:String((e.target&&e.target.getAttribute&&e.target.getAttribute('class'))||''),
        relatedClass:String((e.relatedTarget&&e.relatedTarget.getAttribute&&e.relatedTarget.getAttribute('class'))||'')
      });
      const documentHandlers={};
      const targetHandlers={};
      for(const type of types){
        state.document[type]=0; state.target[type]=0;
        documentHandlers[type]=e=>{state.document[type]+=1;state.last[type]=pack(e);};
        targetHandlers[type]=e=>{state.target[type]+=1;state.targetLast[type]=pack(e);state.targetSequence.push(type);};
        document.addEventListener(type,documentHandlers[type],true);
        target.addEventListener(type,targetHandlers[type],false);
      }
      state.cleanup=()=>{
        for(const type of types){
          document.removeEventListener(type,documentHandlers[type],true);
          target.removeEventListener(type,targetHandlers[type],false);
        }
      };
      window[key]=state;
      return true;
    })(%s,%s)''' % (settle_x, settle_y)
    c.eval(expression)


def _read_delivery(c: probe.Cdp, rect: dict[str, object]) -> dict[str, object]:
    settle_x = float(rect["settleX"])
    settle_y = float(rect["settleY"])
    expression = r'''((x,y) => {
      const key='__webeeblocksCiTooltipDelivery';
      const s=window[key];
      if(!s)return null;
      const hit=document.elementFromPoint(x,y);
      const result={
        document:s.document,target:s.target,last:s.last,targetLast:s.targetLast,targetSequence:s.targetSequence,
        hitTag:(hit&&hit.tagName)||'',
        hitClass:String((hit&&hit.getAttribute&&hit.getAttribute('class'))||'')
      };
      s.cleanup(); delete window[key];
      return result;
    })(%s,%s)''' % (settle_x, settle_y)
    return c.eval(expression)


def _cleanup_delivery_probe(c: probe.Cdp) -> None:
    c.eval(
        "(() => {const s=window.__webeeblocksCiTooltipDelivery;if(s&&s.cleanup)s.cleanup();delete window.__webeeblocksCiTooltipDelivery;return true;})()"
    )


def hover_with_passive_diagnostics(self: probe.Cdp, rect: dict[str, object]) -> None:
    focus = _same_session_focus(self)
    gesture = _gesture_snapshot(self)
    tooltip_before = _tooltip_snapshot(self, rect)
    _install_delivery_probe(self, rect)
    timer_installed = _ORIGINAL_EVAL(self, _TIMER_INSTALL)
    if not timer_installed:
        raise RuntimeError("passive tooltip timer observer could not be installed")
    self._webeeblocks_timer_probe = True
    self._webeeblocks_last_timer_signature = None
    try:
        # Exactly one unchanged canonical outside -> path -> settle trajectory.
        # No second hover, no wait for gesture state, and no outcome-based retry.
        _ORIGINAL_HOVER(self, rect)
        tooltip_after = _tooltip_snapshot(self, rect)
        delivery = _read_delivery(self, rect)
        timer_after = _ORIGINAL_EVAL(self, _TIMER_STATE)
    except BaseException:
        try:
            tooltip_after = _tooltip_snapshot(self, rect)
            delivery = _read_delivery(self, rect)
            timer_after = _ORIGINAL_EVAL(self, _TIMER_STATE)
            print(
                "WEBEEBLOCKS_TOOLTIP_CAUSAL_DIAGNOSTIC "
                + json.dumps(
                    {
                        "focus": focus,
                        "gesture": gesture,
                        "tooltipBefore": tooltip_before,
                        "tooltipAfter": tooltip_after,
                        "delivery": delivery,
                        "timerAfter": timer_after,
                    },
                    sort_keys=True,
                )
            )
        except Exception:
            try:
                _cleanup_delivery_probe(self)
            except Exception:
                pass
        raise

    if not delivery:
        raise RuntimeError("real tooltip hover produced no public pointer-delivery observation")
    evidence = {
        "focus": focus,
        "gesture": gesture,
        "tooltipBefore": tooltip_before,
        "tooltipAfter": tooltip_after,
        "delivery": delivery,
        "timerAfter": timer_after,
    }
    print("WEBEEBLOCKS_TOOLTIP_CAUSAL_DIAGNOSTIC " + json.dumps(evidence, sort_keys=True))

    document = delivery.get("document", {})
    if document.get("mousemove", 0) < 2 or document.get("pointermove", 0) < 2:
        raise RuntimeError(
            "real tooltip hover did not deliver bounded public document move events: "
            + json.dumps(evidence, sort_keys=True)
        )
    if document.get("mouseover", 0) < 1 or document.get("pointerover", 0) < 1:
        raise RuntimeError(
            "real tooltip hover did not deliver public document entry events: "
            + json.dumps(evidence, sort_keys=True)
        )

    target = delivery.get("target", {})
    if (
        target.get("mousemove", 0) < 2
        or target.get("pointermove", 0) < 2
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
    ):
        raise RuntimeError(
            "real tooltip hover did not settle on the exact public Blockly path: "
            + json.dumps(evidence, sort_keys=True)
        )


probe.Cdp.eval = eval_with_passive_diagnostics
probe.Cdp.hover = hover_with_passive_diagnostics

if __name__ == "__main__":
    probe.main()
