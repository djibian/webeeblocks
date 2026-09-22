#!/usr/bin/env python3
"""Bind post-reset repeat selection and exact delivery observation atomically.

Ready run 35657149471 proved that a point selected in one CDP evaluation can lose
exact ``repeat.pathObject.svgPath`` identity before the immediately following
delivery-probe evaluation, even without intervening pointer input.  Preserve the
ranked post-reset selector from ``probe_clearance_entry`` but perform that
selection and installation of the exact target delivery listeners in one browser
evaluation/current DOM task.

This wrapper adds no pointer input, retry, timer interception, tooltip/workspace
mutation or synthetic visibility.  The canonical interaction remains exactly
three real pointer moves and the public 5 s tooltip oracle is unchanged.
"""

from __future__ import annotations

import json
import time

import probe
import probe_entry
import probe_clearance_entry as ranked


_BIND_SELECTED = r'''
  const entryX=Number(selected.entryX);
  const entryY=Number(selected.entryY);
  const settleX=Number(selected.settleX);
  const settleY=Number(selected.settleY);
  const key='__webeeblocksCiTooltipDelivery';
  if(window[key]&&window[key].cleanup)window[key].cleanup();

  const repeat=window.workspace&&workspace.getBlocksByType('controls_repeat_ext',false)[0];
  const target=repeat&&repeat.pathObject&&repeat.pathObject.svgPath;
  if(!repeat||!target)throw new Error('exact repeat tooltip delivery target is unavailable');
  if(target.tooltip!==repeat)throw new Error('repeat SVG path is not bound to the repeat tooltip owner');

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
  return selected;
'''


def _select_and_bind_delivery(c: probe.Cdp) -> dict[str, object]:
    # One synchronous browser evaluation: no task/evaluation boundary exists
    # between ranked candidate selection and exact target/listener binding.
    expression = (
        "(() => {\n  const selected=("
        + probe.REPEAT_HOVER_RECT
        + ");\n"
        + _BIND_SELECTED
        + "\n})()"
    )
    return c.eval(expression)


def _canonical_hover_with_atomic_post_reset_binding(
    c: probe.Cdp, rect: dict[str, object]
) -> None:
    # Resolve the distinct-owner reset before the first real pointer move.
    before_reset = c.eval(probe.REPEAT_HOVER_RECT)
    ranked._copy_reset_target(rect, before_reset)

    c.call(
        "Input.dispatchMouseEvent",
        {"type": "mouseMoved", "x": rect["outsideX"], "y": rect["outsideY"]},
    )
    time.sleep(0.1)

    # After the real owner reset, select the repeat entry/settle and bind the
    # exact repeat path delivery observer in the same current-DOM evaluation.
    after_reset = _select_and_bind_delivery(c)
    ranked._copy_repeat_target(rect, after_reset)

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
                "deliveryBinding": "same-evaluation",
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


probe_entry._canonical_hover_after_reset = _canonical_hover_with_atomic_post_reset_binding

if __name__ == "__main__":
    probe.main()
