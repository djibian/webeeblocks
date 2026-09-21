#!/usr/bin/env python3
"""Extend the passive #414 geometry diagnostic with exact SVG occupancy.

A green geometry run showed the stationary repeat-hover point inside both the
repeat and takeoff path bounding rectangles while the public hit stack contained
only the repeat path.  Bounding-box overlap is not enough to justify the
geometric-exclusion repair, so this wrapper adds the missing passive discriminator:
for the unchanged client point, record whether each exact SVG path's fill/stroke
geometry contains that point.  It dispatches no input and changes no oracle,
Blockly state, workspace state, tooltip state, timing or candidate selection.
"""

from __future__ import annotations

import probe_post_hover_geometry as geometry


base = geometry.base

_OCCUPANCY_HELPER = r'''
  const occupancyOf=(node,px,py)=>{
    if(!node||typeof node.getScreenCTM!=='function'||typeof node.isPointInFill!=='function')return null;
    const matrix=node.getScreenCTM();
    if(!matrix||typeof matrix.inverse!=='function')return null;
    try{
      const local=new DOMPoint(px,py).matrixTransform(matrix.inverse());
      return {
        fill:!!node.isPointInFill(local),
        stroke:typeof node.isPointInStroke==='function' ? !!node.isPointInStroke(local) : null
      };
    }catch(_){return null;}
  };
'''

_REPEAT_OLD = "repeat:{rect:rectOf(repeatPath),ctm:matrixOf(repeatPath),rootRect:rectOf(repeat&&repeat.getSvgRoot&&repeat.getSvgRoot())}"
_REPEAT_NEW = "repeat:{rect:rectOf(repeatPath),ctm:matrixOf(repeatPath),rootRect:rectOf(repeat&&repeat.getSvgRoot&&repeat.getSvgRoot()),occupancy:occupancyOf(repeatPath,x,y)}"
_TAKEOFF_OLD = "takeoff:{rect:rectOf(takeoffPath),ctm:matrixOf(takeoffPath),rootRect:rectOf(takeoff&&takeoff.getSvgRoot&&takeoff.getSvgRoot())}"
_TAKEOFF_NEW = "takeoff:{rect:rectOf(takeoffPath),ctm:matrixOf(takeoffPath),rootRect:rectOf(takeoff&&takeoff.getSvgRoot&&takeoff.getSvgRoot()),occupancy:occupancyOf(takeoffPath,x,y)}"


def _add_occupancy(source: str) -> str:
    marker = "  const geometry=()=>{"
    if marker not in source:
        raise RuntimeError("geometry marker missing from passive #414 diagnostic")
    if _REPEAT_OLD not in source or _TAKEOFF_OLD not in source:
        raise RuntimeError("path geometry records missing from passive #414 diagnostic")
    source = source.replace(marker, _OCCUPANCY_HELPER + "\n" + marker, 1)
    source = source.replace(_REPEAT_OLD, _REPEAT_NEW, 1)
    source = source.replace(_TAKEOFF_OLD, _TAKEOFF_NEW, 1)
    return source


base._POST_HOVER_INSTALL = _add_occupancy(base._POST_HOVER_INSTALL)
base._POST_HOVER_SNAPSHOT = _add_occupancy(base._POST_HOVER_SNAPSHOT)


if __name__ == "__main__":
    base.probe.main()
