#!/usr/bin/env python3
"""Run the canonical student-UI tooltip probe with geometry-stable hover points.

#414 recurrence evidence showed that a pre-hover exclusive hit stack is not
sufficient: after the public tooltip became visible, a stationary pointer could
retarget from the exact repeat path to an underlying takeoff block path at the
same screen coordinates and immediately hide the tooltip. This wrapper preserves
the existing three ordinary CDP pointer moves, exact repeat-path delivery proof,
5 s public tooltip oracle and ordinary exit assertion, but rejects candidate
points that are geometrically occupied by any other rendered workspace block
path even when that competing path is currently occluded in the hit stack.

No tooltip state, timer, workspace, visibility or product/runtime behavior is
mutated, and there is no outcome-conditioned retry.
"""

from __future__ import annotations

import probe
import probe_post_hover_entry  # noqa: F401 - installs the existing passive diagnostics


_GEOMETRY_STABLE_REPEAT_HOVER_RECT = r'''(() => {
 const repeat=workspace.getBlocksByType('controls_repeat_ext',false)[0];
 const resetBlock=workspace.getBlocksByType('webeeblocks_v2_takeoff',false)[0];
 if(!repeat)throw new Error('rendered repeat block missing for hover');
 if(!resetBlock)throw new Error('rendered takeoff block missing for tooltip-owner reset');
 const repeatRoot=repeat.getSvgRoot();
 const resetRoot=resetBlock.getSvgRoot();
 if(!repeatRoot||!resetRoot)throw new Error('rendered tooltip-owner reset roots missing');
 const repeatPath=repeat.pathObject&&repeat.pathObject.svgPath;
 const resetPath=resetBlock.pathObject&&resetBlock.pathObject.svgPath;
 if(!repeatPath||!resetPath)throw new Error('rendered tooltip-bound paths missing');
 if(!repeatRoot.contains(repeatPath)||!resetRoot.contains(resetPath))throw new Error('tooltip-bound path outside rendered block root');
 if(repeatPath.tooltip!==repeat||resetPath.tooltip!==resetBlock)throw new Error('rendered path is not bound to its block tooltip object');
 if(resetPath.tooltip===repeatPath.tooltip)throw new Error('tooltip-owner reset must use a different tooltip owner');

 const classOf=node=>String((node&&node.getAttribute&&node.getAttribute('class'))||'');
 const ownerSummary=node=>{
   const owner=node&&node.tooltip;
   return owner&&typeof owner==='object'
     ? {type:String(owner.type||''),id:String(owner.id||'')}
     : null;
 };
 const blocklyPathsAt=(x,y)=>document.elementsFromPoint(x,y).filter(node=>classOf(node).includes('blocklyPath'));

 // Keep the geometric oracle bounded to paths owned by the rendered workspace
 // fixture. A currently occluded path can become the browser target after a DOM
 // presentation change, so current elementsFromPoint() ordering alone is not a
 // sufficient stability proof.
 const records=workspace.getAllBlocks(false).map(block=>{
   const path=block.pathObject&&block.pathObject.svgPath;
   if(!path)return null;
   if(typeof path.isPointInFill!=='function')throw new Error('SVG path fill hit-test API unavailable');
   const matrix=path.getScreenCTM();
   if(!matrix||typeof matrix.inverse!=='function')throw new Error('SVG path screen transform unavailable');
   let inverse;
   try{inverse=matrix.inverse();}catch(_){throw new Error('SVG path screen transform is not invertible');}
   const rect=path.getBoundingClientRect();
   return {path:path,block:block,inverse:inverse,rect:rect};
 }).filter(Boolean);
 const recordFor=path=>records.find(record=>record.path===path);
 if(!recordFor(repeatPath)||!recordFor(resetPath))throw new Error('tooltip paths missing from rendered workspace geometry set');

 const occupies=(record,x,y)=>{
   const r=record.rect;
   if(x<r.left-0.5||x>r.right+0.5||y<r.top-0.5||y>r.bottom+0.5)return false;
   const local=new DOMPoint(x,y).matrixTransform(record.inverse);
   if(record.path.isPointInFill(local))return true;
   return typeof record.path.isPointInStroke==='function'&&record.path.isPointInStroke(local);
 };
 const geometryAt=(x,y)=>records.filter(record=>occupies(record,x,y)).map(record=>({
   type:String(record.block.type||''),id:String(record.block.id||''),owner:ownerSummary(record.path)
 }));
 const sameExclusive=(path,x,y)=>{
   const paths=blocklyPathsAt(x,y);
   if(paths.length!==1||paths[0]!==path)return false;
   const targetRecord=recordFor(path);
   if(!targetRecord||!occupies(targetRecord,x,y))return false;
   return !records.some(record=>record.path!==path&&occupies(record,x,y));
 };
 const hasClearance=(path,x,y,radius)=>{
   if(!sameExclusive(path,x,y))return false;
   for(let r=1;r<=radius;r++){
     const points=[
       [x-r,y],[x+r,y],[x,y-r],[x,y+r],
       [x-r,y-r],[x-r,y+r],[x+r,y-r],[x+r,y+r]
     ];
     if(!points.every(([px,py])=>sameExclusive(path,px,py)))return false;
   }
   return true;
 };
 const stackSummary=(x,y)=>blocklyPathsAt(x,y).map(node=>({
   tag:node.tagName||'',className:classOf(node),owner:ownerSummary(node)
 }));
 const toScreen=(matrix,point)=>{
   const p=new DOMPoint(point.x,point.y).matrixTransform(matrix);
   return {x:p.x,y:p.y};
 };
 const stablePoint=(path,minClearance)=>{
   if(typeof path.getTotalLength!=='function'||typeof path.getPointAtLength!=='function'){
     throw new Error('exact tooltip-bound SVG path geometry API unavailable');
   }
   const total=path.getTotalLength();
   const matrix=path.getScreenCTM();
   if(!(total>0)||!Number.isFinite(total)||!matrix){
     throw new Error('exact tooltip-bound SVG path geometry unavailable');
   }
   const samples=12;
   const offsets=[5,9,13];
   const delta=Math.max(0.5,Math.min(2,total/(samples*4)));
   for(let i=0;i<samples;i++){
     const at=total*(i+0.5)/samples;
     const center=toScreen(matrix,path.getPointAtLength(at));
     const before=toScreen(matrix,path.getPointAtLength(Math.max(0,at-delta)));
     const after=toScreen(matrix,path.getPointAtLength(Math.min(total,at+delta)));
     const tx=after.x-before.x;
     const ty=after.y-before.y;
     const norm=Math.hypot(tx,ty);
     if(!(norm>0))continue;
     const nx=-ty/norm;
     const ny=tx/norm;
     for(const offset of offsets){
       for(const sign of [1,-1]){
         const x=Math.round(center.x+sign*nx*offset);
         const y=Math.round(center.y+sign*ny*offset);
         if(hasClearance(path,x,y,minClearance)){
           return {x:x,y:y,clearance:minClearance};
         }
       }
     }
   }
   return null;
 };

 const entry=stablePoint(repeatPath,3);
 if(!entry)throw new Error('no geometrically exclusive stable interior hover point on exact repeat path');
 const neighbours=[
   [entry.x+1,entry.y],[entry.x-1,entry.y],
   [entry.x,entry.y+1],[entry.x,entry.y-1]
 ];
 const settle=neighbours.find(([sx,sy])=>hasClearance(repeatPath,sx,sy,2));
 if(!settle)throw new Error('no geometrically exclusive stable settle point on exact repeat path');

 const reset=stablePoint(resetPath,2);
 if(!reset)throw new Error('no geometrically exclusive stable tooltip-owner reset point');
 if(repeatRoot.contains(resetPath))throw new Error('tooltip-owner reset path unexpectedly belongs to repeat root');
 if(document.elementFromPoint(reset.x,reset.y)!==resetPath)throw new Error('tooltip-owner reset point lost exact DOM identity');

 const entryGeometry=geometryAt(entry.x,entry.y);
 const settleGeometry=geometryAt(settle[0],settle[1]);
 const resetGeometry=geometryAt(reset.x,reset.y);
 if(entryGeometry.length!==1||entryGeometry[0].id!==String(repeat.id))throw new Error('repeat entry has competing rendered block geometry');
 if(settleGeometry.length!==1||settleGeometry[0].id!==String(repeat.id))throw new Error('repeat settle has competing rendered block geometry');
 if(resetGeometry.length!==1||resetGeometry[0].id!==String(resetBlock.id))throw new Error('reset point has competing rendered block geometry');

 return {
   x:entry.x-1,y:entry.y-1,width:2,height:2,
   entryX:entry.x,entryY:entry.y,settleX:settle[0],settleY:settle[1],
   outsideX:reset.x,outsideY:reset.y,
   hitTag:repeatPath.tagName,
   hitClass:classOf(repeatPath),
   stableClearance:entry.clearance,
   entryStack:stackSummary(entry.x,entry.y),
   settleStack:stackSummary(settle[0],settle[1]),
   resetTag:resetPath.tagName,
   resetClass:classOf(resetPath),
   resetClearance:reset.clearance,
   resetStack:stackSummary(reset.x,reset.y),
   entryGeometry:entryGeometry,
   settleGeometry:settleGeometry,
   resetGeometry:resetGeometry
 };
})()'''


probe.REPEAT_HOVER_RECT = _GEOMETRY_STABLE_REPEAT_HOVER_RECT


if __name__ == "__main__":
    probe.main()
