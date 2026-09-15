#!/usr/bin/env python3
"""Run the student-UI probe with causal Blockly tooltip diagnostics."""

from __future__ import annotations

import json
import os
from pathlib import Path

import probe


TOOLTIP_DIAGNOSTIC = r'''(() => {
  const tooltip = Blockly.Tooltip;
  if (!tooltip) return {available:false};
  const repeat=workspace.getBlocksByType('controls_repeat_ext',false)[0];
  const path=repeat&&repeat.pathObject&&repeat.pathObject.svgPath;
  const allWorkspaces=typeof Blockly.getAllWorkspaces==='function'
    ? Blockly.getAllWorkspaces()
    : (Blockly.common&&typeof Blockly.common.getAllWorkspaces==='function'
      ? Blockly.common.getAllWorkspaces()
      : [workspace]);
  return {
    available:true,
    visible:typeof tooltip.isVisible==='function'?Boolean(tooltip.isVisible()):null,
    gestureIdle:typeof workspace.getGesture==='function'?workspace.getGesture()===null:null,
    workspaceGestures:allWorkspaces.map((ws,index)=>({
      index:index,
      rendered:Boolean(ws&&ws.rendered),
      main:ws===workspace,
      gestureIdle:ws&&typeof ws.getGesture==='function'?ws.getGesture()===null:null,
    })),
    pathBound:Boolean(path&&repeat&&path.tooltip===repeat),
    pathBindingKeys:path?Object.keys(path).filter(key=>/wrapper|tooltip/i.test(key)).sort():[],
    diagnosticKeys:Object.keys(tooltip)
      .filter(key=>/block|element|poison|show|visible|pid|timer|tooltip/i.test(key))
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
  const record=phase=>event=>{
    trace.push({
      type:event.type,
      phase:phase,
      pointerType:typeof event.pointerType==='string'?event.pointerType:null,
      pointerId:typeof event.pointerId==='number'?event.pointerId:null,
      clientX:event.clientX,
      clientY:event.clientY,
      pageX:event.pageX,
      pageY:event.pageY,
      buttons:event.buttons,
      target:describeNode(event.target),
      currentTargetIsRepeatPath:event.currentTarget===path,
      relatedTarget:describeNode(event.relatedTarget),
    });
  };
  for(const type of ['pointerover','pointermove','pointerout','mouseover','mousemove','mouseout']){
    path.addEventListener(type,record('capture'),{capture:true,passive:true});
    path.addEventListener(type,record('bubble'),{capture:false,passive:true});
  }
  window.__webeeblocksTooltipEventTrace={path:path,events:trace};
  return {
    installed:true,
    eventCount:trace.length,
    pathBindingKeys:Object.keys(path).filter(key=>/wrapper|tooltip/i.test(key)).sort(),
  };
})()'''

EVENT_TRACE = r'''(() => {
  const trace=window.__webeeblocksTooltipEventTrace;
  if(!trace||!trace.path||!Array.isArray(trace.events))return {available:false,events:[]};
  const repeat=workspace.getBlocksByType('controls_repeat_ext',false)[0];
  const tooltip=Blockly.Tooltip;
  const allWorkspaces=typeof Blockly.getAllWorkspaces==='function'
    ? Blockly.getAllWorkspaces()
    : (Blockly.common&&typeof Blockly.common.getAllWorkspaces==='function'
      ? Blockly.common.getAllWorkspaces()
      : [workspace]);
  return {
    available:true,
    pathStillBound:Boolean(repeat&&trace.path===repeat.pathObject.svgPath&&trace.path.tooltip===repeat),
    visible:tooltip&&typeof tooltip.isVisible==='function'?Boolean(tooltip.isVisible()):null,
    gestureIdle:typeof workspace.getGesture==='function'?workspace.getGesture()===null:null,
    workspaceGestures:allWorkspaces.map((ws,index)=>({
      index:index,
      rendered:Boolean(ws&&ws.rendered),
      main:ws===workspace,
      gestureIdle:ws&&typeof ws.getGesture==='function'?ws.getGesture()===null:null,
    })),
    pathBindingKeys:Object.keys(trace.path).filter(key=>/wrapper|tooltip/i.test(key)).sort(),
    events:trace.events.slice(),
  };
})()'''


