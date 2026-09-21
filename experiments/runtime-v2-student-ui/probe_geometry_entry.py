#!/usr/bin/env python3
"""Run the canonical student UI probe with passive tooltip geometry diagnostics.

This successor to the integrated #493/#485 instrumentation does not alter the
canonical real-pointer hover, Blockly state, tooltip state, workspace, timeout,
or acceptance oracle. It adds a second read-only observer after the canonical
hover so a natural #414 recurrence can explain why a client coordinate that was
an exclusive repeat-path hit before tooltip display can later hit another Blockly
path. Geometry is sampled at observer install, on public tooltip DOM mutations,
and at the existing visible/late polling boundaries.
"""

from __future__ import annotations

import json
import time

import probe
import probe_post_hover_entry as base


_BASE_HOVER = probe.Cdp.hover
_BASE_EVAL = probe.Cdp.eval

_GEOMETRY_INSTALL = r'''((x,y) => {
  const key='__webeeblocksCiTooltipGeometry';
  const old=window[key];
  if(old&&old.cleanup)old.cleanup();

  const classOf=node=>String((node&&node.getAttribute&&node.getAttribute('class'))||'');
  const ownerOf=node=>{
    const owner=node&&node.tooltip;
    return owner&&typeof owner==='object'
      ? {type:String(owner.type||''),id:String(owner.id||'')}
      : null;
  };
  const rectOf=node=>{
    if(!node||typeof node.getBoundingClientRect!=='function')return null;
    const r=node.getBoundingClientRect();
    return {x:r.x,y:r.y,left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height};
  };
  const ctmOf=node=>{
    if(!node||typeof node.getScreenCTM!=='function')return null;
    const m=node.getScreenCTM();
    return m ? {a:m.a,b:m.b,c:m.c,d:m.d,e:m.e,f:m.f} : null;
  };
  const styleOf=node=>{
    if(!node)return null;
    const s=getComputedStyle(node);
    return {display:s.display,position:s.position,left:s.left,top:s.top,transform:s.transform,
      zIndex:s.zIndex,pointerEvents:s.pointerEvents,visibility:s.visibility};
  };
  const pathsAt=(px,py)=>document.elementsFromPoint(px,py)
    .filter(node=>classOf(node).includes('blocklyPath'))
    .map(node=>({tag:node.tagName||'',className:classOf(node),owner:ownerOf(node)}));

  const repeat=window.workspace&&workspace.getBlocksByType('controls_repeat_ext',false)[0];
  const takeoff=window.workspace&&workspace.getBlocksByType('webeeblocks_v2_takeoff',false)[0];
  const repeatRoot=repeat&&repeat.getSvgRoot&&repeat.getSvgRoot();
  const takeoffRoot=takeoff&&takeoff.getSvgRoot&&takeoff.getSvgRoot();
  const repeatPath=repeat&&repeat.pathObject&&repeat.pathObject.svgPath;
  const takeoffPath=takeoff&&takeoff.pathObject&&takeoff.pathObject.svgPath;
  if(!repeat||!takeoff||!repeatRoot||!takeoffRoot||!repeatPath||!takeoffPath)
    throw new Error('tooltip geometry diagnostic requires rendered repeat and takeoff paths');

  const tooltip=window.Blockly&&Blockly.Tooltip;
  const div=tooltip&&typeof tooltip.getDiv==='function'
    ? tooltip.getDiv() : document.querySelector('.blocklyTooltipDiv');
  if(!div)throw new Error('public Blockly tooltip div unavailable for geometry diagnostic');

  const blocklyDiv=document.getElementById('blocklyDiv');
  const workspaceSvg=window.workspace&&typeof workspace.getParentSvg==='function'
    ? workspace.getParentSvg() : document.querySelector('.blocklySvg');
  const now=()=>performance.now();
  const visualViewport=()=>window.visualViewport ? {
    width:window.visualViewport.width,height:window.visualViewport.height,
    offsetLeft:window.visualViewport.offsetLeft,offsetTop:window.visualViewport.offsetTop,
    pageLeft:window.visualViewport.pageLeft,pageTop:window.visualViewport.pageTop,
    scale:window.visualViewport.scale
  } : null;
  const geometry=()=>{
    const hit=document.elementFromPoint(x,y);
    const de=document.documentElement;
    const body=document.body;
    return {
      at:now(),
      pointer:{x:x,y:y,hitTag:(hit&&hit.tagName)||'',hitClass:classOf(hit),hitOwner:ownerOf(hit),
        hitIsRepeatPath:hit===repeatPath,hitIsTakeoffPath:hit===takeoffPath,paths:pathsAt(x,y)},
      viewport:{innerWidth:window.innerWidth,innerHeight:window.innerHeight,scrollX:window.scrollX,scrollY:window.scrollY,
        devicePixelRatio:window.devicePixelRatio,visual:visualViewport()},
      document:{clientWidth:de&&de.clientWidth,clientHeight:de&&de.clientHeight,
        scrollWidth:de&&de.scrollWidth,scrollHeight:de&&de.scrollHeight,
        scrollLeft:de&&de.scrollLeft,scrollTop:de&&de.scrollTop,
        bodyScrollWidth:body&&body.scrollWidth,bodyScrollHeight:body&&body.scrollHeight,
        bodyClientWidth:body&&body.clientWidth,bodyClientHeight:body&&body.clientHeight},
      blocklyDiv:{rect:rectOf(blocklyDiv)},
      workspaceSvg:{rect:rectOf(workspaceSvg),ctm:ctmOf(workspaceSvg)},
      repeat:{rootRect:rectOf(repeatRoot),pathRect:rectOf(repeatPath),pathCtm:ctmOf(repeatPath),owner:ownerOf(repeatPath)},
      takeoff:{rootRect:rectOf(takeoffRoot),pathRect:rectOf(takeoffPath),pathCtm:ctmOf(takeoffPath),owner:ownerOf(takeoffPath)},
      tooltip:{rect:rectOf(div),style:styleOf(div),
        visible:tooltip&&typeof tooltip.isVisible==='function' ? !!tooltip.isVisible() : null,
        text:String(div.innerText||div.textContent||'').trim().slice(0,240)}
    };
  };
  const cap=(list,value,limit=48)=>{list.push(value);if(list.length>limit)list.shift();};
  const state={installedAt:now(),initial:null,mutations:[],viewEvents:[],cleanup:null};
  state.initial=geometry();

  const observer=new MutationObserver(records=>{
    for(const record of records){
      cap(state.mutations,{type:record.type,attributeName:record.attributeName||'',geometry:geometry()});
    }
  });
  observer.observe(div,{attributes:true,attributeFilter:['style','class'],childList:true,subtree:true,characterData:true});

  const recordView=event=>cap(state.viewEvents,{type:event.type,at:now(),
    scrollX:window.scrollX,scrollY:window.scrollY,visual:visualViewport()});
  window.addEventListener('scroll',recordView,true);
  window.addEventListener('resize',recordView,true);
  if(window.visualViewport){
    window.visualViewport.addEventListener('scroll',recordView,true);
    window.visualViewport.addEventListener('resize',recordView,true);
  }

  state.snapshot=()=>({installedAt:state.installedAt,initial:state.initial,current:geometry(),
    mutations:state.mutations.slice(),viewEvents:state.viewEvents.slice()});
  state.cleanup=()=>{
    observer.disconnect();
    window.removeEventListener('scroll',recordView,true);
    window.removeEventListener('resize',recordView,true);
    if(window.visualViewport){
      window.visualViewport.removeEventListener('scroll',recordView,true);
      window.visualViewport.removeEventListener('resize',recordView,true);
    }
  };
  window[key]=state;
  return true;
})(%s,%s)'''

