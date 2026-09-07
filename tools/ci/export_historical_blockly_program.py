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

PRINT_OBSERVER_MARKERS = {
    "BoxWithDistSensor.xml": "WEBEEBLOCKS_CI_BOX_DISTANCE_BEHAVIOR_EXECUTED",
    "BoxWithGyroGPS.xml": "WEBEEBLOCKS_CI_BOX_GYRO_GPS_BEHAVIOR_EXECUTED",
    "BoxWithLightSensor.xml": "WEBEEBLOCKS_CI_BOX_LIGHT_SENSOR_BEHAVIOR_EXECUTED",
}

COMPLETION_OBSERVER_MARKERS = {
    "BoxWithEncoders.xml": "WEBEEBLOCKS_CI_BOX_ENCODERS_PROGRAM_COMPLETED",
}

SENSOR_PROBE_OBSERVER = {
    "sensorProbing.xml": (
        "WEBEEBLOCKS_CI_SENSOR_PROBE_BEHAVIOR_EXECUTED",
        ("Gyro:", "GPS:", "getDist:", "getColor:"),
    ),
}


def instrument_print_observer(code: str, program: str, marker: str) -> str:
    """Run exact generated source while requiring a Blockly text_print path to execute."""

    return f'''# CI-only observer around exact Blockly-generated source.
import builtins as _webeeblocks_ci_builtins

_WEBEEBLOCKS_CI_GENERATED_SOURCE = {code!r}
_webeeblocks_ci_original_print = _webeeblocks_ci_builtins.print
_webeeblocks_ci_observed_print = False


def _webeeblocks_ci_print(*args, **kwargs):
    global _webeeblocks_ci_observed_print
    if not _webeeblocks_ci_observed_print:
        _webeeblocks_ci_observed_print = True
        _webeeblocks_ci_original_print("{marker}")
    return _webeeblocks_ci_original_print(*args, **kwargs)


_webeeblocks_ci_builtins.print = _webeeblocks_ci_print
try:
    exec(
        compile(
            _WEBEEBLOCKS_CI_GENERATED_SOURCE,
            "<Blockly:{program}>",
            "exec",
        ),
        globals(),
        globals(),
    )
finally:
    _webeeblocks_ci_builtins.print = _webeeblocks_ci_original_print

if not _webeeblocks_ci_observed_print:
    raise RuntimeError(
        "{program} exited without reaching its Blockly text_print behavior"
    )
'''


def instrument_completion_observer(code: str, program: str, marker: str) -> str:
    """Run exact generated source and emit a marker only after it completes."""

    return f'''# CI-only completion observer around exact Blockly-generated source.
_WEBEEBLOCKS_CI_GENERATED_SOURCE = {code!r}

exec(
    compile(
        _WEBEEBLOCKS_CI_GENERATED_SOURCE,
        "<Blockly:{program}>",
        "exec",
    ),
    globals(),
    globals(),
)

print("{marker}")
'''


def instrument_sensor_probe_observer(
    code: str, program: str, marker: str, required_prefixes: tuple[str, ...]
) -> str:
    """Require all preserved sensorProbing output families to execute."""

    return f'''# CI-only multi-sensor observer around exact Blockly-generated source.
import builtins as _webeeblocks_ci_builtins

_WEBEEBLOCKS_CI_GENERATED_SOURCE = {code!r}
_WEBEEBLOCKS_CI_REQUIRED_PREFIXES = {required_prefixes!r}
_webeeblocks_ci_original_print = _webeeblocks_ci_builtins.print
_webeeblocks_ci_seen = set()
_webeeblocks_ci_marker_emitted = False


def _webeeblocks_ci_print(*args, **kwargs):
    global _webeeblocks_ci_marker_emitted
    rendered = " ".join(str(arg) for arg in args)
    for prefix in _WEBEEBLOCKS_CI_REQUIRED_PREFIXES:
        if rendered.startswith(prefix):
            _webeeblocks_ci_seen.add(prefix)
    if (
        not _webeeblocks_ci_marker_emitted
        and len(_webeeblocks_ci_seen) == len(_WEBEEBLOCKS_CI_REQUIRED_PREFIXES)
    ):
        _webeeblocks_ci_marker_emitted = True
        _webeeblocks_ci_original_print("{marker}")
    return _webeeblocks_ci_original_print(*args, **kwargs)


_webeeblocks_ci_builtins.print = _webeeblocks_ci_print
try:
    exec(
        compile(
            _WEBEEBLOCKS_CI_GENERATED_SOURCE,
            "<Blockly:{program}>",
            "exec",
        ),
        globals(),
        globals(),
    )
finally:
    _webeeblocks_ci_builtins.print = _webeeblocks_ci_original_print

if not _webeeblocks_ci_marker_emitted:
    missing = sorted(set(_WEBEEBLOCKS_CI_REQUIRED_PREFIXES) - _webeeblocks_ci_seen)
    raise RuntimeError(
        "{program} exited before all sensor behaviors were observed: " + repr(missing)
    )
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
    print_marker = PRINT_OBSERVER_MARKERS.get(args.program)
    completion_marker = COMPLETION_OBSERVER_MARKERS.get(args.program)
    sensor_probe = SENSOR_PROBE_OBSERVER.get(args.program)
    if print_marker:
        output_code = instrument_print_observer(code, args.program, print_marker)
    elif completion_marker:
        output_code = instrument_completion_observer(code, args.program, completion_marker)
    elif sensor_probe:
        marker, required_prefixes = sensor_probe
        output_code = instrument_sensor_probe_observer(
            code, args.program, marker, required_prefixes
        )
    else:
        output_code = code
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
