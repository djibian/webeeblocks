#!/usr/bin/env python3
"""Run the single-entry tooltip candidate with exact current-path delivery proof.

The one real outside-to-repeat-path pointer entry and the unchanged public tooltip
oracle remain authoritative.  The delivery observer is installed only after the
pointer has reached the required outside origin, then binds directly to the
current ``repeat.pathObject.svgPath`` and proves that the real entry event reaches
that exact DOM node and tooltip owner.  It does not wrap timers, synthesize input,
mutate Blockly/workspace state, retry the hover, or change product behavior.
"""

from __future__ import annotations

import json
import time

import probe
import probe_entry
import probe_post_hover_entry as base


_INSTALL_CURRENT_REPEAT_DELIVERY = r'''((x,y) => {
  const key='__webeeblocksCiTooltipDelivery';
  const old=window[key];
  if(old&&old.cleanup)old.cleanup();

  const repeat=workspace.getBlocksByType('controls_repeat_ext',false)[0];
  if(!repeat)throw new Error('rendered repeat block missing before single entry');
  const target=repeat.pathObject&&repeat.pathObject.svgPath;
  if(!target)throw new Error('rendered repeat has no current tooltip-bound path');
  const hit=document.elementFromPoint(x,y);
  if(hit!==target)throw new Error('single-entry coordinate does not hit current repeat path');
  if(target.tooltip!==repeat)throw new Error('current repeat path lost its repeat tooltip owner');

  const types=['mousemove','mouseover','mouseout','pointermove','pointerover','pointerout'];
  const state={document:{},target:{},last:{},targetLast:{},targetSequence:[],boundTarget:target,repeat:repeat,cleanup:null};
  const pack=e=>({
    x:e.clientX,y:e.clientY,buttons:e.buttons,defaultPrevented:e.defaultPrevented,
    targetTag:(e.target&&e.target.tagName)||'',
    targetClass:String((e.target&&e.target.getAttribute&&e.target.getAttribute('class'))||''),
    relatedClass:String((e.relatedTarget&&e.relatedTarget.getAttribute&&e.relatedTarget.getAttribute('class'))||''),
    targetIsBound:e.target===target,
    targetSharesTooltip:!!(e.target&&e.target.tooltip&&e.target.tooltip===repeat)
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
  return {
    hitIsCurrentRepeatPath:hit===target,
    tooltipOwnerIsRepeat:target.tooltip===repeat,
    hasPointerOverBinding:!!target.mouseOverWrapper_,
    hasPointerOutBinding:!!target.mouseOutWrapper_,
    targetClass:String((target.getAttribute&&target.getAttribute('class'))||'')
  };
})(%s,%s)'''


_READ_CURRENT_REPEAT_DELIVERY = r'''((x,y) => {
  const key='__webeeblocksCiTooltipDelivery';
  const s=window[key];
  if(!s)return null;
  const repeat=workspace.getBlocksByType('controls_repeat_ext',false)[0];
  const current=repeat&&repeat.pathObject&&repeat.pathObject.svgPath;
  const hit=document.elementFromPoint(x,y);
  const result={
    document:s.document,target:s.target,last:s.last,targetLast:s.targetLast,
    targetSequence:s.targetSequence,
    hitTag:(hit&&hit.tagName)||'',
    hitClass:String((hit&&hit.getAttribute&&hit.getAttribute('class'))||''),
    hitIsBoundTarget:hit===s.boundTarget,
    currentRepeatPathIsBoundTarget:current===s.boundTarget,
    hitIsCurrentRepeatPath:hit===current,
    ownerStillBound:!!repeat&&s.boundTarget.tooltip===repeat,
    currentOwnerIsRepeat:!!repeat&&!!current&&current.tooltip===repeat
  };
  s.cleanup(); delete window[key];
  return result;
})(%s,%s)'''


_CLEANUP_CURRENT_REPEAT_DELIVERY = r'''(() => {
  const key='__webeeblocksCiTooltipDelivery';
  const s=window[key];
  if(!s)return false;
  if(s.cleanup)s.cleanup();
  delete window[key];
  return true;
})()'''


def _read_delivery(c: probe.Cdp, rect: dict[str, object]) -> dict[str, object] | None:
    return base._ORIGINAL_EVAL(
        c,
        _READ_CURRENT_REPEAT_DELIVERY
        % (float(rect["entryX"]), float(rect["entryY"])),
    )


