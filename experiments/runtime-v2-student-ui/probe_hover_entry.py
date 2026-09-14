#!/usr/bin/env python3
"""Run the student-UI probe with an explicit real mouse entry for tooltips."""

from __future__ import annotations

import time

import probe


probe.REPEAT_HOVER_RECT = r'''(() => {
 const repeat=workspace.getBlocksByType('controls_repeat_ext',false)[0];
 if(!repeat)throw new Error('rendered repeat block missing for hover');
 const repeatRoot=repeat.getSvgRoot();
 if(!repeatRoot)throw new Error('rendered repeat SVG root missing for hover');
 const repeatPath=repeatRoot.querySelector('.blocklyPath');
 if(!repeatPath)throw new Error('rendered repeat tooltip-bound SVG path missing for hover');
 const rb=repeatPath.getBoundingClientRect();
 const onPath=(x,y)=>{
   const hit=document.elementFromPoint(x,y);
   return !!(hit&&(hit===repeatPath||repeatPath.contains(hit)));
 };
 const settleOffsets=[[1,0],[-1,0],[0,1],[0,-1],[2,0],[-2,0],[0,2],[0,-2]];
 const entryDirections=[[1,0],[-1,0],[0,1],[0,-1]];
 for(let y=Math.ceil(rb.top)+1;y<Math.floor(rb.bottom)-1;y+=2){
   for(let x=Math.ceil(rb.left)+1;x<Math.floor(rb.right)-1;x+=2){
     if(!onPath(x,y))continue;
     let settle=null;
     for(const [dx,dy] of settleOffsets){
       const sx=x+dx,sy=y+dy;
       if(onPath(sx,sy)){settle={x:sx,y:sy};break;}
     }
     if(!settle)continue;
     for(let radius=2;radius<=24;radius+=2){
       for(const [dx,dy] of entryDirections){
         const ex=x+dx*radius,ey=y+dy*radius;
         if(ex<1||ey<1||ex>=innerWidth-1||ey>=innerHeight-1)continue;
         if(!onPath(ex,ey)){
           const hit=document.elementFromPoint(x,y);
           return {
             x:x-1,y:y-1,width:2,height:2,
             entryX:ex,entryY:ey,targetX:x,targetY:y,
             settleX:settle.x,settleY:settle.y,
             hitTag:hit.tagName,
             hitClass:String(hit.getAttribute&&hit.getAttribute('class')||'')
           };
         }
       }
     }
   }
 }
 throw new Error('no real outside-to-inside tooltip-bound repeat path entry');
})()'''


def causal_hover(self: probe.Cdp, rect: dict[str, float]) -> None:
    """Enter the real tooltip-bound path, then move again while still inside."""

    def move(x: float, y: float) -> None:
        self.call(
            'Input.dispatchMouseEvent',
            {
                'type': 'mouseMoved',
                'x': x,
                'y': y,
                'buttons': 0,
                'pointerType': 'mouse',
            },
        )

    move(rect['entryX'], rect['entryY'])
    time.sleep(.1)
    move(rect['targetX'], rect['targetY'])
    time.sleep(.05)
    move(rect['settleX'], rect['settleY'])


probe.Cdp.hover = causal_hover


if __name__ == '__main__':
    raise SystemExit(probe.main())
