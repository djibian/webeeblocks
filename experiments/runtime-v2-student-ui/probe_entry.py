#!/usr/bin/env python3
"""Run the canonical student UI probe with passive tooltip delivery diagnostics.

The product/runtime probe remains authoritative. This entrypoint changes no
student-visible behavior and never retries a tooltip interaction. Immediately
before the existing single canonical hover, the same CDP session brings the Robot
Window to the front, snapshots Blockly's public gesture lifecycle, and installs
passive listeners proving whether ordinary public mouse/pointer entry and move
events reach the exact tooltip-bound Blockly path at DOM target phase. It also
records read-only Blockly tooltip scheduler state before and immediately after
that unchanged hover so a recurrence can distinguish blocked/binding/scheduling
failures without manufacturing tooltip state. The canonical 5 s visible/non-empty/
localized tooltip oracle remains unchanged.
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


def _tooltip_snapshot(c: probe.Cdp, rect: dict[str, object]) -> dict[str, object]:
    settle_x = float(rect["settleX"])
    settle_y = float(rect["settleY"])
    expression = r'''((x,y) => {
      const tooltip=window.Blockly&&Blockly.Tooltip;
      const target=document.elementFromPoint(x,y);
      const element=tooltip&&tooltip.element_;
      const poisoned=tooltip&&tooltip.poisonedElement_;
      const div=tooltip&&tooltip.DIV;
      const classOf=node=>String((node&&node.getAttribute&&node.getAttribute('class'))||'');
      return {
        available:!!tooltip,
        blocked:tooltip ? !!tooltip.blocked_ : null,
        visible:tooltip ? !!tooltip.visible : null,
        targetClass:classOf(target),
        targetHasTooltip:!!(target&&target.tooltip),
        targetMouseOverBound:!!(target&&target.mouseOverWrapper_),
        targetMouseOutBound:!!(target&&target.mouseOutWrapper_),
        elementIsTarget:!!tooltip&&element===target,
        elementHasTooltip:!!(element&&element.tooltip),
        elementClass:classOf(element),
        poisonedIsTarget:!!tooltip&&poisoned===target,
        showScheduled:!!(tooltip&&tooltip.showPid_),
        mouseOutScheduled:!!(tooltip&&tooltip.mouseOutPid_),
        divExists:!!div,
        divDisplay:div ? getComputedStyle(div).display : null,
        divText:div ? String(div.innerText||div.textContent||'').trim().slice(0,200) : null
      };
    })(%s,%s)''' % (settle_x, settle_y)
    state = c.eval(expression)
    if not state or not state.get("available"):
        raise RuntimeError(
            "Blockly tooltip lifecycle is unavailable for passive diagnostics: "
            + json.dumps(state, sort_keys=True)
        )
    return state


def _install_delivery_probe(c: probe.Cdp, rect: dict[str, object]) -> None:
    settle_x = float(rect["settleX"])
    settle_y = float(rect["settleY"])
    expression = r'''((x,y) => {
      const key='__webeeblocksCiTooltipDelivery';
      if(window[key]&&window[key].cleanup)window[key].cleanup();
      const target=document.elementFromPoint(x,y);
      const targetClass=String((target&&target.getAttribute&&target.getAttribute('class'))||'');
      if(!target||!targetClass.includes('blocklyPath'))throw new Error('tooltip delivery target is not the exact public Blockly path');
      const types=['mousemove','mouseover','mouseout','pointermove','pointerover','pointerout'];
      const state={document:{},target:{},last:{},targetLast:{},targetSequence:[],cleanup:null};
      const pack=e=>({
        x:e.clientX,y:e.clientY,buttons:e.buttons,defaultPrevented:e.defaultPrevented,
        targetTag:(e.target&&e.target.tagName)||'',
        targetClass:String((e.target&&e.target.getAttribute&&e.target.getAttribute('class'))||''),
        relatedClass:String((e.relatedTarget&&e.relatedTarget.getAttribute&&e.relatedTarget.getAttribute('class'))||'')
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
        hitClass:String((hit&&hit.getAttribute&&hit.getAttribute('class'))||'')
      };
      s.cleanup(); delete window[key];
      return result;
    })(%s,%s)''' % (settle_x, settle_y)
    return c.eval(expression)


def _cleanup_delivery_probe(c: probe.Cdp) -> None:
    c.eval(
        "(() => {const s=window.__webeeblocksCiTooltipDelivery;if(s&&s.cleanup)s.cleanup();delete window.__webeeblocksCiTooltipDelivery;return true;})()"
    )


def hover_with_passive_diagnostics(self: probe.Cdp, rect: dict[str, object]) -> None:
    focus = _same_session_focus(self)
    gesture = _gesture_snapshot(self)
    tooltip_before = _tooltip_snapshot(self, rect)
    _install_delivery_probe(self, rect)
    try:
        # Exactly one unchanged canonical outside -> path -> settle trajectory.
        # No second hover, no wait for gesture state, and no outcome-based retry.
        _ORIGINAL_HOVER(self, rect)
        tooltip_after = _tooltip_snapshot(self, rect)
        delivery = _read_delivery(self, rect)
    except BaseException:
        try:
            tooltip_after = _tooltip_snapshot(self, rect)
            delivery = _read_delivery(self, rect)
            print(
                "WEBEEBLOCKS_TOOLTIP_CAUSAL_DIAGNOSTIC "
                + json.dumps(
                    {
                        "focus": focus,
                        "gesture": gesture,
                        "tooltipBefore": tooltip_before,
                        "tooltipAfter": tooltip_after,
                        "delivery": delivery,
                    },
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
    evidence = {
        "focus": focus,
        "gesture": gesture,
        "tooltipBefore": tooltip_before,
        "tooltipAfter": tooltip_after,
        "delivery": delivery,
    }
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
