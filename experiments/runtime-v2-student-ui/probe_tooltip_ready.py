#!/usr/bin/env python3
"""Run the student-UI probe with causal Blockly tooltip diagnostics."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import probe


TOOLTIP_STATE = r'''(() => {
  const tooltip = Blockly.Tooltip;
  if (!tooltip) return {available:false};
  const describe = value => {
    if (!value) return null;
    return {
      type: typeof value.type === 'string' ? value.type : null,
      id: typeof value.id === 'string' ? value.id : null,
      tooltipType: typeof value.tooltip,
      tooltipText: typeof value.tooltip === 'string' ? value.tooltip : null,
    };
  };
  return {
    available:true,
    blocked: typeof tooltip.blocked_ === 'boolean' ? tooltip.blocked_ : null,
    visible: Boolean(tooltip.visible),
    showPidActive: Boolean(tooltip.showPid_),
    current: describe(tooltip.element_),
    poisoned: describe(tooltip.poisonedElement_),
    gestureIdle: typeof workspace.getGesture === 'function' ? workspace.getGesture() === null : null,
    diagnosticKeys: Object.keys(tooltip)
      .filter(key => /block|element|poison|show|visible|pid|timer/i.test(key))
      .sort(),
  };
})()'''

INSTALL_EVENT_TRACE = r'''(() => {
  const repeat=workspace.getBlocksByType('controls_repeat_ext',false)[0];
  if(!repeat)throw new Error('rendered repeat block missing for tooltip event trace');
  const path=repeat.pathObject&&repeat.pathObject.svgPath;
  if(!path)throw new Error('rendered repeat tooltip-bound path missing for event trace');
  if(path.tooltip!==repeat)throw new Error('repeat event-trace path is not bound to repeat tooltip object');
  const trace=[];
  const describeNode=node=>node?{
    tag:String(node.tagName||''),
    className:String(node.getAttribute&&node.getAttribute('class')||''),
    isRepeatPath:node===path,
  }:null;
  for(const type of ['mouseover','mousemove','mouseout']){
    path.addEventListener(type,event=>{
      trace.push({
        type:event.type,
        clientX:event.clientX,
        clientY:event.clientY,
        buttons:event.buttons,
        target:describeNode(event.target),
        currentTargetIsRepeatPath:event.currentTarget===path,
        relatedTarget:describeNode(event.relatedTarget),
      });
    },{capture:false,passive:true});
  }
  window.__webeeblocksTooltipEventTrace={path:path,events:trace};
  return {installed:true,eventCount:trace.length};
})()'''

EVENT_TRACE = r'''(() => {
  const trace=window.__webeeblocksTooltipEventTrace;
  if(!trace||!trace.path||!Array.isArray(trace.events))return {available:false,events:[]};
  const repeat=workspace.getBlocksByType('controls_repeat_ext',false)[0];
  return {
    available:true,
    pathStillBound:Boolean(repeat&&trace.path===repeat.pathObject.svgPath&&trace.path.tooltip===repeat),
    gestureIdle:typeof workspace.getGesture==='function'?workspace.getGesture()===null:null,
    events:trace.events.slice(),
  };
})()'''


_ORIGINAL_HOVER = probe.Cdp.hover
_SNAPSHOTS: list[dict[str, object]] = []


def _artifact_path() -> Path:
    directory = Path(os.environ.get('WEBEEBLOCKS_CI_ARTIFACT_DIR', '/tmp'))
    directory.mkdir(parents=True, exist_ok=True)
    return directory / 'tooltip-state.json'


def _record(label: str, state: dict[str, object]) -> None:
    entry = {'label': label, 'state': state}
    _SNAPSHOTS.append(entry)
    _artifact_path().write_text(
        json.dumps(_SNAPSHOTS, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    print('WEBEEBLOCKS_TOOLTIP_STATE ' + json.dumps(entry, ensure_ascii=False), flush=True)


def _object(cdp: probe.Cdp, expression: str, label: str) -> dict[str, object]:
    value = cdp.eval(expression)
    if not isinstance(value, dict):
        raise RuntimeError(f'{label} did not return an object')
    return value


def _state(cdp: probe.Cdp) -> dict[str, object]:
    return _object(cdp, TOOLTIP_STATE, 'Blockly tooltip state probe')


def _event_trace(cdp: probe.Cdp) -> dict[str, object]:
    return _object(cdp, EVENT_TRACE, 'Blockly tooltip browser-event trace')


def _ready_hover(self: probe.Cdp, rect: dict[str, float]) -> None:
    before = _state(self)
    _record('before-ready-wait', before)
    if not before.get('available') or before.get('blocked') is None:
        raise RuntimeError('Blockly tooltip readiness state unavailable: ' + json.dumps(before, ensure_ascii=False))
    if before.get('gestureIdle') is not True:
        raise RuntimeError('Blockly workspace gesture was still active before tooltip hover: ' + json.dumps(before, ensure_ascii=False))

    deadline = time.monotonic() + 2.0
    ready = before
    while ready.get('blocked') is True and time.monotonic() < deadline:
        time.sleep(.02)
        ready = _state(self)
    _record('ready-before-hover', ready)
    if ready.get('blocked') is not False or ready.get('gestureIdle') is not True:
        raise RuntimeError('Blockly tooltip subsystem was not causally ready before the real hover: ' + json.dumps(ready, ensure_ascii=False))

    installed = _object(self, INSTALL_EVENT_TRACE, 'Blockly tooltip browser-event trace installation')
    _record('event-trace-installed', installed)
    if installed.get('installed') is not True:
        raise RuntimeError('Blockly tooltip browser-event trace was not installed: ' + json.dumps(installed, ensure_ascii=False))

    _ORIGINAL_HOVER(self, rect)

    events = _event_trace(self)
    _record('after-hover-events', events)
    event_list = events.get('events') if isinstance(events.get('events'), list) else []
    event_types = [event.get('type') for event in event_list if isinstance(event, dict)]
    try:
        over_index = event_types.index('mouseover')
        move_index = event_types.index('mousemove', over_index + 1)
    except ValueError as exc:
        raise RuntimeError('real CDP hover did not deliver causal mouseover then mousemove on the exact repeat path: ' + json.dumps(events, ensure_ascii=False)) from exc
    if move_index <= over_index or events.get('pathStillBound') is not True or events.get('gestureIdle') is not True:
        raise RuntimeError('real CDP hover browser-event boundary was not stable: ' + json.dumps(events, ensure_ascii=False))

    after = _state(self)
    _record('after-hover', after)
    current = after.get('current') if isinstance(after.get('current'), dict) else {}
    if after.get('blocked') is not False or after.get('gestureIdle') is not True:
        raise RuntimeError('Blockly tooltip became blocked or gesture-active during the real hover: ' + json.dumps(after, ensure_ascii=False))
    if current.get('type') != 'controls_repeat_ext' or current.get('tooltipType') == 'undefined':
        raise RuntimeError('real hover did not bind the repeat tooltip target: ' + json.dumps(after, ensure_ascii=False))
    if not after.get('showPidActive') and not after.get('visible'):
        raise RuntimeError('real repeat mousemove did not schedule the normal tooltip timer: ' + json.dumps(after, ensure_ascii=False))


probe.Cdp.hover = _ready_hover


if __name__ == '__main__':
    raise SystemExit(probe.main())
