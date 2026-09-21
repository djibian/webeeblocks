#!/usr/bin/env python3
"""Run the canonical student UI probe with passive tooltip delivery diagnostics.

The product/runtime probe remains authoritative. This entrypoint changes no
student-visible behavior and never retries a tooltip interaction. Immediately
before the existing single canonical hover, the same CDP session brings the Robot
Window to the front, snapshots Blockly's public gesture lifecycle, and installs
passive listeners proving whether ordinary public mouse/pointer entry and move
events reach the exact tooltip-bound Blockly path at DOM target phase. The
canonical 5 s visible/non-empty/localized tooltip oracle remains unchanged.
"""

from __future__ import annotations

import json
import time

import probe


_ORIGINAL_HOVER = probe.Cdp.hover


def _same_session_focus(c: probe.Cdp) -> dict[str, object]:
    c.call("Page.bringToFront")
    deadline = time.time() + 2.0
    state = None
    while time.time() < deadline:
        state = c.eval(
            "({focused:document.hasFocus(),visibility:document.visibilityState,workspace:!!window.workspace})"
        )
        if (
            state
            and state.get("focused")
            and state.get("visibility") == "visible"
            and state.get("workspace")
        ):
            return state
        time.sleep(0.05)
    raise RuntimeError(
        "Robot Window lost visible focus immediately before real tooltip hover: "
        + json.dumps(state, sort_keys=True)
    )


def _gesture_snapshot(c: probe.Cdp) -> dict[str, object]:
    state = c.eval(
        r'''(() => {
          const gesture=window.Blockly&&Blockly.Gesture;
          const available=!!gesture&&typeof gesture.inProgress==='function';
          return {available:available,inProgress:available ? !!gesture.inProgress() : null};
        })()'''
    )
    if not state or not state.get("available"):
        raise RuntimeError(
            "Blockly gesture lifecycle is unavailable before real tooltip hover: "
            + json.dumps(state, sort_keys=True)
        )
    return state


def _install_delivery_probe(c: probe.Cdp, rect: dict[str, object]) -> None:
    entry_x = float(rect["entryX"])
    entry_y = float(rect["entryY"])
    settle_x = float(rect["settleX"])
    settle_y = float(rect["settleY"])
    expression = r'''((entryX,entryY,settleX,settleY) => {
      const key='__webeeblocksCiTooltipDelivery';
      if(window[key]&&window[key].cleanup)window[key].cleanup();

      const repeat=window.workspace&&workspace.getBlocksByType('controls_repeat_ext',false)[0];
      const target=repeat&&repeat.pathObject&&repeat.pathObject.svgPath;
      if(!repeat||!target)throw new Error('exact repeat tooltip delivery target is unavailable');
      if(target.tooltip!==repeat)throw new Error('repeat SVG path is not bound to the repeat tooltip owner');

      const entryHit=document.elementFromPoint(entryX,entryY);
      const settleHit=document.elementFromPoint(settleX,settleY);
      if(entryHit!==target||settleHit!==target){
        throw new Error('post-reset tooltip entry/settle does not resolve to repeat.pathObject.svgPath');
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
    })(%s,%s,%s,%s)''' % (entry_x, entry_y, settle_x, settle_y)
    c.eval(expression)


def _read_delivery(c: probe.Cdp, rect: dict[str, object]) -> dict[str, object]:
    entry_x = float(rect["entryX"])
    entry_y = float(rect["entryY"])
    settle_x = float(rect["settleX"])
    settle_y = float(rect["settleY"])
    expression = r'''((entryX,entryY,settleX,settleY) => {
      const key='__webeeblocksCiTooltipDelivery';
      const s=window[key];
      if(!s)return null;

      const repeat=window.workspace&&workspace.getBlocksByType('controls_repeat_ext',false)[0];
      const target=repeat&&repeat.pathObject&&repeat.pathObject.svgPath;
      const entryHit=document.elementFromPoint(entryX,entryY);
      const settleHit=document.elementFromPoint(settleX,settleY);
      const targetStable=!!target&&target===s.target&&repeat===s.repeat&&target.tooltip===repeat;
      const result={
        document:s.document,target:s.targetEvents,last:s.last,targetLast:s.targetLast,targetSequence:s.targetSequence,
        exactTargetStable:targetStable,
        entryHitIsExactTarget:entryHit===target,
        settleHitIsExactTarget:settleHit===target,
        entryHitSharesRepeatTooltip:!!(entryHit&&repeat&&entryHit.tooltip===repeat),
        settleHitSharesRepeatTooltip:!!(settleHit&&repeat&&settleHit.tooltip===repeat),
        hitTag:(settleHit&&settleHit.tagName)||'',
        hitClass:String((settleHit&&settleHit.getAttribute&&settleHit.getAttribute('class'))||'')
      };
      s.cleanup(); delete window[key];
      return result;
    })(%s,%s,%s,%s)''' % (entry_x, entry_y, settle_x, settle_y)
    return c.eval(expression)


