#!/usr/bin/env python3
"""Run the canonical student UI probe with exact same-session hover diagnostics.

The product/runtime probe remains authoritative. This entrypoint only strengthens
its real-tooltip evidence: immediately before the single canonical hover, the
same CDP session brings the Robot Window to the front, records Blockly's public
gesture lifecycle state, and passively proves that public mouse/pointer entry and
movement reach the exact tooltip-bound Blockly path selected by the existing
probe. It does not wait on or mutate gesture/tooltip state, mutate workspace
state, change timeout values or pass conditions, or add a second hover attempt.
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


def _gesture_state(c: probe.Cdp) -> dict[str, object]:
    return c.eval(
        r'''(() => {
          const gesture=window.Blockly&&Blockly.Gesture;
          const available=!!gesture&&typeof gesture.inProgress==='function';
          return {
            available:available,
            inProgress:available ? !!gesture.inProgress() : null
          };
        })()'''
    )


def _install_delivery_probe(c: probe.Cdp) -> None:
    c.eval(
        r'''(() => {
          const key='__webeeblocksCiTooltipDelivery';
          if(window[key]&&window[key].cleanup)window[key].cleanup();
          const repeat=workspace.getBlocksByType('controls_repeat_ext',false)[0];
          const path=repeat&&repeat.pathObject&&repeat.pathObject.svgPath;
          if(!path)throw new Error('exact repeat tooltip path unavailable for passive delivery proof');
          const state={
            mousemove:0,mouseover:0,pointermove:0,pointerover:0,
            pathMousemove:0,pathMouseover:0,pathPointermove:0,pathPointerover:0,
            last:{},pathLast:{},cleanup:null
          };
          const pack=e=>({x:e.clientX,y:e.clientY,targetTag:(e.target&&e.target.tagName)||'',targetClass:String((e.target&&e.target.getAttribute&&e.target.getAttribute('class'))||'')});
          const documentHandlers={};
          const pathHandlers={};
          for(const type of ['mousemove','mouseover','pointermove','pointerover']){
            documentHandlers[type]=e=>{state[type]+=1;state.last[type]=pack(e);};
            document.addEventListener(type,documentHandlers[type],true);
            const keyName='path'+type[0].toUpperCase()+type.slice(1);
            pathHandlers[type]=e=>{state[keyName]+=1;state.pathLast[type]=pack(e);};
            path.addEventListener(type,pathHandlers[type],true);
          }
          state.cleanup=()=>{
            for(const type of Object.keys(documentHandlers))document.removeEventListener(type,documentHandlers[type],true);
            for(const type of Object.keys(pathHandlers))path.removeEventListener(type,pathHandlers[type],true);
          };
          window[key]=state;
          return true;
        })()'''
    )


def _read_delivery(c: probe.Cdp, rect: dict[str, object]) -> dict[str, object]:
    settle_x = float(rect["settleX"])
    settle_y = float(rect["settleY"])
    expression = r'''((x,y) => {
      const key='__webeeblocksCiTooltipDelivery';
      const s=window[key];
      if(!s)return null;
      const hit=document.elementFromPoint(x,y);
      const result={
        mousemove:s.mousemove,mouseover:s.mouseover,pointermove:s.pointermove,pointerover:s.pointerover,
        pathMousemove:s.pathMousemove,pathMouseover:s.pathMouseover,pathPointermove:s.pathPointermove,pathPointerover:s.pathPointerover,
        last:s.last,pathLast:s.pathLast,
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


def _print_diagnostic(
    focus: dict[str, object],
    gesture: dict[str, object],
    delivery: dict[str, object] | None,
    *,
    outcome: str,
    error: BaseException | None = None,
    diagnostic_error: BaseException | None = None,
) -> None:
    diagnostic: dict[str, object] = {
        "focus": focus,
        "gesture": gesture,
        "delivery": delivery,
        "outcome": outcome,
    }
    if error is not None:
        diagnostic["error"] = {"type": type(error).__name__, "message": str(error)}
    if diagnostic_error is not None:
        diagnostic["diagnosticError"] = {
            "type": type(diagnostic_error).__name__,
            "message": str(diagnostic_error),
        }
    print(
        "WEBEEBLOCKS_STUDENT_UI_HOVER_DIAGNOSTIC "
        + json.dumps(diagnostic, sort_keys=True)
    )


def hover_with_same_session_delivery(self: probe.Cdp, rect: dict[str, object]) -> None:
    focus = _same_session_focus(self)
    gesture = _gesture_state(self)
    if not gesture or not gesture.get("available"):
        raise RuntimeError(
            "Blockly gesture lifecycle is unavailable before real tooltip hover: "
            + json.dumps({"focus": focus, "gesture": gesture}, sort_keys=True)
        )
    print(
        "WEBEEBLOCKS_STUDENT_UI_HOVER_READY "
        + json.dumps({"focus": focus, "gesture": gesture}, sort_keys=True)
    )
    _install_delivery_probe(self)
    try:
        # Preserve the single canonical outside -> exact-path -> settle trajectory
        # and its fixed 5 s public tooltip oracle. The listeners are passive.
        _ORIGINAL_HOVER(self, rect)
    except BaseException as error:
        delivery = None
        diagnostic_error = None
        try:
            delivery = _read_delivery(self, rect)
        except BaseException as exc:
            diagnostic_error = exc
            try:
                _cleanup_delivery_probe(self)
            except Exception:
                pass
        _print_diagnostic(
            focus,
            gesture,
            delivery,
            outcome="hover_error",
            error=error,
            diagnostic_error=diagnostic_error,
        )
        raise

    delivery = _read_delivery(self, rect)
    _print_diagnostic(focus, gesture, delivery, outcome="hover_returned")
    diagnostic = {"focus": focus, "gesture": gesture, "delivery": delivery}

    if not delivery:
        raise RuntimeError("real tooltip hover produced no public pointer-delivery observation")
    if delivery.get("mousemove", 0) < 2 or delivery.get("pointermove", 0) < 2:
        raise RuntimeError(
            "real tooltip hover did not deliver bounded public move events: "
            + json.dumps(diagnostic, sort_keys=True)
        )
    if delivery.get("mouseover", 0) < 1 or delivery.get("pointerover", 0) < 1:
        raise RuntimeError(
            "real tooltip hover did not deliver public entry events: "
            + json.dumps(diagnostic, sort_keys=True)
        )
    if delivery.get("pathMouseover", 0) < 1 or delivery.get("pathPointerover", 0) < 1:
        raise RuntimeError(
            "real tooltip hover did not deliver public entry to the exact tooltip-bound Blockly path: "
            + json.dumps(diagnostic, sort_keys=True)
        )
    if delivery.get("pathMousemove", 0) < 2 or delivery.get("pathPointermove", 0) < 2:
        raise RuntimeError(
            "real tooltip hover did not deliver bounded moves to the exact tooltip-bound Blockly path: "
            + json.dumps(diagnostic, sort_keys=True)
        )
    hit_class = str(delivery.get("hitClass", ""))
    last_mouse = delivery.get("last", {}).get("mousemove", {})
    last_pointer = delivery.get("last", {}).get("pointermove", {})
    path_last_mouse = delivery.get("pathLast", {}).get("mousemove", {})
    path_last_pointer = delivery.get("pathLast", {}).get("pointermove", {})
    if (
        "blocklyPath" not in hit_class
        or "blocklyPath" not in str(last_mouse.get("targetClass", ""))
        or "blocklyPath" not in str(last_pointer.get("targetClass", ""))
        or "blocklyPath" not in str(path_last_mouse.get("targetClass", ""))
        or "blocklyPath" not in str(path_last_pointer.get("targetClass", ""))
    ):
        raise RuntimeError(
            "real tooltip hover did not settle on the exact public Blockly path: "
            + json.dumps(diagnostic, sort_keys=True)
        )


probe.Cdp.hover = hover_with_same_session_delivery

if __name__ == "__main__":
    probe.main()
