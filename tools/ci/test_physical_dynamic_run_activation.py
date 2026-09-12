#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / "tools" / "ci"
PHYSICAL = ROOT / "tools" / "physical"
for directory in (CI, PHYSICAL):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import test_dynamic_run_activation as activation_test  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def unsupported_operator_ast() -> str:
    return activation_test.canonical(
        [
            {"height_m": 0.8, "kind": "takeoff"},
            {
                "condition": {
                    "kind": "compare",
                    "left": {
                        "kind": "arithmetic",
                        "left": {"kind": "number", "value": 2.0},
                        "op": "POWER",
                        "right": {"kind": "number", "value": 3.0},
                    },
                    "op": "GT",
                    "right": {"kind": "number", "value": 1.0},
                },
                "else": [{"kind": "wait", "seconds": 0.1}],
                "kind": "if",
                "then": [{"kind": "wait", "seconds": 0.1}],
            },
            {"kind": "land"},
        ]
    )


def test_unsupported_shared_expression_fails_before_reset_or_takeoff() -> None:
    activation_test.RANGE_FAIL = False
    activation_test.base.EVENTS.clear()
    activation_test.install_dynamic_fakes()

    replies = activation_test.host.run_host_sequence(
        unsupported_operator_ast(),
        steps=1,
    )

    require(replies[0]["ok"] is True, "run-context validation must remain diagnostic")
    require(replies[1]["ok"] is False, "caller semantic substitution must remain rejected")
    require(replies[2]["ok"] is False, "unsupported shared expression acquired execution")
    require(
        not any(
            isinstance(event, tuple) and event and event[0] == "bridge-begin"
            for event in activation_test.base.EVENTS
        ),
        "unsupported shared expression was discovered only after reset cutover",
    )
    require(
        "power-cycle" not in activation_test.base.EVENTS,
        "unsupported shared expression reached reset effect",
    )
    require(
        ("transport-send", "epoch-after") not in activation_test.base.EVENTS,
        "unsupported shared expression reached causal takeoff",
    )
    require(
        not any(
            isinstance(event, tuple)
            and event
            and event[0] in {
                "dynamic-range-open",
                "dynamic-move",
                "dynamic-turn",
                "dynamic-vertical",
                "dynamic-land",
            }
            for event in activation_test.base.EVENTS
        ),
        "unsupported shared expression reached dynamic observation/effect progression",
    )


def main() -> int:
    test_unsupported_shared_expression_fails_before_reset_or_takeoff()
    print(
        "PASS production dynamic host rejects unsupported shared expressions before "
        "reset/takeoff while caller IPC remains non-authority"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
