#!/usr/bin/env python3
"""Run the student-UI probe after proving Blockly tooltip gesture readiness."""

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
    diagnosticKeys: Object.keys(tooltip)
      .filter(key => /block|element|poison|show|visible|pid|timer/i.test(key))
      .sort(),
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


def _state(cdp: probe.Cdp) -> dict[str, object]:
    value = cdp.eval(TOOLTIP_STATE)
    if not isinstance(value, dict):
        raise RuntimeError('Blockly tooltip state probe did not return an object')
    return value


def _ready_hover(self: probe.Cdp, rect: dict[str, float]) -> None:
    before = _state(self)
    _record('before-ready-wait', before)
    if not before.get('available') or before.get('blocked') is None:
        raise RuntimeError('Blockly tooltip readiness state unavailable: ' + json.dumps(before, ensure_ascii=False))

    deadline = time.monotonic() + 2.0
    ready = before
    while ready.get('blocked') is True and time.monotonic() < deadline:
        time.sleep(.02)
        ready = _state(self)
    _record('ready-before-hover', ready)
    if ready.get('blocked') is not False:
        raise RuntimeError('Blockly tooltip remained blocked before the real hover: ' + json.dumps(ready, ensure_ascii=False))

    _ORIGINAL_HOVER(self, rect)

    after = _state(self)
    _record('after-hover', after)
    current = after.get('current') if isinstance(after.get('current'), dict) else {}
    if after.get('blocked') is not False:
        raise RuntimeError('Blockly tooltip became blocked during the real hover: ' + json.dumps(after, ensure_ascii=False))
    if current.get('type') != 'controls_repeat_ext' or current.get('tooltipType') == 'undefined':
        raise RuntimeError('real hover did not bind the repeat tooltip target: ' + json.dumps(after, ensure_ascii=False))
    if not after.get('showPidActive') and not after.get('visible'):
        raise RuntimeError('real repeat mousemove did not schedule the normal tooltip timer: ' + json.dumps(after, ensure_ascii=False))


probe.Cdp.hover = _ready_hover


if __name__ == '__main__':
    raise SystemExit(probe.main())