_ORIGINAL_HOVER = probe.Cdp.hover
_SNAPSHOTS: list[dict[str, object]] = []
_LAST_CDP: probe.Cdp | None = None


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


def _diagnostic(cdp: probe.Cdp) -> dict[str, object]:
    return _object(cdp, TOOLTIP_DIAGNOSTIC, 'Blockly tooltip diagnostic probe')


def _event_trace(cdp: probe.Cdp) -> dict[str, object]:
    return _object(cdp, EVENT_TRACE, 'Blockly tooltip browser-event trace')


def _ready_hover(self: probe.Cdp, rect: dict[str, float]) -> None:
    global _LAST_CDP
    _LAST_CDP = self

    before = _diagnostic(self)
    _record('before-hover', before)
    if not before.get('available'):
        raise RuntimeError('Blockly tooltip API unavailable before the real hover: ' + json.dumps(before, ensure_ascii=False))
    if before.get('gestureIdle') is not True:
        raise RuntimeError('Blockly workspace gesture was still active before tooltip hover: ' + json.dumps(before, ensure_ascii=False))
    workspace_gestures = before.get('workspaceGestures') if isinstance(before.get('workspaceGestures'), list) else []
    if any(isinstance(item, dict) and item.get('gestureIdle') is False for item in workspace_gestures):
        raise RuntimeError('a Blockly workspace gesture was still active before tooltip hover: ' + json.dumps(before, ensure_ascii=False))

    installed = _object(self, INSTALL_EVENT_TRACE, 'Blockly tooltip browser-event trace installation')
    _record('event-trace-installed', installed)
    if installed.get('installed') is not True:
        raise RuntimeError('Blockly tooltip browser-event trace was not installed: ' + json.dumps(installed, ensure_ascii=False))

    _ORIGINAL_HOVER(self, rect)

    events = _event_trace(self)
    _record('after-hover-events', events)
    event_list = events.get('events') if isinstance(events.get('events'), list) else []
    bubble_types = [
        event.get('type') for event in event_list
        if isinstance(event, dict) and event.get('phase') == 'bubble'
    ]
    try:
        over_index = bubble_types.index('pointerover')
        move_index = bubble_types.index('pointermove', over_index + 1)
    except ValueError as exc:
        raise RuntimeError('real CDP hover did not deliver causal pointerover then pointermove through the exact repeat path: ' + json.dumps(events, ensure_ascii=False)) from exc
    if move_index <= over_index or events.get('pathStillBound') is not True or events.get('gestureIdle') is not True:
        raise RuntimeError('real CDP pointer-event boundary was not stable: ' + json.dumps(events, ensure_ascii=False))
    workspace_gestures = events.get('workspaceGestures') if isinstance(events.get('workspaceGestures'), list) else []
    if any(isinstance(item, dict) and item.get('gestureIdle') is False for item in workspace_gestures):
        raise RuntimeError('a Blockly workspace gesture became active during the real hover: ' + json.dumps(events, ensure_ascii=False))

    after = _diagnostic(self)
    _record('after-hover', after)
    if after.get('gestureIdle') is not True:
        raise RuntimeError('Blockly workspace gesture became active during the real hover: ' + json.dumps(after, ensure_ascii=False))


probe.Cdp.hover = _ready_hover


def _record_terminal_diagnostics() -> None:
    if _LAST_CDP is None:
        return
    try:
        _record('terminal-events', _event_trace(_LAST_CDP))
        _record('terminal-diagnostic', _diagnostic(_LAST_CDP))
    except Exception as exc:
        _record('terminal-diagnostic-error', {'error': repr(exc)})


if __name__ == '__main__':
    try:
        raise SystemExit(probe.main())
    except BaseException:
        _record_terminal_diagnostics()
        raise
