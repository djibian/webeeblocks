#!/usr/bin/env python3
"""Combine post-reset target reselection with passive geometry/occupancy evidence.

This wrapper keeps the #500 real three-move hover and unchanged public tooltip
oracle while reusing the closed #497 passive diagnostic. It dispatches no extra
input and changes no Blockly, workspace or tooltip state.
"""

from __future__ import annotations

import probe_post_hover_occupancy  # noqa: F401 - installs passive diagnostic
import probe_clearance_entry  # noqa: F401 - installs post-reset reselection
import probe


if __name__ == "__main__":
    probe.main()