def _perform_single_entry_with_current_target(
    self: probe.Cdp, rect: dict[str, object]
) -> None:
    focus = probe_entry._same_session_focus(self)
    gesture = probe_entry._gesture_snapshot(self)

    # Establish the real outside origin first.  Resolving the DOM target before
    # this move was the exact-head failure in the preceding candidate: Blockly
    # could legitimately replace the path node before the entry event arrived.
    self.call(
        "Input.dispatchMouseEvent",
        {
            "type": "mouseMoved",
            "x": rect["outsideX"],
            "y": rect["outsideY"],
        },
    )
    time.sleep(0.1)

    installed = base._ORIGINAL_EVAL(
        self,
        _INSTALL_CURRENT_REPEAT_DELIVERY
        % (float(rect["entryX"]), float(rect["entryY"])),
    )
    if (
        not installed
        or not installed.get("hitIsCurrentRepeatPath")
        or not installed.get("tooltipOwnerIsRepeat")
        or not installed.get("hasPointerOverBinding")
        or not installed.get("hasPointerOutBinding")
    ):
        raise RuntimeError(
            "current repeat path is not safely bound immediately before single entry: "
            + json.dumps(installed, sort_keys=True)
        )

    delivery = None
    try:
        # Exactly one real entry onto the current exact tooltip-bound repeat path.
        self.call(
            "Input.dispatchMouseEvent",
            {"type": "mouseMoved", "x": rect["entryX"], "y": rect["entryY"]},
        )
        time.sleep(0.04)
        delivery = _read_delivery(self, rect)
    except BaseException:
        try:
            delivery = _read_delivery(self, rect)
            print(
                "WEBEEBLOCKS_TOOLTIP_CAUSAL_DIAGNOSTIC "
                + json.dumps(
                    {"focus": focus, "gesture": gesture, "delivery": delivery},
                    sort_keys=True,
                )
            )
        except Exception:
            try:
                base._ORIGINAL_EVAL(self, _CLEANUP_CURRENT_REPEAT_DELIVERY)
            except Exception:
                pass
        raise

    if not delivery:
        raise RuntimeError("single-entry hover produced no current-path delivery evidence")
    evidence = {"focus": focus, "gesture": gesture, "delivery": delivery}
    print("WEBEEBLOCKS_TOOLTIP_CAUSAL_DIAGNOSTIC " + json.dumps(evidence, sort_keys=True))

    document = delivery.get("document", {})
    if document.get("mousemove", 0) < 1 or document.get("pointermove", 0) < 1:
        raise RuntimeError(
            "single entry did not deliver public document move events: "
            + json.dumps(evidence, sort_keys=True)
        )
    if document.get("mouseover", 0) < 1 or document.get("pointerover", 0) < 1:
        raise RuntimeError(
            "single entry did not deliver public document entry events: "
            + json.dumps(evidence, sort_keys=True)
        )

    target = delivery.get("target", {})
    if (
        target.get("mousemove", 0) < 1
        or target.get("pointermove", 0) < 1
        or target.get("mouseover", 0) < 1
        or target.get("pointerover", 0) < 1
    ):
        raise RuntimeError(
            "single entry did not reach the current exact repeat path at target phase: "
            + json.dumps(evidence, sort_keys=True)
        )

    mouse_sequence = [
        event
        for event in delivery.get("targetSequence", [])
        if event in ("mouseover", "mouseout", "mousemove")
    ]
    if not mouse_sequence or mouse_sequence[-1] != "mousemove":
        raise RuntimeError(
            "single entry did not finish with a stable current-path mousemove: "
            + json.dumps(evidence, sort_keys=True)
        )

    if not all(
        delivery.get(name)
        for name in (
            "hitIsBoundTarget",
            "currentRepeatPathIsBoundTarget",
            "hitIsCurrentRepeatPath",
            "ownerStillBound",
            "currentOwnerIsRepeat",
        )
    ):
        raise RuntimeError(
            "single-entry repeat path identity changed during delivery: "
            + json.dumps(evidence, sort_keys=True)
        )

    target_mouse = delivery.get("targetLast", {}).get("mousemove", {})
    target_pointer = delivery.get("targetLast", {}).get("pointermove", {})
    if (
        "blocklyPath" not in str(delivery.get("hitClass", ""))
        or not target_mouse.get("targetIsBound")
        or not target_pointer.get("targetIsBound")
        or not target_mouse.get("targetSharesTooltip")
        or not target_pointer.get("targetSharesTooltip")
    ):
        raise RuntimeError(
            "single-entry events were not owned by the exact tooltip-bound repeat path: "
            + json.dumps(evidence, sort_keys=True)
        )


def hover_with_current_target_diagnostics(
    self: probe.Cdp, rect: dict[str, object]
) -> None:
    _perform_single_entry_with_current_target(self, rect)
    installed = base._ORIGINAL_EVAL(
        self,
        base._POST_HOVER_INSTALL
        % (float(rect["entryX"]), float(rect["entryY"])),
    )
    if not installed:
        raise RuntimeError("passive post-hover tooltip observer could not be installed")
    self._webeeblocks_post_hover_rect = dict(rect)
    self._webeeblocks_post_hover_started = time.monotonic()
    self._webeeblocks_post_hover_late_emitted = False
    self._webeeblocks_post_hover_active = True


# Importing the prior candidate retains its stable rect and passive eval observer.
# Replace only its rejected pre-entry target-binding implementation.
probe.Cdp.hover = hover_with_current_target_diagnostics

if __name__ == "__main__":
    probe.main()