def _cleanup_delivery_probe(c: probe.Cdp) -> None:
    c.eval(
        "(() => {const s=window.__webeeblocksCiTooltipDelivery;if(s&&s.cleanup)s.cleanup();delete window.__webeeblocksCiTooltipDelivery;return true;})()"
    )


def _canonical_hover_after_reset(c: probe.Cdp, rect: dict[str, object]) -> None:
    """Preserve the canonical three real moves while binding after the first move."""
    c.call(
        "Input.dispatchMouseEvent",
        {"type": "mouseMoved", "x": rect["outsideX"], "y": rect["outsideY"]},
    )
    time.sleep(0.1)
    _install_delivery_probe(c, rect)
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


def hover_with_passive_diagnostics(self: probe.Cdp, rect: dict[str, object]) -> None:
    focus = _same_session_focus(self)
    gesture = _gesture_snapshot(self)
    try:
        # Keep the canonical outside -> path -> settle trajectory and timings.
        # Bind the exact repeat target only after the real outside/reset move, so
        # the prerequisite describes the DOM that will actually receive entry.
        # No extra move, second hover, gesture wait, or outcome-based retry.
        _canonical_hover_after_reset(self, rect)
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
                _cleanup_delivery_probe(self)
            except Exception:
                pass
        raise

    if not delivery:
        raise RuntimeError("real tooltip hover produced no public pointer-delivery observation")
    evidence = {"focus": focus, "gesture": gesture, "delivery": delivery}
    print("WEBEEBLOCKS_TOOLTIP_CAUSAL_DIAGNOSTIC " + json.dumps(evidence, sort_keys=True))

    if (
        not delivery.get("exactTargetStable")
        or not delivery.get("entryHitIsExactTarget")
        or not delivery.get("settleHitIsExactTarget")
        or not delivery.get("entryHitSharesRepeatTooltip")
        or not delivery.get("settleHitSharesRepeatTooltip")
    ):
        raise RuntimeError(
            "real tooltip hover lost exact repeat.pathObject.svgPath identity or tooltip ownership: "
            + json.dumps(evidence, sort_keys=True)
        )

    document = delivery.get("document", {})
    if document.get("mousemove", 0) < 2 or document.get("pointermove", 0) < 2:
        raise RuntimeError(
            "real tooltip hover did not deliver bounded public document move events: "
            + json.dumps(evidence, sort_keys=True)
        )
    if document.get("mouseover", 0) < 1 or document.get("pointerover", 0) < 1:
        raise RuntimeError(
            "real tooltip hover did not deliver public document entry events: "
            + json.dumps(evidence, sort_keys=True)
        )

    target = delivery.get("target", {})
    if (
        target.get("mousemove", 0) < 2
        or target.get("pointermove", 0) < 2
        or target.get("mouseover", 0) < 1
        or target.get("pointerover", 0) < 1
    ):
        raise RuntimeError(
            "real tooltip hover did not reach repeat.pathObject.svgPath at target phase: "
            + json.dumps(evidence, sort_keys=True)
        )
    mouse_sequence = [
        event
        for event in delivery.get("targetSequence", [])
        if event in ("mouseover", "mouseout", "mousemove")
    ]
    if not mouse_sequence or mouse_sequence[-1] != "mousemove":
        raise RuntimeError(
            "real tooltip hover did not finish with a stable exact repeat-path target mousemove: "
            + json.dumps(evidence, sort_keys=True)
        )

    target_mouse = delivery.get("targetLast", {}).get("mousemove", {})
    target_pointer = delivery.get("targetLast", {}).get("pointermove", {})
    if (
        not target_mouse.get("targetIsExactRepeatPath")
        or not target_pointer.get("targetIsExactRepeatPath")
        or not target_mouse.get("targetSharesRepeatTooltip")
        or not target_pointer.get("targetSharesRepeatTooltip")
    ):
        raise RuntimeError(
            "real tooltip hover event target was not the exact repeat path / tooltip owner: "
            + json.dumps(evidence, sort_keys=True)
        )


probe.Cdp.hover = hover_with_passive_diagnostics

if __name__ == "__main__":
    probe.main()
