#!/usr/bin/env python3
"""Run the real student-UI probe with one stable CDP mouse hover trajectory."""

from __future__ import annotations

import time

import probe


def stable_hover(self: probe.Cdp, rect: dict[str, float]) -> None:
    """Cross the target boundary, then emit one settled real mouse movement.

    Blockly's tooltip binding records the hovered element on ``mouseover`` and
    only schedules display from a later ``mousemove``.  After closing a dropdown,
    one long diagonal CDP trajectory can finish on the block in the same dispatch
    that establishes ``mouseover``.  A short local outside-to-inside trajectory
    followed by a tiny in-target movement proves the normal browser event order
    without calling Blockly tooltip internals or retrying the assertion.
    """
    target_x = rect['x'] + rect['width'] / 2
    target_y = rect['y'] + rect['height'] / 2
    start_y = max(1.0, target_y - 16.0)

    def move(x: float, y: float) -> None:
        self.call('Input.dispatchMouseEvent', {
            'type': 'mouseMoved',
            'x': x,
            'y': y,
            'buttons': 0,
            'pointerType': 'mouse',
        })

    move(target_x, start_y)
    time.sleep(.1)
    for step in range(1, 9):
        fraction = step / 8
        move(target_x, start_y + (target_y - start_y) * fraction)
        time.sleep(.04)

    # A real pointer normally generates another mousemove after entering the
    # target.  Keep both points inside the 2 px hit-tested rectangle so this is
    # still a user-equivalent hover, not a direct tooltip invocation.
    time.sleep(.05)
    move(target_x - 0.25, target_y)
    time.sleep(.05)
    move(target_x + 0.25, target_y)


probe.Cdp.hover = stable_hover


if __name__ == '__main__':
    raise SystemExit(probe.main())
