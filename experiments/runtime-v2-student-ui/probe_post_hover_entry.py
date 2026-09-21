#!/usr/bin/env python3
"""Run the canonical student UI probe with passive post-hover diagnostics.

The canonical product/runtime probe and the existing exact-path delivery boundary
remain authoritative.  This wrapper adds only passive browser observations after
the one canonical hover has completed: page focus/visibility, ordinary
mouse/pointer traffic, and public tooltip DOM mutations/visibility.  It does not
wrap timers, dispatch additional input, mutate Blockly/workspace state, retry the
hover, or change the 5 s tooltip oracle.
"""

from __future__ import annotations

import json
import time

import probe
import probe_entry


_ORIGINAL_EVAL = probe.Cdp.eval
_ORIGINAL_HOVER = probe.Cdp.hover

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
    relatedClass:classOf(e.relatedTarget)
  });
  const state={
    installedAt:now(),events:[],lifecycle:[],mutations:[],cleanup:null,
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
    # Keep the already-integrated exact-path/focus/delivery diagnostic unchanged.
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
