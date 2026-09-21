#!/usr/bin/env python3
"""Add passive geometry evidence to the canonical #414 real-hover probe.

This wrapper does not change the pointer trajectory, Blockly tooltip lifecycle,
workspace, 5 s public tooltip oracle, or ordinary leave-to-close assertion. It
only records geometry/hit-test state when the already-observed same-coordinate
pointer ownership transitions occur, so a natural recurrence can distinguish a
real SVG/layout/transform shift from a paint/hit-test ownership change.
"""

from __future__ import annotations

import json

import probe
import probe_post_hover_entry as base


_BASE_HOVER = base.hover_with_post_hover_diagnostics
_BASE_EMIT = base._emit

_GEOMETRY_INSTALL = r'''((x,y) => {
  const key='__webeeblocksCiTooltipGeometry';
  const old=window[key];
  if(old&&old.cleanup)old.cleanup();

  const post=window.__webeeblocksCiTooltipPostHover;
  const target=post&&post.target;
  if(!target)throw new Error('post-hover exact target unavailable for geometry observation');

  const repeat=workspace.getBlocksByType('controls_repeat_ext',false)[0];
  const takeoff=workspace.getBlocksByType('webeeblocks_v2_takeoff',false)[0];
  if(!repeat||!takeoff)throw new Error('geometry observer requires repeat and takeoff blocks');

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
    return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom};
  };
  const boxOf=node=>{
    if(!node||typeof node.getBBox!=='function')return null;
    try{const b=node.getBBox();return{x:b.x,y:b.y,width:b.width,height:b.height};}catch(_){return null;}
  };
  const ctmOf=node=>{
    if(!node||typeof node.getScreenCTM!=='function')return null;
    const m=node.getScreenCTM();
    return m?{a:m.a,b:m.b,c:m.c,d:m.d,e:m.e,f:m.f}:null;
  };
  const styleOf=node=>{
    if(!node)return null;
    const s=getComputedStyle(node);
    return {
      display:s.display,visibility:s.visibility,pointerEvents:s.pointerEvents,
      transform:s.transform,fill:s.fill,stroke:s.stroke,strokeWidth:s.strokeWidth
    };
  };
  const blockOf=block=>{
    const root=block&&block.getSvgRoot&&block.getSvgRoot();
    const path=block&&block.pathObject&&block.pathObject.svgPath;
    return {
      type:block&&String(block.type||''),id:block&&String(block.id||''),
      rootRect:rectOf(root),rootCtm:ctmOf(root),rootStyle:styleOf(root),
      pathRect:rectOf(path),pathBox:boxOf(path),pathCtm:ctmOf(path),pathStyle:styleOf(path)
    };
  };
  const nodeSummary=node=>({
    tag:(node&&node.tagName)||'',className:classOf(node),owner:ownerOf(node),
    isObserved:node===target,rect:rectOf(node),ctm:ctmOf(node),style:styleOf(node)
  });
  const stackAt=(px,py)=>document.elementsFromPoint(px,py).slice(0,12).map(nodeSummary);
  const metricsOf=()=>{
    try{
      const m=workspace.getMetrics();
      const names=['viewLeft','viewTop','viewWidth','viewHeight','contentLeft','contentTop','contentWidth','contentHeight','absoluteLeft','absoluteTop'];
      const out={};
      for(const name of names)if(Number.isFinite(m[name]))out[name]=m[name];
      return out;
    }catch(_){return null;}
  };
  const tooltip=window.Blockly&&Blockly.Tooltip;
  const div=tooltip&&typeof tooltip.getDiv==='function'
    ? tooltip.getDiv() : document.querySelector('.blocklyTooltipDiv');
  const canvas=workspace.getCanvas&&workspace.getCanvas();
  const blocklyDiv=document.getElementById('blocklyDiv');

  const sample=(kind,extra)=>{
    const hit=document.elementFromPoint(x,y);
    return Object.assign({
      kind:kind,at:performance.now(),x:x,y:y,
      focused:document.hasFocus(),visibility:document.visibilityState,
      viewport:{width:innerWidth,height:innerHeight,scrollX:scrollX,scrollY:scrollY,devicePixelRatio:devicePixelRatio},
      workspaceScale:workspace.scale,workspaceMetrics:metricsOf(),
      blocklyDivRect:rectOf(blocklyDiv),canvasRect:rectOf(canvas),canvasCtm:ctmOf(canvas),canvasStyle:styleOf(canvas),
      repeat:blockOf(repeat),takeoff:blockOf(takeoff),
      hit:nodeSummary(hit),stack:stackAt(x,y),
      tooltip:{
        visible:tooltip&&typeof tooltip.isVisible==='function'?!!tooltip.isVisible():null,
        rect:rectOf(div),display:div?getComputedStyle(div).display:null,
        text:div?String(div.innerText||div.textContent||'').trim().slice(0,240):null
      }
    },extra||{});
  };

  const state={samples:[],cleanup:null};
  const cap=value=>{state.samples.push(value);if(state.samples.length>96)state.samples.shift();};
  cap(sample('initial'));

  const types=['pointerout','pointerover','mouseout','mouseover'];
  const handlers={};
  for(const type of types){
    handlers[type]=event=>{
      if(event.clientX!==x||event.clientY!==y)return;
      cap(sample('event',{
        event:{
          type:event.type,target:nodeSummary(event.target),related:nodeSummary(event.relatedTarget)
        }
      }));
    };
    document.addEventListener(type,handlers[type],true);
  }

  state.cleanup=()=>{
    for(const type of types)document.removeEventListener(type,handlers[type],true);
  };
  window[key]=state;
  return true;
})(%s,%s)'''

