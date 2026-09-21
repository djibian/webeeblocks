#!/usr/bin/env python3
"""Add passive post-fire geometry evidence to the canonical #414 hover probe.

This diagnostic deliberately reuses the exact real pointer trajectory, tooltip
acceptance oracle and state-preserving observers from probe_post_hover_entry.
It only enriches the already-passive observer with geometry/viewport snapshots
before and after public tooltip DOM mutations and ordinary pointer lifecycle
events.  It does not intercept timers, mutate Blockly/workspace/tooltip state,
dispatch extra input, retry the hover, or change the 5 s oracle.
"""

from __future__ import annotations

import probe_post_hover_entry as base


base._POST_HOVER_INSTALL = r'''((x,y) => {
  const key='__webeeblocksCiTooltipPostHover';
  const old=window[key];
  if(old&&old.cleanup)old.cleanup();

  const target=document.elementFromPoint(x,y);
  const classOf=node=>String((node&&node.getAttribute&&node.getAttribute('class'))||'');
  const targetClass=classOf(target);
  if(!target||!targetClass.includes('blocklyPath'))throw new Error('post-hover target is not the exact public Blockly path');

  const ownerOf=node=>{
    const owner=node&&node.tooltip;
    return owner&&typeof owner==='object'
      ? {type:String(owner.type||''),id:String(owner.id||'')}
      : null;
  };
  const stackAt=(px,py)=>document.elementsFromPoint(px,py)
    .filter(node=>classOf(node).includes('blocklyPath'))
    .map(node=>({
      tag:node.tagName||'',className:classOf(node),isObserved:node===target,
      sharesObservedTooltip:!!(node&&target&&node.tooltip&&node.tooltip===target.tooltip),
      owner:ownerOf(node)
    }));

  const tooltip=window.Blockly&&Blockly.Tooltip;
  const hasVisible=!!tooltip&&typeof tooltip.isVisible==='function';
  const hasGetDiv=!!tooltip&&typeof tooltip.getDiv==='function';
  const div=hasGetDiv ? tooltip.getDiv() : document.querySelector('.blocklyTooltipDiv');
  if(!div)throw new Error('public Blockly tooltip div unavailable for post-hover observation');

  const now=()=>performance.now();
  const rectOf=node=>{
    if(!node||typeof node.getBoundingClientRect!=='function')return null;
    const r=node.getBoundingClientRect();
    return {x:r.x,y:r.y,left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height};
  };
  const matrixOf=node=>{
    if(!node||typeof node.getScreenCTM!=='function')return null;
    const m=node.getScreenCTM();
    return m ? {a:m.a,b:m.b,c:m.c,d:m.d,e:m.e,f:m.f} : null;
  };
  const geometry=()=>{
    const repeat=window.workspace&&workspace.getBlocksByType('controls_repeat_ext',false)[0];
    const takeoff=window.workspace&&workspace.getBlocksByType('webeeblocks_v2_takeoff',false)[0];
    const repeatPath=repeat&&repeat.pathObject&&repeat.pathObject.svgPath;
    const takeoffPath=takeoff&&takeoff.pathObject&&takeoff.pathObject.svgPath;
    const parentSvg=window.workspace&&typeof workspace.getParentSvg==='function' ? workspace.getParentSvg() : null;
    const canvas=window.workspace&&typeof workspace.getCanvas==='function' ? workspace.getCanvas() : null;
    const hit=document.elementFromPoint(x,y);
    const de=document.documentElement;
    const body=document.body;
    const vv=window.visualViewport;
    const divStyle=getComputedStyle(div);
    const deStyle=getComputedStyle(de);
    const bodyStyle=body ? getComputedStyle(body) : null;
    return {
      at:now(),
      pointer:{x:x,y:y,hitTag:(hit&&hit.tagName)||'',hitClass:classOf(hit),hitOwner:ownerOf(hit),stack:stackAt(x,y)},
      viewport:{
        scrollX:window.scrollX,scrollY:window.scrollY,innerWidth:window.innerWidth,innerHeight:window.innerHeight,
        devicePixelRatio:window.devicePixelRatio,
        visual:vv ? {offsetLeft:vv.offsetLeft,offsetTop:vv.offsetTop,pageLeft:vv.pageLeft,pageTop:vv.pageTop,width:vv.width,height:vv.height,scale:vv.scale} : null
      },
      document:{
        clientWidth:de.clientWidth,clientHeight:de.clientHeight,scrollWidth:de.scrollWidth,scrollHeight:de.scrollHeight,
        overflowX:deStyle.overflowX,overflowY:deStyle.overflowY,
        bodyClientWidth:body&&body.clientWidth,bodyClientHeight:body&&body.clientHeight,
        bodyScrollWidth:body&&body.scrollWidth,bodyScrollHeight:body&&body.scrollHeight,
        bodyOverflowX:bodyStyle&&bodyStyle.overflowX,bodyOverflowY:bodyStyle&&bodyStyle.overflowY
      },
      repeat:{rect:rectOf(repeatPath),ctm:matrixOf(repeatPath),rootRect:rectOf(repeat&&repeat.getSvgRoot&&repeat.getSvgRoot())},
      takeoff:{rect:rectOf(takeoffPath),ctm:matrixOf(takeoffPath),rootRect:rectOf(takeoff&&takeoff.getSvgRoot&&takeoff.getSvgRoot())},
      workspace:{svgRect:rectOf(parentSvg),svgCtm:matrixOf(parentSvg),canvasRect:rectOf(canvas),canvasCtm:matrixOf(canvas)},
      tooltip:{
        visible:hasVisible ? !!tooltip.isVisible() : null,display:divStyle.display,
        position:divStyle.position,left:divStyle.left,top:divStyle.top,
        width:div.offsetWidth,height:div.offsetHeight,rect:rectOf(div),parentRect:rectOf(div.parentElement),
        text:String(div.innerText||div.textContent||'').trim().slice(0,240)
      }
    };
  };
  const pack=e=>({
    type:e.type,at:now(),x:e.clientX,y:e.clientY,pageX:e.pageX,pageY:e.pageY,buttons:e.buttons,
    targetTag:(e.target&&e.target.tagName)||'',targetClass:classOf(e.target),
    relatedClass:classOf(e.relatedTarget),
    targetOwner:ownerOf(e.target),relatedOwner:ownerOf(e.relatedTarget),
    targetIsObserved:e.target===target,relatedIsObserved:e.relatedTarget===target,
    targetSharesTooltip:!!(e.target&&target&&e.target.tooltip&&e.target.tooltip===target.tooltip),
    relatedSharesTooltip:!!(e.relatedTarget&&target&&e.relatedTarget.tooltip&&e.relatedTarget.tooltip===target.tooltip),
    geometry:geometry()
  });
  const state={
    installedAt:now(),target:target,events:[],lifecycle:[],mutations:[],cleanup:null,
    initial:{focused:document.hasFocus(),visibility:document.visibilityState,geometry:geometry()}
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
  const lifecycle=(kind,value)=>cap(state.lifecycle,{kind:kind,at:now(),value:value,geometry:geometry()},32);
  const onFocus=()=>lifecycle('focus',null);
  const onBlur=()=>lifecycle('blur',null);
  const onVisibility=()=>lifecycle('visibility',document.visibilityState);
  const onResize=()=>lifecycle('resize',null);
  const onScroll=()=>lifecycle('scroll',{scrollX:window.scrollX,scrollY:window.scrollY});
  const onVisualResize=()=>lifecycle('visual-resize',null);
  const onVisualScroll=()=>lifecycle('visual-scroll',null);
  window.addEventListener('focus',onFocus,true);
  window.addEventListener('blur',onBlur,true);
  document.addEventListener('visibilitychange',onVisibility,true);
  window.addEventListener('resize',onResize,true);
  window.addEventListener('scroll',onScroll,true);
  if(window.visualViewport){
    window.visualViewport.addEventListener('resize',onVisualResize,true);
    window.visualViewport.addEventListener('scroll',onVisualScroll,true);
  }

  const observer=new MutationObserver(records=>{
    for(const record of records){
      cap(state.mutations,{
        at:now(),type:record.type,attributeName:record.attributeName||'',
        display:getComputedStyle(div).display,
        text:String(div.innerText||div.textContent||'').trim().slice(0,240),
        geometry:geometry()
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
    window.removeEventListener('resize',onResize,true);
    window.removeEventListener('scroll',onScroll,true);
    if(window.visualViewport){
      window.visualViewport.removeEventListener('resize',onVisualResize,true);
      window.visualViewport.removeEventListener('scroll',onVisualScroll,true);
    }
  };
  window[key]=state;
  return true;
})(%s,%s)'''

