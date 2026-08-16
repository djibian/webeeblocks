#!/usr/bin/env python3
"""Export one preserved Blockly fixture using the real vendored Blockly 2020 runtime."""

from __future__ import annotations

import argparse
import hashlib
import tempfile
from pathlib import Path

from run_historical_blockly_oracle import (
    EXPECTED_PYTHON_SHA256,
    ROBOT_WINDOW_DIR,
    build_harness,
    run_browser,
)


def instrument_box_distance_controller(code: str) -> str:
    """Run the exact generated source while requiring its historical print block to execute.

    BoxWithDistSensor contains a Blockly ``text_print`` block inside the distance-sensor
    loop.  The CI wrapper observes calls to Python's builtin ``print`` without changing
    the generated source bytes, then fails after execution if that Blockly-generated
    behavior was never reached.  This prevents the supervisor timeout from creating a
    false-positive end-to-end result when ``my_controller`` exits too early.
    """

    return f'''# CI-only observer around exact Blockly-generated source.
import builtins as _webeeblocks_ci_builtins

_WEBEEBLOCKS_CI_GENERATED_SOURCE = {code!r}
_webeeblocks_ci_original_print = _webeeblocks_ci_builtins.print
_webeeblocks_ci_observed_print = False


def _webeeblocks_ci_print(*args, **kwargs):
    global _webeeblocks_ci_observed_print
    _webeeblocks_ci_observed_print = True
    return _webeeblocks_ci_original_print(*args, **kwargs)


_webeeblocks_ci_builtins.print = _webeeblocks_ci_print
try:
    exec(
        compile(
            _WEBEEBLOCKS_CI_GENERATED_SOURCE,
            "<Blockly:BoxWithDistSensor.xml>",
            "exec",
        ),
        globals(),
        globals(),
    )
finally:
    _webeeblocks_ci_builtins.print = _webeeblocks_ci_original_print

if not _webeeblocks_ci_observed_print:
    raise RuntimeError(
        "BoxWithDistSensor controller exited without reaching its Blockly text_print sensor behavior"
    )

_webeeblocks_ci_original_print("WEBEEBLOCKS_CI_BOX_DISTANCE_BEHAVIOR_EXECUTED")
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("program", choices=tuple(EXPECTED_PYTHON_SHA256))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", dir=ROBOT_WINDOW_DIR, encoding="utf-8", delete=False
    ) as handle:
        handle.write(build_harness())
        harness_path = Path(handle.name)

    try:
        result = run_browser(harness_path)
    finally:
        harness_path.unlink(missing_ok=True)

    if not result.get("ok"):
        raise RuntimeError(f"Blockly browser execution failed: {result.get('error')}")

    generated = result.get("programs")
    if not isinstance(generated, dict):
        raise RuntimeError("Blockly browser result is malformed")
    entry = generated.get(args.program)
    if not isinstance(entry, dict) or not isinstance(entry.get("code"), str):
        raise RuntimeError(f"missing generated Python for {args.program}")

    code = entry["code"]
    digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
    expected = EXPECTED_PYTHON_SHA256[args.program]
    if digest != expected:
        raise RuntimeError(
            f"generated Python drift for {args.program}: sha256={digest}, expected={expected}"
        )

    compile(code, f"<Blockly:{args.program}>", "exec")
    output_code = (
        instrument_box_distance_controller(code)
        if args.program == "BoxWithDistSensor.xml"
        else code
    )
    compile(output_code, f"<CI:{args.program}>", "exec")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output_code, encoding="utf-8")
    print(
        f"PASS: exported exact {args.program} source (sha256={digest}) to {args.output}; "
        f"CI wrapper bytes={len(output_code.encode('utf-8'))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
