#!/usr/bin/env python3
"""Combine post-reset target reselection with passive geometry/occupancy evidence.

This wrapper keeps the #500 real three-move hover and unchanged public tooltip
oracle while reusing the closed #497 passive diagnostic.  The current repair
also closes the temporal selector/delivery handoff exposed by Ready run
35657149471: after the real distinct-owner reset, candidate selection and exact
repeat-path delivery-listener binding happen in one browser evaluation before
any repeat-entry pointer move is dispatched.

It dispatches no extra input and changes no Blockly, workspace, tooltip, timer or
visibility state.  The public 5 s tooltip oracle and ordinary leave-to-close
assertion remain authoritative.
"""

from __future__ import annotations

import json
import time

import probe_post_hover_occupancy  # noqa: F401 - installs passive diagnostic
import probe_clearance_entry as clearance  # installs ranked post-reset selector
import probe_entry
import probe


_BIND_DELIVERY_HELPER = r'''(() => {
  const helperKey='__webeeblocksCiBindTooltipDelivery';
  window[helperKey]=(rect)=>{
    const key='__webeeblocksCiTooltipDelivery';
    if(window[key]&&window[key].cleanup)window[key].cleanup();

    const repeat=window.workspace&&workspace.getBlocksByType('controls_repeat_ext',false)[0];
    const target=repeat&&repeat.pathObject&&repeat.pathObject.svgPath;
    if(!repeat||!target)throw new Error('exact repeat tooltip delivery target is unavailable');
    if(target.tooltip!==repeat)throw new Error('repeat SVG path is not bound to the repeat tooltip owner');

    const entryX=Number(rect.entryX);
    const entryY=Number(rect.entryY);
    const settleX=Number(rect.settleX);
    const settleY=Number(rect.settleY);
    if(![entryX,entryY,settleX,settleY].every(Number.isFinite)){
      throw new Error('post-reset tooltip entry/settle coordinates are invalid');
    }

    const entryHit=document.elementFromPoint(entryX,entryY);
    const settleHit=document.elementFromPoint(settleX,settleY);
    if(entryHit!==target||settleHit!==target){
      throw new Error('atomic post-reset tooltip entry/settle does not resolve to repeat.pathObject.svgPath');
    }

    const targetClass=String((target.getAttribute&&target.getAttribute('class'))||'');
    if(!targetClass.includes('blocklyPath'))throw new Error('repeat tooltip delivery target is not a public Blockly path');

    const types=['mousemove','mouseover','mouseout','pointermove','pointerover','pointerout'];
    const state={
      target:target,repeat:repeat,
      entryX:entryX,entryY:entryY,settleX:settleX,settleY:settleY,
      document:{},targetEvents:{},last:{},targetLast:{},targetSequence:[],cleanup:null
    };
    const pack=e=>({
      x:e.clientX,y:e.clientY,buttons:e.buttons,defaultPrevented:e.defaultPrevented,
      targetTag:(e.target&&e.target.tagName)||'',
      targetClass:String((e.target&&e.target.getAttribute&&e.target.getAttribute('class'))||''),
      relatedClass:String((e.relatedTarget&&e.relatedTarget.getAttribute&&e.relatedTarget.getAttribute('class'))||''),
      targetIsExactRepeatPath:e.target===target,
      targetSharesRepeatTooltip:!!(e.target&&e.target.tooltip===repeat),
      relatedIsExactRepeatPath:e.relatedTarget===target,
      relatedSharesRepeatTooltip:!!(e.relatedTarget&&e.relatedTarget.tooltip===repeat)
    });
    const documentHandlers={};
    const targetHandlers={};
    for(const type of types){
      state.document[type]=0; state.targetEvents[type]=0;
      documentHandlers[type]=e=>{state.document[type]+=1;state.last[type]=pack(e);};
      targetHandlers[type]=e=>{state.targetEvents[type]+=1;state.targetLast[type]=pack(e);state.targetSequence.push(type);};
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
  };
  return true;
})()'''


def _select_and_bind_delivery(c: probe.Cdp) -> dict[str, object]:
    # The selector IIFE and delivery binding execute in the same Runtime.evaluate
    # task.  There is therefore no second browser-evaluation boundary carrying
    # selected coordinates before the exact target/listeners are bound.
    expression = (
        "(() => {"
        "const rect=(" + probe.REPEAT_HOVER_RECT + ");"
        "const bind=window.__webeeblocksCiBindTooltipDelivery;"
        "if(typeof bind!=='function')throw new Error('atomic tooltip delivery binder unavailable');"
        "bind(rect);"
        "delete window.__webeeblocksCiBindTooltipDelivery;"
        "return rect;"
        "})()"
    )
    return c.eval(expression)


def _canonical_hover_with_atomic_post_reset_binding(
    c: probe.Cdp, rect: dict[str, object]
) -> None:
    # ``hover_with_passive_diagnostics`` already performed the focus check.
    # Re-evaluate only the distinct-owner reset point before the first real move.
    before_reset = c.eval(probe.REPEAT_HOVER_RECT)
    clearance._copy_reset_target(rect, before_reset)

    # Defining the helper observes or mutates no Blockly/DOM target state.  The
    # actual selected coordinates and exact listener target are resolved together
    # later in one browser evaluation after the real owner-reset move.
    c.eval(_BIND_DELIVERY_HELPER)
    c.call(
        "Input.dispatchMouseEvent",
        {"type": "mouseMoved", "x": rect["outsideX"], "y": rect["outsideY"]},
    )
    time.sleep(0.1)

    after_reset = _select_and_bind_delivery(c)
    clearance._copy_repeat_target(rect, after_reset)

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


# probe_entry.hover_with_passive_diagnostics resolves this module-global helper at
# call time, so replacing it here keeps the existing delivery readback/oracles and
# changes only the post-reset selection -> exact-listener-binding handoff.
probe_entry._canonical_hover_after_reset = _canonical_hover_with_atomic_post_reset_binding


if __name__ == "__main__":
    probe.main()
