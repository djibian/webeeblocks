#!/usr/bin/env python3
"""Compatibility import for the isolated resumable shared-interpreter session.

The implementation lives under ``tools/session`` so its private
``shared_interpreter_worker.js`` cannot replace the already-integrated worker
used by ``shared_interpreter_host.py``. Range/control-flow semantics remain in
the authoritative Runtime interpreter; this file only exposes the trusted-host
session types from their isolated transport directory.
"""

from __future__ import annotations

from pathlib import Path
import sys

_PHYSICAL = Path(__file__).resolve().parent
_TOOLS = _PHYSICAL.parent
for _directory in (_PHYSICAL, _TOOLS):
    _text = str(_directory)
    if _text not in sys.path:
        sys.path.insert(0, _text)

from session.shared_interpreter_session import (  # noqa: E402,F401
    SelectedPhysicalAction,
    SharedInterpreterSession,
    SharedInterpreterSessionError,
)

__all__ = [
    "SelectedPhysicalAction",
    "SharedInterpreterSession",
    "SharedInterpreterSessionError",
]
