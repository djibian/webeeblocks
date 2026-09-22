#!/usr/bin/env python3
"""Compose the #500 tooltip repair with live direction-field geometry.

Ready run 35693970499 proved the real tooltip path itself succeeded, then exposed
an independent stale-coordinate assumption in the later direction-dropdown
check: public tooltip display shifted the Blockly workspace vertically, so the
rectangle captured before the hover no longer addressed the rendered DIRECTION
field after the tooltip closed.

This wrapper keeps the existing tooltip interaction/oracle unchanged.  It only
re-resolves the already-rendered locale-evidence direction field from the live
Blockly DOM immediately before the first independent click.  No click is retried,
no overlay or workspace state is mutated, and subsequent clicks keep the original
probe behavior.
"""

from __future__ import annotations

import inspect
import json

import probe_post_reset_geometry  # noqa: F401 - installs #500 tooltip repair
import probe


_LIVE_DIRECTION_FIELD_RECT = r'''(() => {
  const range=workspace.getBlocksByType('webeeblocks_v2_range',false)
    .find(block=>block.getRelativeToSurfaceXY().x>500);
  if(!range)throw new Error('rendered locale direction block missing for live dropdown click');
  const field=range.getField('DIRECTION');
  const root=field&&field.getSvgRoot&&field.getSvgRoot();
  if(!root)throw new Error('rendered locale direction field missing for live dropdown click');
  const r=root.getBoundingClientRect();
  const style=getComputedStyle(root);
  if(style.display==='none'||style.visibility==='hidden'||!(r.width>0&&r.height>0)){
    throw new Error('rendered locale direction field is not visibly clickable');
  }
  const x=r.x+r.width/2;
  const y=r.y+r.height/2;
  const hit=document.elementFromPoint(x,y);
  if(!hit||!(hit===root||root.contains(hit))){
    throw new Error('live direction-field centre is not owned by the rendered field');
  }
  return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom};
})()'''


_ORIGINAL_CLICK = probe.Cdp.click
_MAIN_SOURCE = inspect.getsource(probe.main)
_DIRECTION_CALL = "c.click(rendered['directionFieldRect'])"
_direction_index = _MAIN_SOURCE.find(_DIRECTION_CALL)
if (
    _MAIN_SOURCE.count(_DIRECTION_CALL) != 1
    or _direction_index < 0
    or _MAIN_SOURCE.find("c.click(") != _direction_index
    or _MAIN_SOURCE.find("c.click(vol_rect)") <= _direction_index
):
    raise RuntimeError('student-ui click ordering changed; live direction-field repair must be revalidated')


def _click_with_live_direction_field(self: probe.Cdp, rect: dict[str, object]) -> None:
    if not getattr(self, '_webeeblocks_live_direction_field_clicked', False):
        live_rect = self.eval(_LIVE_DIRECTION_FIELD_RECT)
        self._webeeblocks_live_direction_field_clicked = True
        print(
            'WEBEEBLOCKS_DIRECTION_LIVE_RECT '
            + json.dumps(live_rect, sort_keys=True)
        )
        _ORIGINAL_CLICK(self, live_rect)
        return
    _ORIGINAL_CLICK(self, rect)


probe.Cdp.click = _click_with_live_direction_field


if __name__ == '__main__':
    probe.main()
