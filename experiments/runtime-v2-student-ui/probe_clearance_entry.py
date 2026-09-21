#!/usr/bin/env python3
"""Run the canonical student-ui tooltip probe with post-reset exact-path selection.

Fresh #414 evidence first showed that the integrated #493 pre-hover target could
sit too close to a connected path boundary.  Exact Ready run 35653363738 then
refined the failure: a deeper pre-hover point was exclusive to the repeat path,
but after the distinct-owner reset the same saved coordinates no longer resolved
to ``repeat.pathObject.svgPath`` and the canonical delivery probe correctly
failed closed before the tooltip oracle.

Keep the same finite exact-path selector and the same three real pointer moves,
but bind coordinates to the DOM state in which each move is actually made.  The
reset point is reselected after the existing focus step and before the first
move; after that real distinct-owner reset move, the repeat entry/settle points
are reselected once from the then-current exact SVG path before the remaining
two moves.  This is geometry selection, not an interaction retry: no extra
pointer move is emitted, no tooltip/workspace state is assigned, no timer or
Blockly lifecycle function is wrapped, and the unchanged 5 s public tooltip
oracle plus ordinary-leave assertion remain authoritative.
"""

from __future__ import annotations

import json
import time

import probe
import probe_entry
import probe_post_hover_entry as integrated


_DEEP_CLEARANCE_REPLACEMENTS = (
    ("const offsets=[5,9,13];", "const offsets=[13,17,21];"),
    ("const entry=stablePoint(repeatPath,3);", "const entry=stablePoint(repeatPath,10);"),
    (
        "const settle=neighbours.find(([sx,sy])=>hasClearance(repeatPath,sx,sy,2));",
        "const settle=neighbours.find(([sx,sy])=>hasClearance(repeatPath,sx,sy,9));",
    ),
)


def _deeper_repeat_hover_rect() -> str:
    expression = integrated._RESET_REPEAT_HOVER_RECT
    for old, new in _DEEP_CLEARANCE_REPLACEMENTS:
        count = expression.count(old)
        if count != 1:
            raise RuntimeError(
                "integrated tooltip geometry contract changed unexpectedly: "
                + json.dumps({"needle": old, "count": count}, sort_keys=True)
            )
        expression = expression.replace(old, new, 1)
    return expression


probe.REPEAT_HOVER_RECT = _deeper_repeat_hover_rect()


def _copy_repeat_target(target: dict[str, object], source: dict[str, object]) -> None:
    for key in (
        "x",
        "y",
        "width",
        "height",
        "entryX",
        "entryY",
        "settleX",
        "settleY",
        "hitTag",
        "hitClass",
        "stableClearance",
        "entryStack",
        "settleStack",
    ):
        target[key] = source[key]


def _copy_reset_target(target: dict[str, object], source: dict[str, object]) -> None:
    for key in (
        "outsideX",
        "outsideY",
        "resetTag",
        "resetClass",
        "resetClearance",
        "resetStack",
    ):
        target[key] = source[key]


def _canonical_hover_with_post_reset_reselection(
    c: probe.Cdp, rect: dict[str, object]
) -> None:
    # ``hover_with_passive_diagnostics`` has already performed the existing
    # focus check.  Re-evaluate only geometry before the first real pointer move
    # so the distinct-owner reset itself is aimed at the current exact path.
    before_reset = c.eval(probe.REPEAT_HOVER_RECT)
    _copy_reset_target(rect, before_reset)

    c.call(
        "Input.dispatchMouseEvent",
        {"type": "mouseMoved", "x": rect["outsideX"], "y": rect["outsideY"]},
    )
    time.sleep(0.1)

    # The owner-reset move may alter hit ownership/geometry.  Select once again
    # from that post-reset DOM state before installing the canonical exact-path
    # delivery probe.  This adds no pointer interaction and therefore cannot turn
    # a failed hover into a retry.
    after_reset = c.eval(probe.REPEAT_HOVER_RECT)
    _copy_repeat_target(rect, after_reset)

    print(
        "WEBEEBLOCKS_TOOLTIP_POST_RESET_TARGET "
        + json.dumps(
            {
                "entry": [rect.get("entryX"), rect.get("entryY")],
                "settle": [rect.get("settleX"), rect.get("settleY")],
                "reset": [rect.get("outsideX"), rect.get("outsideY")],
                "stableClearance": rect.get("stableClearance"),
                "resetClearance": rect.get("resetClearance"),
                "entryStack": rect.get("entryStack"),
                "settleStack": rect.get("settleStack"),
                "resetStack": rect.get("resetStack"),
            },
            sort_keys=True,
        )
    )

    probe_entry._install_delivery_probe(c, rect)
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


probe_entry._canonical_hover_after_reset = _canonical_hover_with_post_reset_reselection

if __name__ == "__main__":
    probe.main()
