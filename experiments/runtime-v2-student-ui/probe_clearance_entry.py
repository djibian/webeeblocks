#!/usr/bin/env python3
"""Run the canonical tooltip probe on the most stable post-reset repeat target.

Exact Ready run 35653363738 first proved that repeat coordinates selected before
the distinct-owner reset can be stale after that real reset move.  The later
exact Ready head d55633ec94738156f27895b7fe51fa262f0bd2a1 reselected from the
post-reset DOM, but run 35654272131 still reproduced a same-coordinate
repeat-to-takeoff retarget immediately after the public tooltip rendered.

Ready run 35657149471 then exposed a narrower selector/delivery mismatch on head
e16d5bb1e24efc421f61f6d970abadbc40c56c78: the ranked point at (287,208) had
only the repeat blocklyPath in the filtered elementsFromPoint stack, but the
immediately following exact delivery prerequisite found that elementFromPoint
itself did not resolve to repeat.pathObject.svgPath.  A candidate used for real
pointer delivery must therefore satisfy both constraints at selection time.

Keep that necessary post-reset reselection and the integrated #493 candidate set,
minimum 3 px entry / 2 px settle contract, and exactly three real pointer moves.
Instead of accepting the first qualifying repeat point (which deterministically
selects the connected-block seam at about (200,201)), rank the same finite
candidate set by measured exclusive browser hit-test clearance and choose the
largest available margin.  The bounded 16 px scoring horizon is the existing
largest normal offset (13 px) plus the existing 3 px entry requirement.  It ranks
candidates but does not introduce a stronger acceptance threshold.

The exclusivity predicate also requires document.elementFromPoint() to be the
exact repeat SVG path, matching the already-existing delivery contract rather
than accepting a filtered stack whose top hit is some different element.  This
criterion applies equally to entry, settle and the measured clearance points.

This targets the durable failure boundary without inventing a larger mandatory
clearance.  No extra pointer move is emitted, no tooltip/workspace state is
assigned, no timer or Blockly lifecycle function is wrapped, and the unchanged
5 s public visible/non-empty/localized oracle plus ordinary-leave assertion
remain authoritative.  The passive geometry/occupancy wrapper may remain layered
above this file to preserve evidence if a natural recurrence still occurs.
"""

from __future__ import annotations

import json
import time

import probe
import probe_entry
import probe_post_hover_entry as integrated


_OLD_SAME_EXCLUSIVE = r''' const sameExclusive=(path,x,y)=>{
   const paths=blocklyPathsAt(x,y);
   return paths.length===1&&paths[0]===path;
 };'''

_NEW_SAME_EXCLUSIVE = r''' const sameExclusive=(path,x,y)=>{
   if(document.elementFromPoint(x,y)!==path)return false;
   const paths=blocklyPathsAt(x,y);
   return paths.length===1&&paths[0]===path;
 };'''

_OLD_REPEAT_SELECTION = r''' const entry=stablePoint(repeatPath,3);
 if(!entry)throw new Error('no exclusive stable interior hover point on exact Blockly tooltip-bound repeat path');
 const neighbours=[
   [entry.x+1,entry.y],[entry.x-1,entry.y],
   [entry.x,entry.y+1],[entry.x,entry.y-1]
 ];
 const settle=neighbours.find(([sx,sy])=>hasClearance(repeatPath,sx,sy,2));
 if(!settle)throw new Error('no exclusive stable settle point on exact Blockly tooltip-bound repeat path');

 const reset=stablePoint(resetPath,2);'''

_NEW_REPEAT_SELECTION = r''' // Preserve #493's finite path-derived candidate set, but do not let its
 // iteration order choose an edge-adjacent point merely because that point is
 // the first one satisfying the existing minimum clearance.  Score candidates
 // by the largest exclusive hit-test radius observed inside the already-bounded
 // 16 px measurement horizon (13 px max existing offset + 3 px existing entry
 // minimum).  The score ranks candidates; it is not a stronger acceptance gate.
 const measuredClearance=(path,x,y,maxRadius)=>{
   if(!sameExclusive(path,x,y))return 0;
   let clearance=0;
   for(let r=1;r<=maxRadius;r++){
     const points=[
       [x-r,y],[x+r,y],[x,y-r],[x,y+r],
       [x-r,y-r],[x-r,y+r],[x+r,y-r],[x+r,y+r]
     ];
     if(!points.every(([px,py])=>sameExclusive(path,px,py)))break;
     clearance=r;
   }
   return clearance;
 };
 const rankedRepeatPoint=(minClearance)=>{
   const path=repeatPath;
   const total=path.getTotalLength();
   const matrix=path.getScreenCTM();
   if(!(total>0)||!Number.isFinite(total)||!matrix){
     throw new Error('exact tooltip-bound repeat SVG path geometry unavailable');
   }
   const samples=12;
   const offsets=[5,9,13];
   const scoreRadius=16;
   const delta=Math.max(0.5,Math.min(2,total/(samples*4)));
   let best=null;
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
         const clearance=measuredClearance(path,x,y,scoreRadius);
         if(clearance<minClearance)continue;
         if(!best||clearance>best.clearance){
           best={x:x,y:y,clearance:clearance};
         }
       }
     }
   }
   return best;
 };

 const entry=rankedRepeatPoint(3);
 if(!entry)throw new Error('no exclusive stable interior hover point on exact Blockly tooltip-bound repeat path');
 const neighbours=[
   [entry.x+1,entry.y],[entry.x-1,entry.y],
   [entry.x,entry.y+1],[entry.x,entry.y-1]
 ];
 let settle=null;
 for(const candidate of neighbours){
   const clearance=measuredClearance(repeatPath,candidate[0],candidate[1],16);
   if(clearance<2)continue;
   if(!settle||clearance>settle.clearance){
     settle={x:candidate[0],y:candidate[1],clearance:clearance};
   }
 }
 if(!settle)throw new Error('no exclusive stable settle point on exact Blockly tooltip-bound repeat path');

 const reset=stablePoint(resetPath,2);'''