_GEOMETRY_SNAPSHOT = r'''(() => {
  const s=window.__webeeblocksCiTooltipGeometry;
  return s&&s.snapshot ? s.snapshot() : null;
})()'''

_GEOMETRY_CLEANUP = r'''(() => {
  const key='__webeeblocksCiTooltipGeometry';
  const s=window[key];
  if(!s)return false;
  if(s.cleanup)s.cleanup();
  delete window[key];
  return true;
})()'''


def _emit_geometry(c: probe.Cdp, reason: str, cleanup: bool) -> None:
    snapshot = _BASE_EVAL(c, _GEOMETRY_SNAPSHOT)
    print(
        "WEBEEBLOCKS_TOOLTIP_GEOMETRY_DIAGNOSTIC "
        + json.dumps({"reason": reason, "snapshot": snapshot}, sort_keys=True)
    )
    if cleanup:
        _BASE_EVAL(c, _GEOMETRY_CLEANUP)
        c._webeeblocks_geometry_active = False


def hover_with_geometry(self: probe.Cdp, rect: dict[str, object]) -> None:
    # Preserve the integrated canonical hover and its exact acceptance prerequisites.
    _BASE_HOVER(self, rect)
    installed = _BASE_EVAL(
        self,
        _GEOMETRY_INSTALL % (float(rect["settleX"]), float(rect["settleY"])),
    )
    if not installed:
        raise RuntimeError("passive tooltip geometry observer could not be installed")
    self._webeeblocks_geometry_started = time.monotonic()
    self._webeeblocks_geometry_late_emitted = False
    self._webeeblocks_geometry_active = True


def eval_with_geometry(self: probe.Cdp, expr: str):
    result = _BASE_EVAL(self, expr)
    if expr != probe.VISIBLE_OVERLAY or not getattr(
        self, "_webeeblocks_geometry_active", False
    ):
        return result

    if base._tooltip_visible(result):
        _emit_geometry(self, "public-tooltip-visible", cleanup=True)
        return result

    elapsed = time.monotonic() - getattr(
        self, "_webeeblocks_geometry_started", time.monotonic()
    )
    # Match the existing passive late boundary. It has no pass authority and
    # leaves the observer active through the remainder of the unchanged 5 s oracle.
    if elapsed >= 4.25 and not getattr(
        self, "_webeeblocks_geometry_late_emitted", False
    ):
        self._webeeblocks_geometry_late_emitted = True
        _emit_geometry(self, "still-absent-after-4.25s", cleanup=False)
    return result


probe.Cdp.hover = hover_with_geometry
probe.Cdp.eval = eval_with_geometry

if __name__ == "__main__":
    probe.main()
