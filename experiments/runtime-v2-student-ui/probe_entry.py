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
    # Focus can change compositor/layout state between the canonical pre-hover
    # geometry read and real input. Re-resolve the same authorized hover geometry
    # after focus, then bind evidence to Blockly's current exact repeat path.
    fresh_rect = c.eval(probe.REPEAT_HOVER_RECT)
    if not isinstance(fresh_rect, dict):
        raise RuntimeError("real tooltip hover geometry unavailable after focus")
    rect.clear()
    rect.update(fresh_rect)

    settle_x = float(rect["settleX"])
    settle_y = float(rect["settleY"])
    expression = r'''((x,y) => {
      const key='__webeeblocksCiTooltipDelivery';
      if(window[key]&&window[key].cleanup)window[key].cleanup();
      const repeat=workspace.getBlocksByType('controls_repeat_ext',false)[0];
      const target=repeat&&repeat.pathObject&&repeat.pathObject.svgPath;
      if(!target)throw new Error('current repeat has no exact tooltip-bound Blockly path');
      if(target.tooltip!==repeat)throw new Error('current repeat path is not bound to its tooltip owner');
      const hit=document.elementFromPoint(x,y);
      if(hit!==target)throw new Error('tooltip delivery coordinate does not hit the current exact repeat path after focus');
      const targetClass=String((target.getAttribute&&target.getAttribute('class'))||'');
      if(!targetClass.includes('blocklyPath'))throw new Error('current exact repeat path is not a public Blockly path');
      const types=['mousemove','mouseover','mouseout','pointermove','pointerover','pointerout'];
      const state={observedTarget:target,document:{},target:{},last:{},targetLast:{},targetSequence:[],cleanup:null};
      const pack=e=>({
        x:e.clientX,y:e.clientY,buttons:e.buttons,defaultPrevented:e.defaultPrevented,
        targetTag:(e.target&&e.target.tagName)||'',
        targetClass:String((e.target&&e.target.getAttribute&&e.target.getAttribute('class'))||''),
        relatedClass:String((e.relatedTarget&&e.relatedTarget.getAttribute&&e.relatedTarget.getAttribute('class'))||''),
        targetIsObserved:e.target===target,relatedIsObserved:e.relatedTarget===target
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
      return true;
    })(%s,%s)''' % (settle_x, settle_y)
    c.eval(expression)


def _read_delivery(c: probe.Cdp, rect: dict[str, object]) -> dict[str, object]:
    settle_x = float(rect["settleX"])
    settle_y = float(rect["settleY"])
    expression = r'''((x,y) => {
      const key='__webeeblocksCiTooltipDelivery';
      const s=window[key];
      if(!s)return null;
      const hit=document.elementFromPoint(x,y);
      const result={
        document:s.document,target:s.target,last:s.last,targetLast:s.targetLast,targetSequence:s.targetSequence,
        hitTag:(hit&&hit.tagName)||'',
        hitClass:String((hit&&hit.getAttribute&&hit.getAttribute('class'))||''),
        hitIsObserved:hit===s.observedTarget
      };
      s.cleanup(); delete window[key];
      return result;
    })(%s,%s)''' % (settle_x, settle_y)
    result = c.eval(expression)
    if not result or result.get("hitIsObserved") is not True:
        raise RuntimeError(
            "tooltip delivery coordinate left the current exact repeat path before evidence read: "
            + json.dumps(result, sort_keys=True)
        )
    return result


def _cleanup_delivery_probe(c: probe.Cdp) -> None:
    c.eval(
        "(() => {const s=window.__webeeblocksCiTooltipDelivery;if(s&&s.cleanup)s.cleanup();delete window.__webeeblocksCiTooltipDelivery;return true;})()"
    )


def hover_with_passive_diagnostics(self: probe.Cdp, rect: dict[str, object]) -> None:
    focus = _same_session_focus(self)
    gesture = _gesture_snapshot(self)
    _install_delivery_probe(self, rect)
    try:
        # Exactly one unchanged canonical outside -> path -> settle trajectory.
        # No second hover, no wait for gesture state, and no outcome-based retry.
        _ORIGINAL_HOVER(self, rect)
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
            "real tooltip hover did not reach the exact Blockly path at target phase: "
            + json.dumps(evidence, sort_keys=True)
        )
    mouse_sequence = [
        event
        for event in delivery.get("targetSequence", [])
        if event in ("mouseover", "mouseout", "mousemove")
    ]
    if not mouse_sequence or mouse_sequence[-1] != "mousemove":
        raise RuntimeError(
            "real tooltip hover did not finish with a stable exact-path target mousemove: "
            + json.dumps(evidence, sort_keys=True)
        )

    hit_class = str(delivery.get("hitClass", ""))
    target_mouse = delivery.get("targetLast", {}).get("mousemove", {})
    target_pointer = delivery.get("targetLast", {}).get("pointermove", {})
    if (
        "blocklyPath" not in hit_class
        or "blocklyPath" not in str(target_mouse.get("targetClass", ""))
        or "blocklyPath" not in str(target_pointer.get("targetClass", ""))
    ):
        raise RuntimeError(
            "real tooltip hover did not settle on the exact public Blockly path: "
            + json.dumps(evidence, sort_keys=True)
        )


probe.Cdp.hover = hover_with_passive_diagnostics

if __name__ == "__main__":
    probe.main()