_OLD_RETURN = r'''   entryX:entry.x,entryY:entry.y,settleX:settle[0],settleY:settle[1],
   outsideX:reset.x,outsideY:reset.y,
   hitTag:repeatPath.tagName,
   hitClass:classOf(repeatPath),
   stableClearance:entry.clearance,'''

_NEW_RETURN = r'''   entryX:entry.x,entryY:entry.y,settleX:settle.x,settleY:settle.y,
   outsideX:reset.x,outsideY:reset.y,
   hitTag:repeatPath.tagName,
   hitClass:classOf(repeatPath),
   stableClearance:entry.clearance,
   settleClearance:settle.clearance,'''

_OLD_SETTLE_STACK = "   settleStack:stackSummary(settle[0],settle[1]),"
_NEW_SETTLE_STACK = "   settleStack:stackSummary(settle.x,settle.y),"


def _ranked_repeat_hover_rect() -> str:
    expression = integrated._RESET_REPEAT_HOVER_RECT
    replacements = (
        (_OLD_SAME_EXCLUSIVE, _NEW_SAME_EXCLUSIVE),
        (_OLD_REPEAT_SELECTION, _NEW_REPEAT_SELECTION),
        (_OLD_RETURN, _NEW_RETURN),
        (_OLD_SETTLE_STACK, _NEW_SETTLE_STACK),
    )
    for old, new in replacements:
        count = expression.count(old)
        if count != 1:
            raise RuntimeError(
                "integrated tooltip selector contract changed unexpectedly: "
                + json.dumps({"needle": old[:120], "count": count}, sort_keys=True)
            )
        expression = expression.replace(old, new, 1)
    return expression


probe.REPEAT_HOVER_RECT = _ranked_repeat_hover_rect()


def _copy_repeat_target(target: dict[str, object], source: dict[str, object]) -> None:
    for key in (
        "x",
        "y",
        "width",
        "height",
        "entryX",
        "entryY",
        "settleX",
        "settleY",
        "hitTag",
        "hitClass",
        "stableClearance",
        "settleClearance",
        "entryStack",
        "settleStack",
    ):
        target[key] = source[key]


def _copy_reset_target(target: dict[str, object], source: dict[str, object]) -> None:
    for key in (
        "outsideX",
        "outsideY",
        "resetTag",
        "resetClass",
        "resetClearance",
        "resetStack",
    ):
        target[key] = source[key]


def _canonical_hover_with_post_reset_reselection(
    c: probe.Cdp, rect: dict[str, object]
) -> None:
    # ``hover_with_passive_diagnostics`` has already performed the existing
    # focus check.  Re-evaluate geometry before the first real pointer move so
    # the distinct-owner reset itself is aimed at the current exact path.
    before_reset = c.eval(probe.REPEAT_HOVER_RECT)
    _copy_reset_target(rect, before_reset)

    c.call(
        "Input.dispatchMouseEvent",
        {"type": "mouseMoved", "x": rect["outsideX"], "y": rect["outsideY"]},
    )
    time.sleep(0.1)

    # Bind repeat entry/settle to the DOM state after the real owner-reset move.
    # Selection emits no pointer input and happens exactly once before the two
    # remaining canonical real moves, so this cannot become outcome retry.
    after_reset = c.eval(probe.REPEAT_HOVER_RECT)
    _copy_repeat_target(rect, after_reset)

    print(
        "WEBEEBLOCKS_TOOLTIP_POST_RESET_TARGET "
        + json.dumps(
            {
                "entry": [rect.get("entryX"), rect.get("entryY")],
                "settle": [rect.get("settleX"), rect.get("settleY")],
                "reset": [rect.get("outsideX"), rect.get("outsideY")],
                "stableClearance": rect.get("stableClearance"),
                "settleClearance": rect.get("settleClearance"),
                "resetClearance": rect.get("resetClearance"),
                "entryStack": rect.get("entryStack"),
                "settleStack": rect.get("settleStack"),
                "resetStack": rect.get("resetStack"),
            },
            sort_keys=True,
        )
    )

    probe_entry._install_delivery_probe(c, rect)
    c.call(
        "Input.dispatchMouseEvent",
        {"type": "mouseMoved", "x": rect["entryX"], "y": rect["entryY"]},
    )
    time.sleep(0.12)
    c.call(
        "Input.dispatchMouseEvent",
        {"type": "mouseMoved", "x": rect["settleX"], "y": rect["settleY"]},
    )
    time.sleep(0.04)


probe_entry._canonical_hover_after_reset = _canonical_hover_with_post_reset_reselection

if __name__ == "__main__":
    probe.main()
