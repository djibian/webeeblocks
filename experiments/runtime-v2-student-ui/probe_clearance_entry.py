#!/usr/bin/env python3
"""Run the canonical student-ui tooltip probe with post-reset exact-path selection.

Exact Ready run 35653363738 refined #414: the selector had produced an exact
repeat-path point before the distinct-owner reset, but the same saved coordinates
no longer resolved to ``repeat.pathObject.svgPath`` after that real reset move.
The canonical delivery prerequisite therefore failed closed before the tooltip
oracle.

Preserve the integrated #493 finite selector and its evidenced 3 px entry / 2 px
settle clearance unchanged.  Keep the same three real pointer moves, but bind
coordinates to the DOM state in which each move is actually made.  The reset
point is reselected after the existing focus step and before the first move;
after that real distinct-owner reset move, the repeat entry/settle points are
reselected once from the then-current exact SVG path before the remaining two
moves.  This is geometry selection, not an interaction retry: no extra pointer
move is emitted, no tooltip/workspace state is assigned, no timer or Blockly
lifecycle function is wrapped, and the unchanged 5 s public tooltip oracle plus
ordinary-leave assertion remain authoritative.
"""

from __future__ import annotations

import json
import time

import probe
import probe_entry
import probe_post_hover_entry as integrated


# Reuse the integrated #493 exact-path selector without retuning its geometry.
# The causal delta in this candidate is when selection occurs, not how large an
# arbitrary pre-fire clearance radius is required.
probe.REPEAT_HOVER_RECT = integrated._RESET_REPEAT_HOVER_RECT


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
    # focus check.  Re-evaluate geometry before the first real pointer move so
    # the distinct-owner reset itself is aimed at the current exact path.
    before_reset = c.eval(probe.REPEAT_HOVER_RECT)
    _copy_reset_target(rect, before_reset)

    c.call(
        "Input.dispatchMouseEvent",
        {"type": "mouseMoved", "x": rect["outsideX"], "y": rect["outsideY"]},
    )
    time.sleep(0.1)

    # Exact Ready evidence proved that the reset move can invalidate coordinates
    # chosen beforehand.  Select once from the post-reset DOM state before the
    # canonical exact-path delivery probe and the remaining two real moves.
    # There is no additional hover or outcome-conditioned retry.
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