base._POST_HOVER_SNAPSHOT = r'''((x,y) => {
  const s=window.__webeeblocksCiTooltipPostHover;
  if(!s)return null;
  const classOf=node=>String((node&&node.getAttribute&&node.getAttribute('class'))||'');
  const ownerOf=node=>{
    const owner=node&&node.tooltip;
    return owner&&typeof owner==='object'
      ? {type:String(owner.type||''),id:String(owner.id||'')}
      : null;
  };
  const stackAt=(px,py)=>document.elementsFromPoint(px,py)
    .filter(node=>classOf(node).includes('blocklyPath'))
    .map(node=>({tag:node.tagName||'',className:classOf(node),isObserved:node===s.target,owner:ownerOf(node)}));
  const rectOf=node=>{
    if(!node||typeof node.getBoundingClientRect!=='function')return null;
    const r=node.getBoundingClientRect();
    return {x:r.x,y:r.y,left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height};
  };
  const matrixOf=node=>{
    if(!node||typeof node.getScreenCTM!=='function')return null;
    const m=node.getScreenCTM();
    return m ? {a:m.a,b:m.b,c:m.c,d:m.d,e:m.e,f:m.f} : null;
  };
  const tooltip=window.Blockly&&Blockly.Tooltip;
  const hasVisible=!!tooltip&&typeof tooltip.isVisible==='function';
  const hasGetDiv=!!tooltip&&typeof tooltip.getDiv==='function';
  const div=hasGetDiv ? tooltip.getDiv() : document.querySelector('.blocklyTooltipDiv');
  const geometry=()=>{
    const repeat=window.workspace&&workspace.getBlocksByType('controls_repeat_ext',false)[0];
    const takeoff=window.workspace&&workspace.getBlocksByType('webeeblocks_v2_takeoff',false)[0];
    const repeatPath=repeat&&repeat.pathObject&&repeat.pathObject.svgPath;
    const takeoffPath=takeoff&&takeoff.pathObject&&takeoff.pathObject.svgPath;
    const parentSvg=window.workspace&&workspace.getParentSvg ? workspace.getParentSvg() : null;
    const canvas=window.workspace&&workspace.getCanvas ? workspace.getCanvas() : null;
    const hit=document.elementFromPoint(x,y);
    const de=document.documentElement;
    const body=document.body;
    const vv=window.visualViewport;
    const ds=div ? getComputedStyle(div) : null;
    return {
      at:performance.now(),pointer:{x:x,y:y,hitTag:(hit&&hit.tagName)||'',hitClass:classOf(hit),hitOwner:ownerOf(hit),stack:stackAt(x,y)},
      viewport:{scrollX:window.scrollX,scrollY:window.scrollY,innerWidth:window.innerWidth,innerHeight:window.innerHeight,visual:vv?{offsetLeft:vv.offsetLeft,offsetTop:vv.offsetTop,pageLeft:vv.pageLeft,pageTop:vv.pageTop,width:vv.width,height:vv.height,scale:vv.scale}:null},
      document:{clientWidth:de.clientWidth,clientHeight:de.clientHeight,scrollWidth:de.scrollWidth,scrollHeight:de.scrollHeight,bodyClientWidth:body&&body.clientWidth,bodyClientHeight:body&&body.clientHeight,bodyScrollWidth:body&&body.scrollWidth,bodyScrollHeight:body&&body.scrollHeight},
      repeat:{rect:rectOf(repeatPath),ctm:matrixOf(repeatPath),rootRect:rectOf(repeat&&repeat.getSvgRoot&&repeat.getSvgRoot())},
      takeoff:{rect:rectOf(takeoffPath),ctm:matrixOf(takeoffPath),rootRect:rectOf(takeoff&&takeoff.getSvgRoot&&takeoff.getSvgRoot())},
      workspace:{svgRect:rectOf(parentSvg),svgCtm:matrixOf(parentSvg),canvasRect:rectOf(canvas),canvasCtm:matrixOf(canvas)},
      tooltip:div?{visible:hasVisible?!!tooltip.isVisible():null,display:ds.display,position:ds.position,left:ds.left,top:ds.top,width:div.offsetWidth,height:div.offsetHeight,rect:rectOf(div),parentRect:rectOf(div.parentElement),text:String(div.innerText||div.textContent||'').trim().slice(0,240)}:null
    };
  };
  return {installedAt:s.installedAt,initial:s.initial,current:{focused:document.hasFocus(),visibility:document.visibilityState,geometry:geometry()},events:s.events.slice(),lifecycle:s.lifecycle.slice(),mutations:s.mutations.slice()};
})(%s,%s)'''


if __name__ == "__main__":
    base.probe.main()
