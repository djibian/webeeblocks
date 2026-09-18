#!/usr/bin/env python3
"""Run the canonical student UI probe with an exact same-session hover boundary.

The product/runtime probe remains authoritative. This entrypoint only strengthens
its real-tooltip evidence: immediately before the canonical hover, the same CDP
session brings the Robot Window to the front and passively proves the exact
public pointer/mouse entry, movement and exit sequence delivered around the
Blockly path selected by the existing probe. It does not mutate Blockly tooltip
state, workspace state, timeout values or pass conditions.
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


def _install_delivery_probe(c: probe.Cdp) -> None:
    c.eval(
        r'''(() => {
          const key='__webeeblocksCiTooltipDelivery';
          if(window[key]&&window[key].cleanup)window[key].cleanup();
          const state={
            mousemove:0,mouseover:0,pointermove:0,pointerover:0,mouseout:0,pointerout:0,
            last:{},events:[],cleanup:null
          };
          const pack=e=>({
            x:e.clientX,y:e.clientY,
            targetTag:(e.target&&e.target.tagName)||'',
            targetClass:String((e.target&&e.target.getAttribute&&e.target.getAttribute('class'))||''),
            relatedTag:(e.relatedTarget&&e.relatedTarget.tagName)||'',
            relatedClass:String((e.relatedTarget&&e.relatedTarget.getAttribute&&e.relatedTarget.getAttribute('class'))||'')
          });
          const handlers={};
          for(const type of ['mousemove','mouseover','pointermove','pointerover','mouseout','pointerout']){
            handlers[type]=e=>{
              state[type]+=1;
              const event={type,...pack(e)};
              state.last[type]=event;
              if(state.events.length<64)state.events.push(event);
            };
            document.addEventListener(type,handlers[type],true);
          }
          state.cleanup=()=>{for(const type of Object.keys(handlers))document.removeEventListener(type,handlers[type],true);};
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
        mouseout:s.mouseout,pointerout:s.pointerout,last:s.last,events:s.events,
        hitTag:(hit&&hit.tagName)||'',
        hitClass:String((hit&&hit.getAttribute&&hit.getAttribute('class'))||'')
      };
      s.cleanup(); delete window[key];
      return result;
    })(%s,%s)''' % (settle_x, settle_y)
    return c.eval(expression)


def _is_path_event(event: object, event_type: str) -> bool:
    return bool(
        isinstance(event, dict)
        and event.get("type") == event_type
        and "blocklyPath" in str(event.get("targetClass", ""))
    )


def hover_with_same_session_delivery(self: probe.Cdp, rect: dict[str, object]) -> None:
    focus = _same_session_focus(self)
    _install_delivery_probe(self)
    try:
        _ORIGINAL_HOVER(self, rect)
        delivery = _read_delivery(self, rect)
    except BaseException:
        try:
            self.eval(
                "(() => {const s=window.__webeeblocksCiTooltipDelivery;if(s&&s.cleanup)s.cleanup();delete window.__webeeblocksCiTooltipDelivery;return true;})()"
            )
        except Exception:
            pass
        raise

    if not delivery:
        raise RuntimeError("real tooltip hover produced no public pointer-delivery observation")

    evidence = {"focus": focus, "delivery": delivery}
    print(
        "WEBEEBLOCKS_STUDENT_UI_HOVER_DELIVERY "
        + json.dumps(evidence, sort_keys=True, separators=(",", ":"))
    )

    if delivery.get("mousemove", 0) < 2 or delivery.get("pointermove", 0) < 2:
        raise RuntimeError(
            "real tooltip hover did not deliver bounded public move events: "
            + json.dumps(evidence, sort_keys=True)
        )
    if delivery.get("mouseover", 0) < 1 or delivery.get("pointerover", 0) < 1:
        raise RuntimeError(
            "real tooltip hover did not deliver public entry events: "
            + json.dumps(evidence, sort_keys=True)
        )

    events = delivery.get("events", [])
    mouse_entry = next((i for i, event in enumerate(events) if _is_path_event(event, "mouseover")), None)
    pointer_entry = next((i for i, event in enumerate(events) if _is_path_event(event, "pointerover")), None)
    if mouse_entry is None or pointer_entry is None:
        raise RuntimeError(
            "real tooltip hover entry did not target the exact public Blockly path: "
            + json.dumps(evidence, sort_keys=True)
        )

    last_entry = max(mouse_entry, pointer_entry)
    premature_exit = [
        event
        for event in events[last_entry + 1 :]
        if _is_path_event(event, "mouseout") or _is_path_event(event, "pointerout")
    ]
    if premature_exit:
        raise RuntimeError(
            "real tooltip hover left the exact public Blockly path before the canonical wait: "
            + json.dumps(evidence, sort_keys=True)
        )

    hit_class = str(delivery.get("hitClass", ""))
    last_mouse = delivery.get("last", {}).get("mousemove", {})
    last_pointer = delivery.get("last", {}).get("pointermove", {})
    if (
        "blocklyPath" not in hit_class
        or "blocklyPath" not in str(last_mouse.get("targetClass", ""))
        or "blocklyPath" not in str(last_pointer.get("targetClass", ""))
    ):
        raise RuntimeError(
            "real tooltip hover did not settle on the exact public Blockly path: "
            + json.dumps(evidence, sort_keys=True)
        )


probe.Cdp.hover = hover_with_same_session_delivery

if __name__ == "__main__":
    probe.main()