_GEOMETRY_SNAPSHOT = r'''((x,y) => {
  const state=window.__webeeblocksCiTooltipGeometry;
  if(!state)return null;
  const post=window.__webeeblocksCiTooltipPostHover;
  const target=post&&post.target;
  const classOf=node=>String((node&&node.getAttribute&&node.getAttribute('class'))||'');
  const ownerOf=node=>{
    const owner=node&&node.tooltip;
    return owner&&typeof owner==='object'?{type:String(owner.type||''),id:String(owner.id||'')}:null;
  };
  const hit=document.elementFromPoint(x,y);
  return {
    samples:state.samples.slice(),
    final:{
      at:performance.now(),hitTag:(hit&&hit.tagName)||'',hitClass:classOf(hit),
      hitOwner:ownerOf(hit),hitIsObserved:hit===target,
      blocklyPathStack:document.elementsFromPoint(x,y)
        .filter(node=>classOf(node).includes('blocklyPath'))
        .map(node=>({tag:node.tagName||'',className:classOf(node),owner:ownerOf(node),isObserved:node===target}))
    }
  };
})(%s,%s)'''

_GEOMETRY_CLEANUP = r'''(() => {
  const key='__webeeblocksCiTooltipGeometry';
  const state=window[key];
  if(!state)return false;
  if(state.cleanup)state.cleanup();
  delete window[key];
  return true;
})()'''


def _geometry_snapshot(c: probe.Cdp):
    rect = getattr(c, "_webeeblocks_geometry_rect", None)
    if not rect:
        return None
    return base._ORIGINAL_EVAL(
        c,
        _GEOMETRY_SNAPSHOT % (float(rect["settleX"]), float(rect["settleY"])),
    )


def hover_with_geometry(self: probe.Cdp, rect: dict[str, object]) -> None:
    _BASE_HOVER(self, rect)
    installed = base._ORIGINAL_EVAL(
        self,
        _GEOMETRY_INSTALL % (float(rect["settleX"]), float(rect["settleY"])),
    )
    if not installed:
        raise RuntimeError("passive tooltip geometry observer could not be installed")
    self._webeeblocks_geometry_rect = dict(rect)


def emit_with_geometry(c: probe.Cdp, reason: str, cleanup: bool) -> None:
    print(
        "WEBEEBLOCKS_TOOLTIP_GEOMETRY_DIAGNOSTIC "
        + json.dumps({"reason": reason, "snapshot": _geometry_snapshot(c)}, sort_keys=True)
    )
    if cleanup:
        base._ORIGINAL_EVAL(c, _GEOMETRY_CLEANUP)
    _BASE_EMIT(c, reason, cleanup)


base._emit = emit_with_geometry
probe.Cdp.hover = hover_with_geometry

if __name__ == "__main__":
    probe.main()
