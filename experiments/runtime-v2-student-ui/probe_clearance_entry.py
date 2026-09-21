#!/usr/bin/env python3
"""Run the canonical student-ui tooltip probe with deeper exact-path clearance.

Fresh #414 evidence on Ready run 35648562803 showed the #493 distinct-owner
reset working far enough for the real localized repeat tooltip to render, but
the chosen exact repeat path point then re-hit-tested to the connected takeoff
path and hid the tooltip immediately.  The retained #493 selector only required
3 px entry / 2 px settle clearance and sampled offsets beginning 5 px from the
SVG path boundary.

This wrapper preserves the same real-pointer owner-reset interaction, passive
post-hover diagnostics, unchanged 5 s public tooltip oracle and ordinary-leave
closure assertion.  It changes only the pre-hover geometry requirement: sample
13/17/21 px from the exact SVG path and require a 10 px exclusive repeat-path
neighbourhood at entry plus 9 px at settle.  No tooltip/workspace state is
mutated, no timer/lifecycle function is wrapped, and no outcome-conditioned
retry is added.
"""

from __future__ import annotations

import json

import probe
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
_BASE_HOVER = probe.Cdp.hover


def hover_with_clearance_evidence(self: probe.Cdp, rect: dict[str, object]) -> None:
    print(
        "WEBEEBLOCKS_TOOLTIP_CLEARANCE_TARGET "
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
    _BASE_HOVER(self, rect)


probe.Cdp.hover = hover_with_clearance_evidence

if __name__ == "__main__":
    probe.main()
